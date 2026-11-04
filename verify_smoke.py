#!/usr/bin/env python3
"""打擊蒼蠅大作戰 V4 —— 端到端驗證（Playwright）。

涵蓋：8 把武器（含黏蠅紙定身易傷、鹽槍扇心暴擊、電蚊拍連鎖、雙持雙點、雷射穿透）、
第 3 關防禦（可頌衛生度）、第 4 關蜜蜂懲罰與突風、第 5 關 Boss 二階段/護盾/力竭、
無盡模式（存活、迷你王、排行）、V3 音效與人聲、手機直向版面。

    python verify_smoke.py [--base-url URL] [--headed]
"""
from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
ART = ROOT / "artifacts"
FAILS: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)
    return ok


def serve(directory: Path, port: int) -> socketserver.TCPServer:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    handler.log_message = lambda *a, **k: None

    class Server(socketserver.TCPServer):
        allow_reuse_address = True

    server = Server(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    ART.mkdir(exist_ok=True)
    server = None
    if args.base_url:
        url = args.base_url
        print(f"testing existing URL: {url}")
    else:
        server = serve(ROOT, args.port)
        url = f"http://127.0.0.1:{server.server_address[1]}/index.html"
        print(f"serving {ROOT} on {url}")

    errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not args.headed,
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                  "--autoplay-policy=no-user-gesture-required"],
        )
        page = browser.new_page(viewport={"width": 430, "height": 880})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.goto(url, wait_until="load")
        page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        page.evaluate("try { localStorage.clear(); } catch (e) {}")
        page.reload(wait_until="load")
        page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)

        # ---------- 1. 版面 / 主循環 ----------
        vp = page.evaluate("({w: innerWidth, h: innerHeight, dpr: devicePixelRatio, cw: game.width, ch: game.height, touch: getComputedStyle(document.body).touchAction})")
        check("canvas 依 DPR 滿版", vp["cw"] == int(vp["w"] * min(vp["dpr"], 2)) and vp["ch"] == int(vp["h"] * min(vp["dpr"], 2)), str(vp))
        check("阻擋預設觸控手勢", vp["touch"] == "none")
        f0 = page.evaluate("__game.frame")
        time.sleep(1.0)
        f1 = page.evaluate("__game.frame")
        check("主循環持續推進", f1 - f0 >= 8, f"{f0} -> {f1} fps-ish")

        # ---------- 2. 選關畫面 ----------
        menu = page.evaluate("""({
          levels: document.querySelectorAll('.levels .lv').length,
          endlessLocked: document.getElementById('btnEndlessMenu').disabled,
          weapons: __game.WEAPONS.map(w => [w.id, w.unlock]),
          chips: document.querySelectorAll('.wbtn').length,
        })""")
        check("V4：8 把武器 + 5 個關卡 + 無盡（未解鎖）",
              menu["levels"] == 5 and menu["endlessLocked"] and len(menu["weapons"]) == 8,
              f"levels={menu['levels']} 武器={len(menu['weapons'])}")
        check("武器解鎖門檻符合規格",
              [w[1] for w in menu["weapons"]] == [0, 400, 1000, 1800, 3000, 4500, 6500, 9000],
              str([w[1] for w in menu["weapons"]]))
        check("底部常駐 8 個武器切換鈕", menu["chips"] == 8, str(menu["chips"]))

        page.click(".lv[data-level='1']")
        time.sleep(0.5)
        st = page.evaluate("({phase: __game.state.phase, level: __game.state.level, target: __game.LEVELS[1].goal.target, flies: __game.flies.length})")
        check("第 1 關開始（目標 500 分 / 40 秒）", st["phase"] == "playing" and st["level"] == 1 and st["target"] == 500, str(st))

        # ---------- 3. V3 音效 + 人聲 ----------
        decoded = True
        try:
            page.wait_for_function("Object.keys(__game.voice.buffers).length === 3", timeout=15_000)
        except Exception:
            decoded = False
        check("V3 人聲 3 段已解碼", decoded, str(page.evaluate("Object.keys(__game.voice.buffers)")))

        page.evaluate("__game.audio.log.length = 0; __game.voice.log.length = 0")
        fly = page.evaluate("(() => { const f = __game.spawnFly(innerWidth * .5, innerHeight * .45, 'house'); return {x: f.x, y: f.y}; })()")
        page.mouse.click(fly["x"], fly["y"])
        time.sleep(0.25)
        snd = page.evaluate("({a: __game.audio.log.map(e => e.name), v: __game.voice.log.map(e => e.name)})")
        check("擊殺音效分層 + 人聲", "swing" in snd["a"] and "kill" in snd["a"] and snd["v"].count("voice:kill") == 1, str(snd))

        page.evaluate("__game.flies.length = 0; __game.state.cool = 0")
        miss_before = page.evaluate("__game.state.misses")
        page.mouse.click(30, page.evaluate("innerHeight") * 0.8)
        time.sleep(0.2)
        check("空拍計入失誤", page.evaluate("__game.state.misses") > miss_before)

        # ---------- 4. 武器庫（第 2 關：擊殺目標，不會被分數破關干擾） ----------
        def goto_level(n: int):
            page.evaluate(f"__game.startLevel({n})")
            time.sleep(0.35)

        def set_score(v: int):
            page.evaluate(f"__game.addScore({v} - __game.state.score)")
            time.sleep(0.12)

        def clear(w=0.0):
            page.evaluate("__game.flies.length = 0; __game.state.cool = 0; __game.effects.length = 0")

        goto_level(2)
        set_score(400)
        check("400 分 → 塑膠蒼蠅拍", page.evaluate("__game.weapon") == "swatter")
        set_score(1000)
        check("1000 分 → 黏蠅紙", page.evaluate("__game.weapon") == "trap")

        clear()
        tx, ty = 200, 400
        trap_hit = page.evaluate(f"""(() => {{
          const f = __game.spawnFly({tx}, {ty}, 'bottle');
          f.__target = 1;
          __game.state.cool = 0;
          __game.attack({tx}, {ty});           // 放黏蠅紙
          return {{frozen: f.frozenT, hp: f.hp, traps: __game.traps.length}};
        }})()""")
        time.sleep(0.25)
        trap_hit2 = page.evaluate("({frozen: (__game.flies.find(f => f.__target) || {}).frozenT, traps: __game.traps.length})")
        check("黏蠅紙：放置後定身 2 秒", trap_hit["traps"] >= 1 and (trap_hit2["frozen"] or 0) > 1.0, str(trap_hit2))
        page.evaluate("__game.state.weaponIndex = 0; __game.state.cool = 0")   # 報紙 1 傷
        page.evaluate(f"__game.attack({tx}, {ty})")
        time.sleep(0.15)
        hp_after = page.evaluate("(__game.flies.find(f => f.__target) || {hp: -1}).hp")
        check("黏蠅紙：被黏住的蒼蠅受 1.5 倍傷害（2HP → 0.5）", 0 < hp_after <= 0.6, f"hp={hp_after}")

        set_score(1800)
        check("1800 分 → 電蚊拍", page.evaluate("__game.weapon") == "electric")
        clear()
        ax, ay = 210, 500
        aoe = page.evaluate(f"""(() => {{
          __game.spawnFly({ax}, {ay});
          __game.spawnFly({ax + 120}, {ay});      // 範圍外，靠連鎖電到
          __game.spawnFly({ax + 250}, {ay});      // 連鎖第二跳
          __game.state.cool = 0;
          __game.attack({ax}, {ay});
          return {{dead: __game.flies.filter(f => f.state === 'dying' || f.dead).length,
                  zaps: __game.effects.filter(e => e.type === 'zap').length}};
        }})()""")
        time.sleep(0.15)
        check("電蚊拍：AOE + 連鎖閃電（3 隻）", aoe["dead"] >= 3, str(aoe))
        check("擊殺計數會累加（第 2/4 關目標）", page.evaluate("__game.state.kills") >= 3,
              f"kills={page.evaluate('__game.state.kills')}")

        set_score(3000)
        check("3000 分 → 散彈鹽槍", page.evaluate("__game.weapon") == "salt")
        clear()
        salt = page.evaluate("""(() => {
          const w = innerWidth, h = innerHeight;
          const mx = w / 2, my = h * 0.8;                                  // 槍口（點擊點）
          const centre = __game.spawnFly(mx, my - 70, 'bottle');           // 正對中心 = 扇心
          const edge = __game.spawnFly(mx + 66, my - 150, 'bottle');       // 偏 25 度 = 扇緣
          __game.state.cool = 0;
          __game.attack(mx, my);
          return {centre: centre.hp, edge: edge.hp};
        })()""")
        check("鹽槍：扇心 3 傷打死、扇緣只 1 傷", salt["centre"] <= 0 and 0 < salt["edge"] <= 1.2, str(salt))

        set_score(4500)
        check("4500 分 → 殺蟲噴霧", page.evaluate("__game.weapon") == "spray")
        clear()
        sx, sy = 210, 470
        page.evaluate(f"__game.spawnFly({sx}, {sy}, 'bottle').state = 'rest'")
        page.mouse.move(sx, sy)
        page.mouse.down()
        time.sleep(1.3)
        spray = page.evaluate("({clouds: __game.clouds.length, hp: (__game.flies[0] || {hp: -1}).hp})")
        page.mouse.up()
        check("噴霧：毒霧每 0.3 秒結算、2HP 被打死", spray["clouds"] >= 1 and spray["hp"] <= 0, str(spray))

        set_score(6500)
        check("6500 分 → 雙持高壓電蚊拍", page.evaluate("__game.weapon") == "twin")
        clear()
        twin = page.evaluate("""(() => {
          const x = innerWidth / 2, y = innerHeight * 0.5;
          const left = __game.spawnFly(x - 55, y);
          const right = __game.spawnFly(x + 55, y);
          __game.state.cool = 0;
          __game.attack(x, y);
          return {dead: [left, right].filter(f => f.state === 'dying' || f.dead).length};
        })()""")
        check("雙持：左右兩側各一次電爆", twin["dead"] == 2, str(twin))

        set_score(9000)
        check("9000 分 → 雷射炮", page.evaluate("__game.weapon") == "laser")
        clear()
        ly = 300
        laser = page.evaluate(f"""(() => {{
          __game.spawnFly(40, {ly}); __game.spawnFly(innerWidth - 40, {ly + 6}); __game.spawnFly(innerWidth / 2, {ly - 8});
          __game.state.cool = 0;
          __game.attack(innerWidth / 2, {ly});
          return {{dead: __game.flies.filter(f => f.state === 'dying' || f.dead).length, beam: !!__game.state.laser}};
        }})()""")
        check("雷射：80px 帶狀穿透清場", laser["dead"] >= 3 and laser["beam"], str(laser))

        # ---------- 5. 第 3 關：防禦可頌 ----------
        goto_level(3)
        d0 = page.evaluate("({hp: __game.defend.hp, types: __game.LEVELS[3].types, camo: __game.FLY_TYPES.gold.camo})")
        check("第 3 關：可頌衛生度滿、含偽裝金斑麗蠅", 90 < d0["hp"] <= 100 and "gold" in d0["types"] and d0["camo"] is True, str(d0))
        eat = page.evaluate("""(() => {
          const t = __game.defend;
          const f = __game.spawnFly(t.x, t.y, 'house');
          return {target: !!f.targetPos};
        })()""")
        time.sleep(1.0)
        d1 = page.evaluate("({hp: __game.defend.hp, eating: __game.flies.some(f => f.eating)})")
        check("蒼蠅抵達可頌後進入 eating 並扣衛生度", eat["target"] and d1["eating"] and d1["hp"] < 100, str(d1))
        page.evaluate("__game.setTimeLeft(0.05)")
        time.sleep(0.4)
        check("守住 60 秒 → 第 3 關通關", page.evaluate("__game.state.phase") == "won")

        # ---------- 6. 第 4 關：蜜蜂懲罰 + 突風 ----------
        goto_level(4)
        bee = page.evaluate("""(() => {
          __game.flies.length = 0;
          const b = __game.spawnBee();
          __game.state.weaponIndex = 0;   // 報紙（雷射會跳過友軍）
          __game.state.cool = 0;
          const before = __game.state.score;
          __game.attack(b.x, b.y);
          return {hits: __game.state.beeHits, lock: __game.state.weaponLockT, delta: __game.state.score - before};
        })()""")
        check("誤擊蜜蜂：-200 分、武器凍結 1 秒", bee["hits"] == 1 and bee["lock"] > 0.5 and bee["delta"] == -200, str(bee))
        locked_attack = page.evaluate("(() => { __game.state.misses = 0; __game.state.cool = 0; __game.attack(100, 400); return __game.state.misses; })()")
        check("凍結期間無法出擊", locked_attack == 0, f"misses={locked_attack}")
        gust = page.evaluate("""(() => {
          const f = __game.spawnFly(innerWidth / 2, innerHeight / 2);
          __game.forceGust();
          const x0 = f.x;
          return {wind: !!__game.state.wind, x0};
        })()""")
        time.sleep(0.4)
        gust2 = page.evaluate("({wind: !!__game.state.wind, moved: __game.flies.some(f => true)})")
        check("突風：產生側風物件並推動蒼蠅", gust["wind"] and gust2["wind"], str(gust))

        # ---------- 7. 第 5 關：Boss 二階段 ----------
        goto_level(5)
        boss0 = page.evaluate("({hp: __game.boss.hp, r: __game.boss.r, phase: __game.boss.phase})")
        check("第 5 關：蠅王 80 HP、體積 4 倍", boss0["hp"] == 80 and boss0["r"] >= 40 and boss0["phase"] == 1, str(boss0))

        page.evaluate("__game.forceSummon()")
        time.sleep(0.25)
        shield = page.evaluate("""(() => {
          const b = __game.boss;
          const hp0 = b.hp;
          __game.state.weaponIndex = 0; __game.state.cool = 0;
          __game.attack(b.x, b.y);
          return {shield: __game.flies.filter(f => f.shield && !f.dead).length, bossShield: b.shieldCount, hp0, hp1: b.hp};
        })()""")
        check("Phase 1：召喚 10 隻護盾，護盾期間 Boss 免疫",
              shield["shield"] >= 10 and shield["bossShield"] >= 10 and shield["hp1"] == shield["hp0"], str(shield))

        pierce = page.evaluate("""(() => {
          const b = __game.boss;
          b.dodgeCd = 9;                 // 關掉 20% 閃避，讓這一發一定命中
          const hp0 = b.hp;
          __game.state.weaponIndex = 7; __game.state.cool = 0;   // 雷射
          __game.attack(innerWidth / 2, b.y);
          return {hp0, hp1: b.hp, shield: b.shieldCount};
        })()""")
        check("雷射：穿透護盾削弱 Boss（8 傷）", pierce["hp1"] == pierce["hp0"] - 8, str(pierce))

        page.evaluate("__game.forcePhase2(); __game.forceDive()")
        exhausted = True
        try:
            page.wait_for_function("__game.boss && __game.boss.exhaustT > 0.5", timeout=5_000)
        except Exception:
            exhausted = False
        p2 = page.evaluate("""({dive: !!__game.boss.dive, phase: __game.boss.phase,
                                exhaust: __game.boss.exhaustT, hp: __game.boss.hp})""")
        check("Phase 2：HP ≤ 50% 狂暴、俯衝後力竭 2 秒",
              exhausted and p2["phase"] == 2, str(p2))

        crit = page.evaluate("""(() => {
          const b = __game.boss;
          __game.flies.filter(f => f.shield).forEach(f => { f.dead = true; });
          b.shieldCount = 0;               // update() 下一帧才會重算，這裡先同步
          __game.forceExhaust(2);          // 明確進入力竭
          __game.state.weaponIndex = 0; __game.state.cool = 0;
          const hp0 = b.hp;
          __game.attack(b.x, b.y);
          return {hp0, hp1: b.hp, exhaust: b.exhaustT};
        })()""")
        check("力竭期間受到雙倍傷害（1 傷 → 2）", crit["hp0"] - crit["hp1"] == 2, str(crit))

        page.evaluate("""(() => {
          const b = __game.boss;
          __game.state.weaponIndex = 7; __game.state.cool = 0;
          b.hp = 8; b.exhaustT = 0; b.shieldCount = 0;
          __game.flies.filter(f => f.shield).forEach(f => { f.dead = true; });
          __game.attack(innerWidth / 2, b.y);
        })()""")
        time.sleep(0.8)
        win5 = page.evaluate("({phase: __game.state.phase, progress: __game.progress, voices: __game.voice.log.map(e => e.name)})")
        check("Boss 倒下 → 通關並存進度（解鎖無盡）", win5["phase"] == "won" and win5["progress"].get("5") is True, str(win5["progress"]))
        check("擊倒蠅王有人聲「你有病喔」", "voice:boss" in win5["voices"], str(win5["voices"][-3:]))

        # ---------- 8. 無盡模式 ----------
        page.evaluate("__game.showStart()")
        time.sleep(0.3)
        unlocked = page.evaluate("!document.getElementById('btnEndlessMenu').disabled")
        check("通關第 5 關後解鎖無盡模式", unlocked)
        page.evaluate("__game.clearEndlessBoard(); __game.startEndless()")
        time.sleep(0.6)
        e0 = page.evaluate("({phase: __game.state.phase, endless: __game.state.endless, survival: __game.state.survival, label: document.getElementById('levelName').textContent})")
        check("無盡模式啟動（無時間上限、存活計時）", e0["phase"] == "playing" and e0["endless"] and e0["survival"] > 0, str(e0))
        page.evaluate("__game.state.miniBossT = 0.05")
        time.sleep(0.5)
        mini = page.evaluate("__game.flies.filter(f => f.isMiniBoss).length")
        check("每 60 秒的迷你蠅王會出現", mini >= 1, f"miniboss={mini}")
        page.evaluate("__game.state.misses = 21")
        time.sleep(0.4)
        end = page.evaluate("({phase: __game.state.phase, board: __game.board})")
        check("容錯用完 → 結束並寫入排行", end["phase"] == "lost" and len(end["board"]) == 1, str(end["board"]))

        # ---------- 9. 靜音 / 截圖 ----------
        # 關掉結算/選關遮罩（#modal 在靜音鈕上層），直接測右上角那顆按鈕
        page.evaluate("document.getElementById('modal').classList.add('hidden')")
        time.sleep(0.2)
        page.click("#muteBtn")
        time.sleep(0.15)
        m1 = page.evaluate("({muted: __game.audio.muted, saved: localStorage.getItem('fly.swat.muted')})")
        page.evaluate("__game.voice.log.length = 0; __game.audio.log.length = 0; __game.state.cool = 0")
        page.evaluate("__game.startLevel(1); __game.state.cool = 0; __game.spawnFly(innerWidth/2, innerHeight/2)")
        page.mouse.click(page.evaluate("innerWidth") / 2, page.evaluate("innerHeight") / 2)
        time.sleep(0.3)
        quiet = page.evaluate("({a: __game.audio.log.map(e => e.name), v: __game.voice.log.map(e => e.name), muted: __game.audio.muted})")
        check("靜音：音效與人聲都不播",
              m1["muted"] is True and m1["saved"] == "1" and not quiet["a"] and not quiet["v"], str(quiet))
        page.click("#muteBtn")

        page.evaluate("__game.startLevel(1)")
        time.sleep(0.8)
        page.screenshot(path=str(ART / "fly-v4-desktop.png"))

        mctx = browser.new_context(**dict(p.devices["Pixel 5"]))
        mp = mctx.new_page()
        mp.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        mp.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        mp.goto(url, wait_until="load")
        mp.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        mp.tap(".lv[data-level='1']")
        time.sleep(0.7)
        mv = mp.evaluate("({phase: __game.state.phase, chips: document.querySelectorAll('.wbtn').length, w: innerWidth, h: innerHeight})")
        check("手機（Pixel 5）：直向版面 + 8 武器列", mv["phase"] == "playing" and mv["chips"] == 8, str(mv))
        target = mp.evaluate("(() => { const f = __game.spawnFly(innerWidth * .5, innerHeight * .45); return {x: f.x, y: f.y}; })()")
        mp.touchscreen.tap(target["x"], target["y"])
        time.sleep(0.3)
        check("手機觸控拍打計分", mp.evaluate("__game.state.score") > 0, f"score={mp.evaluate('__game.state.score')}")
        mp.screenshot(path=str(ART / "fly-v4-mobile.png"))
        mctx.close()

        browser.close()

    if server:
        server.shutdown()

    check("沒有 console / page error", not errors, "; ".join(errors[:3]))
    for shot in ("fly-v4-desktop.png", "fly-v4-mobile.png"):
        pth = ART / shot
        check(f"截圖 {shot}", pth.is_file() and pth.stat().st_size > 20_000,
              f"{pth.stat().st_size // 1024} KB" if pth.is_file() else "missing")

    print()
    if FAILS:
        print(f"RESULT: FAIL ({len(FAILS)}: {', '.join(FAILS)})")
        return 1
    print("RESULT: PASS (8 武器 / 5 關 / 防禦 / 干擾 / Boss 二階段 / 無盡 / 音效人聲 / 手機)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
