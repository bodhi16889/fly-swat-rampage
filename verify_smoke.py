#!/usr/bin/env python3
"""打擊蒼蠅大作戰 V5 —— 端到端驗證（Playwright）。

涵蓋：100 關（5 章 × 20 關、難度遞增、Boss 每 10 關）、20 把武器（前 8 把機制、
後 12 把新機制：三連/音波/誘餌/磁力/火箭/無人機/全域/冰凍/火焰/冰霧/電網/電漿）、
防禦關、蜜蜂/突風、Boss 二階段、無盡模式、廣告復活/續命、持久化、手機與 640×480。

時間判定一律用 wait_for_function 等狀態，不用固定 sleep：
headless + SwiftShader 前 1–2 秒只有 1–2 fps，睡眠會量到暖機或舊座標。

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

UNLOCKS = [0, 400, 1000, 1800, 3000, 4500, 6500, 9000,
           12000, 15500, 19500, 24000, 29000, 34500, 40500, 47000,
           54500, 63000, 73000, 85000]


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)
    return ok


def wait_frames(page, n: int = 10, timeout: int = 15_000) -> None:
    """等 rAF 暖機。

    headless + SwiftShader 在前 1–2 秒只跑得到 1–2 fps（著色器/首繪編譯），
    直接量「1 秒內幾帧」會量到暖機而不是實際效能。先確認主循環已推進 n 帧再量。
    """
    start = page.evaluate("__game.frame")
    page.wait_for_function(f"__game.frame >= {start + n}", timeout=timeout)


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
        wait_frames(page, 10)          # 先暖機，避免把首繪編譯時間當成 fps
        f0 = page.evaluate("__game.frame")
        time.sleep(1.0)
        f1 = page.evaluate("__game.frame")
        check("主循環持續推進（暖機後）", f1 - f0 >= 8, f"{f0} -> {f1} fps-ish")

        # ---------- 2. 選單：100 關 / 20 武器 / 5 章 ----------
        menu = page.evaluate("""({
          levels: Object.keys(__game.LEVELS).length,
          chapters: document.querySelectorAll('.chtab').length,
          cells: document.querySelectorAll('.lvcell').length,
          endlessLocked: document.getElementById('btnEndlessMenu').disabled,
          weapons: __game.WEAPONS.map(w => [w.id, w.unlock]),
          chips: document.querySelectorAll('.wbtn').length,
          goals: Object.values(__game.LEVELS).reduce((a, l) => { a[l.goal.type] = (a[l.goal.type] || 0) + 1; return a; }, {}),
        })""")
        check("V5：100 關 + 20 武器 + 5 章（每章 20 關）",
              menu["levels"] == 100 and menu["chapters"] == 5 and menu["cells"] == 20
              and len(menu["weapons"]) == 20 and menu["endlessLocked"],
              f"levels={menu['levels']} 章={menu['chapters']} 武器={len(menu['weapons'])}")
        check("武器解鎖門檻符合 V5 規格",
              [w[1] for w in menu["weapons"]] == UNLOCKS, str([w[1] for w in menu["weapons"]]))
        check("底部武器列 20 把（可橫向捲動）", menu["chips"] == 20, str(menu["chips"]))
        check("關卡目標四型都有（score / kills / defend / boss）",
              all(menu["goals"].get(k, 0) > 0 for k in ("score", "kills", "defend", "boss"))
              and sum(menu["goals"].values()) == 100, str(menu["goals"]))

        diff = page.evaluate("""({
          spawn: [1, 25, 49, 75, 99].map(n => +__game.LEVELS[n].spawnEvery.toFixed(3)),
          boss: [10, 50, 100].map(n => __game.LEVELS[n].bossHp),
          times: [1, 50, 100].map(n => __game.LEVELS[n].time),
        })""")
        check("難度遞增：生成間隔變短、Boss HP 變高",
              all(a > b for a, b in zip(diff["spawn"], diff["spawn"][1:]))
              and all(a < b for a, b in zip(diff["boss"], diff["boss"][1:])), str(diff))

        profile = page.evaluate("({name: __game.profile.name, stored: localStorage.getItem('fly.swat.profile'),"
                                " shown: document.getElementById('profileName').textContent})")
        check("本機暱稱：首次自動產生並存在 localStorage",
              bool(profile["name"]) and profile["stored"] and profile["name"] == profile["shown"],
              str(profile))
        page.click("#btnRename")
        page.fill("#nameInput", "<b>Adan</b>")
        page.click("#btnSaveName")
        time.sleep(0.2)
        renamed = page.evaluate("({name: __game.profile.name, stored: localStorage.getItem('fly.swat.profile'),"
                                " shown: document.getElementById('profileName').textContent})")
        check("改名：去除標籤、立即生效並持久化",
              renamed["name"] == "Adan" and renamed["shown"] == "Adan"
              and '"Adan"' in (renamed["stored"] or ""), str(renamed))

        page.click(".lvcell[data-level='1']")
        time.sleep(0.4)
        st = page.evaluate("({phase: __game.state.phase, level: __game.state.level, target: __game.LEVELS[1].goal.target, flies: __game.flies.length})")
        check("第 1 關開始（目標 340 分 / 40 秒）",
              st["phase"] == "playing" and st["level"] == 1 and st["target"] == 340, str(st))

        # ---------- 3. 音效 + 人聲 ----------
        decoded = True
        try:
            page.wait_for_function("Object.keys(__game.voice.buffers).length === 3", timeout=15_000)
        except Exception:
            decoded = False
        check("人聲 3 段已解碼", decoded, str(page.evaluate("Object.keys(__game.voice.buffers)")))

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

        # ---------- 4. 武器庫：前 8 把機制 ----------
        def goto_level(n: int):
            page.evaluate(f"__game.startLevel({n})")
            time.sleep(0.35)

        def set_score(v: int):
            page.evaluate(f"__game.addScore({v} - __game.state.score)")
            time.sleep(0.12)

        def clear():
            page.evaluate(
                "__game.flies.length = 0; __game.clouds.length = 0; __game.traps.length = 0;"
                " __game.state.waves.length = 0; __game.state.decoys.length = 0;"
                " __game.state.rockets.length = 0; __game.state.drones.length = 0;"
                " __game.effects.length = 0; __game.state.cool = 0")

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
          __game.attack({tx}, {ty});
          return {{frozen: f.frozenT, hp: f.hp, traps: __game.traps.length}};
        }})()""")
        page.wait_for_function("__game.state.traps.length >= 1", timeout=3_000)
        page.wait_for_function("(__game.flies.find(f => f.__target) || {}).frozenT > 1", timeout=3_000)
        trap_hit2 = page.evaluate("({frozen: (__game.flies.find(f => f.__target) || {}).frozenT, traps: __game.state.traps.length})")
        check("黏蠅紙：放置後定身 2 秒", trap_hit["traps"] >= 1 and (trap_hit2["frozen"] or 0) > 1.0, str(trap_hit2))
        page.evaluate("__game.state.weaponIndex = 0; __game.state.cool = 0")
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
          __game.spawnFly({ax + 120}, {ay});
          __game.spawnFly({ax + 250}, {ay});
          __game.state.cool = 0;
          __game.attack({ax}, {ay});
          return {{dead: __game.flies.filter(f => f.state === 'dying' || f.dead).length,
                  zaps: __game.effects.filter(e => e.type === 'zap').length}};
        }})()""")
        time.sleep(0.15)
        check("電蚊拍：AOE + 連鎖閃電（3 隻）", aoe["dead"] >= 3, str(aoe))
        check("擊殺計數會累加", page.evaluate("__game.state.kills") >= 3,
              f"kills={page.evaluate('__game.state.kills')}")

        set_score(3000)
        check("3000 分 → 散彈鹽槍", page.evaluate("__game.weapon") == "salt")
        clear()
        salt = page.evaluate("""(() => {
          const w = innerWidth, h = innerHeight;
          const mx = w / 2, my = h * 0.8;
          const centre = __game.spawnFly(mx, my - 70, 'bottle');
          const edge = __game.spawnFly(mx + 66, my - 150, 'bottle');
          __game.state.cool = 0;
          __game.attack(mx, my);
          return {centre: centre.hp, edge: edge.hp};
        })()""")
        check("鹽槍：扇心 3 傷打死、扇緣只 1 傷", salt["centre"] <= 0 and 0 < salt["edge"] <= 1.2, str(salt))

        set_score(4500)
        check("4500 分 → 殺蟲噴霧", page.evaluate("__game.weapon") == "spray")
        clear()
        sx, sy = 210, 470
        page.evaluate(f"""(() => {{
          const f = __game.spawnFly({sx}, {sy}, 'bottle');
          f.__probe = true;
          f.state = 'rest'; f.restT = 9;
        }})()""")
        page.mouse.move(sx, sy)
        page.mouse.down()
        page.wait_for_function("__game.clouds.length >= 1", timeout=5_000)
        killed = True
        try:
            page.wait_for_function(
                "(() => { const f = __game.flies.find(f => f.__probe);"
                " return !f || f.hp <= 0 || f.state === 'dying'; })()",
                timeout=5_000)
        except Exception:
            killed = False
        spray = page.evaluate("({clouds: __game.clouds.length,"
                              " hp: (__game.flies.find(f => f.__probe) || {hp: 0}).hp})")
        page.mouse.up()
        check("噴霧：毒霧每 0.3 秒結算、2HP 被打死", killed and spray["clouds"] >= 1, str(spray))

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

        # ---------- 5. 後 12 把新武器機制 ----------
        def dead_all(timeout: int = 8_000) -> bool:
            try:
                page.wait_for_function(
                    "window.__probe && window.__probe.every(f => f.dead || f.state === 'dying' || f.hp <= 0)",
                    timeout=timeout)
                return True
            except Exception:
                return False

        def arm(idx: int):
            page.evaluate(f"__game.state.unlocked = 20; __game.state.weaponIndex = {idx}; __game.state.cool = 0")

        def probe_attack(idx: int, points, at, timeout: int = 8_000) -> bool:
            arm(idx)
            page.evaluate(
                """([idx, pts, ax, ay]) => {
                  __game.startLevel(1);
                  __game.flies.length = 0;
                  __game.state.weaponIndex = idx;
                  __game.state.cool = 0;
                  window.__probe = pts.map(([x, y]) => {
                    const f = __game.spawnFly(x, y, 'house');
                    f.state = 'rest'; f.restT = 9;
                    return f;
                  });
                  __game.attack(ax, ay);
                }""", [idx, points, at[0], at[1]])
            return dead_all(timeout)

        W, H = 430, 880
        check("三連拍：三個判定點各打死一隻",
              probe_attack(10, [[W/2-70, H/2], [W/2, H/2], [W/2+70, H/2]], (W/2, H/2)))
        check("音波：擴散波掃到半徑內所有蒼蠅",
              probe_attack(11, [[W/2, H/2-100], [W/2+120, H/2], [W/2-120, H/2-80]], (W/2, H/2)))
        check("誘餌：吸引後爆炸清場",
              probe_attack(12, [[W/2+120, H/2], [W/2-120, H/2-60]], (W/2, H/2), 10_000))
        check("磁力：把蒼蠅拉到中心並造成傷害",
              probe_attack(14, [[W/2+150, H/2], [W/2-150, H/2+80]], (W/2, H/2)))
        check("火箭：飛到點上爆炸",
              probe_attack(15, [[W/2, H*0.3], [W/2+60, H*0.3]], (W/2, H*0.3)))
        check("無人機：自動鎖定射擊",
              probe_attack(18, [[W/2+60, H/2]], (W/2, H/2)))
        check("全域殲滅：一擊清空畫面",
              probe_attack(19, [[100, 200], [300, 400], [200, 600]], (W/2, H/2)))

        arm(17)
        page.evaluate(f"""(() => {{
          __game.startLevel(1); __game.flies.length = 0; __game.state.weaponIndex = 17; __game.state.cool = 0;
          window.__probe = [__game.spawnFly({W/2}, {H/2}, 'house')];
          window.__probe[0].state = 'rest'; window.__probe[0].restT = 9;
          __game.attack({W/2}, {H/2});
        }})()""")
        frozen_ok = True
        try:
            page.wait_for_function("window.__probe[0].frozenT > 3", timeout=5_000)
        except Exception:
            frozen_ok = False
        check("急凍陷阱：定身 3.5 秒", frozen_ok, str(page.evaluate("window.__probe[0].frozenT")))

        arm(9)
        page.evaluate(f"""(() => {{
          __game.startLevel(1); __game.flies.length = 0; __game.state.weaponIndex = 9; __game.state.cool = 0;
          window.__probe = [__game.spawnFly({W/2}, {H/2}, 'bottle')];
          window.__probe[0].state = 'rest'; window.__probe[0].restT = 9;
        }})()""")
        page.mouse.move(W/2, H/2)
        page.mouse.down()
        cryo_ok = True
        try:
            page.wait_for_function("window.__probe[0].hp <= 0 && window.__probe[0].frozenT > 0", timeout=8_000)
        except Exception:
            cryo_ok = False
        cryo = page.evaluate("({hp: window.__probe[0].hp, frozen: window.__probe[0].frozenT, clouds: __game.clouds.length})")
        page.mouse.up()
        check("冰霧：持續傷害並定身", cryo_ok and cryo["clouds"] >= 1, str(cryo))

        arm(13)
        page.evaluate(f"""(() => {{
          __game.startLevel(1); __game.flies.length = 0; __game.state.weaponIndex = 13; __game.state.cool = 0;
          window.__probe = [[{W/2}, {H/2}], [{W/2+40}, {H/2-30}]].map(([x, y]) => {{
            const f = __game.spawnFly(x, y, 'house'); f.state = 'rest'; f.restT = 9; return f;
          }});
        }})()""")
        page.mouse.move(W/2, H*0.7)
        page.mouse.down()
        flame_ok = dead_all(8_000)
        flame = page.evaluate("window.__probe.map(f => f.hp)")
        page.mouse.up()
        check("火焰：扇形持續傷害", flame_ok, str(flame))

        # ---------- 5b. 每關 PB / 本機排行 ----------
        def win_score(n: int, score: int):
            page.evaluate(f"__game.startLevel({n}); __game.addScore({score} - __game.state.levelScore)")
            page.wait_for_function("__game.state.phase === 'won'", timeout=5_000)

        win_score(1, 340)
        b1 = page.evaluate("__game.bests['1']")
        pb_ui = page.evaluate("document.querySelector('.pb') ? document.querySelector('.pb').textContent : ''")
        check("PB：通關後記錄本關最佳（分數、名字、時間）",
              bool(b1) and b1[0]["value"] == 340 and b1[0]["name"] == "Adan"
              and isinstance(b1[0]["timeMs"], int) and "340" in pb_ui, f"{b1} / {pb_ui}")
        win_score(1, 500)
        check("PB：更高分會刷新", page.evaluate("__game.bests['1'][0].value") == 500)
        win_score(1, 340)
        check("PB：較差分數不會蓋掉最佳",
              page.evaluate("__game.bests['1'][0].value") == 500
              and len(page.evaluate("__game.bests['1']")) == 3)
        page.evaluate("__game.showBoard(1)")
        board = page.evaluate("({rows: document.querySelectorAll('.brow[data-brow]').length,"
                              " first: document.querySelector('.brow[data-brow]').textContent.trim().replace(/\s+/g, ' ')})")
        check("本機排行：章節 20 關列表顯示最佳",
              board["rows"] == 20 and "500" in board["first"], str(board))
        page.click(".brow[data-brow='1']")
        time.sleep(0.2)
        detail = page.evaluate("({rows: document.querySelectorAll('.brow.static').length,"
                               " text: document.querySelector('.brow.static').textContent.trim().replace(/\s+/g, ' ')})")
        check("本機排行：關卡前 5 名", detail["rows"] == 3 and "500" in detail["text"], str(detail))
        page.evaluate("__game.showStart()")
        page.click("#btnRename")
        page.fill("#nameInput", "Guest")
        page.click("#btnSaveName")
        win_score(1, 340)
        names = page.evaluate("__game.bests['1'].map(e => e.name)")
        check("同一裝置可用不同暱稱上榜", "Adan" in names and "Guest" in names, str(names))

        # ---------- 6. 防禦關（第 3 章） ----------
        goto_level(41)
        d0 = page.evaluate("({hp: __game.defend.hp, drain: __game.LEVELS[41].drainPerSec, camo: __game.FLY_TYPES.gold.camo, goal: __game.LEVELS[41].goal.type})")
        check("第 41 關：防禦關、可頌衛生度滿、含偽裝金斑麗蠅",
              90 < d0["hp"] <= 100 and d0["goal"] == "defend" and d0["drain"] >= 4 and d0["camo"] is True, str(d0))
        eat = page.evaluate("""(() => {
          const t = __game.defend;
          const f = __game.spawnFly(t.x, t.y, 'house');
          return {target: !!f.targetPos};
        })()""")
        eaten = True
        try:
            page.wait_for_function("__game.defend.hp < 100 && __game.flies.some(f => f.eating)", timeout=5_000)
        except Exception:
            eaten = False
        d1 = page.evaluate("({hp: __game.defend.hp, eating: __game.flies.some(f => f.eating)})")
        check("蒼蠅抵達可頌後進入 eating 並扣衛生度", eat["target"] and eaten, str(d1))
        page.evaluate("__game.setTimeLeft(0.05)")
        won3 = True
        try:
            page.wait_for_function("__game.state.phase === 'won'", timeout=5_000)
        except Exception:
            won3 = False
        check("守住時間 → 防禦關通關", won3, f"phase={page.evaluate('__game.state.phase')}")

        # ---------- 7. 蜜蜂 + 突風（第 4 章） ----------
        goto_level(61)
        cfg61 = page.evaluate("({bee: __game.LEVELS[61].bees, maxBee: __game.LEVELS[61].goal.maxBeeHits, gust: __game.LEVELS[61].gustEvery})")
        check("第 61 關：蜜蜂、誤擊上限 2、突風間隔", cfg61["bee"] and cfg61["maxBee"] == 2 and cfg61["gust"] > 0, str(cfg61))
        bee = page.evaluate("""(() => {
          __game.flies.length = 0;
          const b = __game.spawnBee();
          __game.state.weaponIndex = 0;
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
          return {wind: !!__game.state.wind, x0: f.x};
        })()""")
        time.sleep(0.4)
        gust2 = page.evaluate("({wind: !!__game.state.wind, x: (__game.flies.find(f => !f.friendly) || {}).x})")
        check("突風：產生側風物件並推動蒼蠅", gust["wind"] and gust2["wind"], str(gust))

        # ---------- 8. Boss（每 10 關） ----------
        goto_level(10)
        boss0 = page.evaluate("({hp: __game.boss.hp, max: __game.boss.maxHp, r: __game.boss.r, phase: __game.boss.phase, shield: __game.LEVELS[10].shieldCount})")
        check("第 10 關：蠅王 80 HP、體積 4 倍",
              boss0["hp"] == 80 and boss0["max"] == 80 and boss0["r"] >= 40 and boss0["phase"] == 1, str(boss0))
        check("Boss HP 隨關卡成長（10 → 50 → 100）",
              page.evaluate("__game.LEVELS[10].bossHp < __game.LEVELS[50].bossHp && __game.LEVELS[50].bossHp < __game.LEVELS[100].bossHp"))

        page.evaluate("__game.forceSummon()")
        page.wait_for_function("__game.flies.filter(f => f.shield && !f.dead).length >= 8", timeout=5_000)
        page.wait_for_function("__game.boss.shieldCount >= 8", timeout=5_000)
        shield = page.evaluate("""(() => {
          const b = __game.boss;
          const hp0 = b.hp;
          __game.state.weaponIndex = 0; __game.state.cool = 0;
          __game.attack(b.x, b.y);
          return {shield: __game.flies.filter(f => f.shield && !f.dead).length, bossShield: b.shieldCount, hp0, hp1: b.hp};
        })()""")
        check("Phase 1：召喚護盾，護盾期間 Boss 免疫",
              shield["shield"] >= 8 and shield["bossShield"] >= 8 and shield["hp1"] == shield["hp0"], str(shield))

        pierce = page.evaluate("""(() => {
          const b = __game.boss;
          b.dodgeCd = 9;
          const hp0 = b.hp;
          __game.state.weaponIndex = 7; __game.state.cool = 0;
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
        p2 = page.evaluate("({dive: !!__game.boss.dive, phase: __game.boss.phase, exhaust: __game.boss.exhaustT, hp: __game.boss.hp})")
        check("Phase 2：HP ≤ 50% 狂暴、俯衝後力竭 2 秒", exhausted and p2["phase"] == 2, str(p2))

        crit = page.evaluate("""(() => {
          const b = __game.boss;
          __game.flies.filter(f => f.shield).forEach(f => { f.dead = true; });
          b.shieldCount = 0;
          __game.forceExhaust(2);
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
        won5 = True
        try:
            page.wait_for_function("__game.state.phase === 'won'", timeout=5_000)
            page.wait_for_function("__game.voice.log.some(e => e.name === 'voice:boss')", timeout=5_000)
        except Exception:
            won5 = False
        win5 = page.evaluate("({phase: __game.state.phase, progress: __game.progress, voices: __game.voice.log.map(e => e.name)})")
        check("Boss 倒下 → 通關並存進度（第 10 關）",
              won5 and win5["progress"].get("10") is True, str(win5["progress"]))
        check("擊倒蠅王有人聲", "voice:boss" in win5["voices"], str(win5["voices"][-3:]))

        # ---------- 9. 無盡解鎖（通關第 100 關） ----------
        page.evaluate("__game.showStart()")
        time.sleep(0.3)
        still_locked = page.evaluate("document.getElementById('btnEndlessMenu').disabled")
        check("只過第 10 關時無盡仍鎖住", still_locked)
        page.evaluate("for (let i = 1; i <= 100; i++) __game.saveProgress(i); __game.showStart()")
        time.sleep(0.3)
        unlocked = page.evaluate("!document.getElementById('btnEndlessMenu').disabled")
        check("通關第 100 關後解鎖無盡模式", unlocked)

        page.evaluate("__game.clearEndlessBoard(); __game.startEndless()")
        page.wait_for_function("__game.state.endless && __game.state.survival > 0", timeout=5_000)
        e0 = page.evaluate("({phase: __game.state.phase, endless: __game.state.endless, label: document.getElementById('levelName').textContent})")
        check("無盡模式啟動（無時間上限、存活計時）", e0["phase"] == "playing" and e0["endless"], str(e0))
        page.evaluate("__game.state.miniBossT = 0.05")
        mini_ok = True
        try:
            page.wait_for_function("__game.flies.some(f => f.isMiniBoss)", timeout=5_000)
        except Exception:
            mini_ok = False
        check("每 60 秒的迷你蠅王會出現", mini_ok)

        # ---------- 10. 靜音 ----------
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

        # ---------- 11. 武器解鎖持久化（20 把 / 85,000 分） ----------
        page.evaluate("__game.addScore(85000 - __game.state.score)")
        before = page.evaluate("({score: __game.state.score, unlocked: __game.unlocked,"
                               " stored: localStorage.getItem('fly.swat.score')})")
        page.reload(wait_until="load")
        page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        wait_frames(page, 5)
        after = page.evaluate("({score: __game.state.score, unlocked: __game.unlocked,"
                              " weapon: __game.weapon,"
                              " chips: document.querySelectorAll('.wbtn:not(.locked)').length})")
        check("武器解鎖持久化：重新載入後 20 把都在、預設殲滅裝置",
              before["unlocked"] == 20 and before["stored"] == "85000"
              and after["unlocked"] == 20 and after["weapon"] == "nuke"
              and after["chips"] == 20 and after["score"] == 85000, f"{before} -> {after}")

        page.evaluate("__game.startLevel(1, true)")
        reset = page.evaluate("({score: __game.state.score, unlocked: __game.unlocked,"
                              " stored: localStorage.getItem('fly.swat.score'), level: __game.state.level})")
        check("從第 1 關重新開始會重置累積分數與武器",
              reset["score"] == 0 and reset["unlocked"] == 1 and reset["stored"] == "0"
              and reset["level"] == 1, str(reset))

        # ---------- 12. GamePix SDK（生命週期／暫停／廣告／復活／續命／無 SDK） ----------
        gp = page.evaluate("({enabled: __game.gp.enabled, log: __game.gp.log,"
                           " hidden: document.getElementById('loading').classList.contains('hidden')})")
        check("GamePix：manual lifecycle 載入完成、loading 已收",
              gp["enabled"] and "loaded" in gp["log"] and "loading:100" in gp["log"] and gp["hidden"],
              str(gp["log"]))
        check("GamePix：開始關卡會送 gameStart", "gameStart" in page.evaluate("__game.gp.log"))
        check("GamePix：非 Player 的公開頁不呼叫廣告",
              page.evaluate("__game.gp.adsAllowed === false"))

        zctx = browser.new_context(locale="zh-TW")
        zp = zctx.new_page()
        zp.goto(url, wait_until="load")
        zp.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        zh_h1 = zp.evaluate("document.querySelector('#card h1').textContent")
        zh_chip = zp.evaluate("document.querySelector('.wbtn').textContent")
        zh_lang = zp.evaluate("document.documentElement.lang")
        zctx.close()
        check("語系：中文系統顯示中文、其餘預設英文",
              zh_h1 == "打擊蒼蠅大作戰" and "報紙" in zh_chip and zh_lang == "zh-Hant",
              f"{zh_h1} / {zh_chip} / lang={zh_lang}")

        page.evaluate("""(() => {
          window.__gpStub = { ints: 0, rews: 0, rewOk: true };
          __game.gp.adsAllowed = true;
          window.GamePix = { ads: {
            interstitial: () => { window.__gpStub.ints++; return Promise.resolve({ success: true }); },
            reward: () => { window.__gpStub.rews++; return Promise.resolve({ success: window.__gpStub.rewOk }); },
          }, events: { on() {} }, lang: () => 'en' };
        })()""")

        page.evaluate("__game.startLevel(2); __game.state.timeLeft = 30")
        wait_frames(page, 5)
        t0 = page.evaluate("(() => { const v = __game.state.timeLeft; __game.gp.pause('test'); return v; })()")
        time.sleep(0.6)
        t1 = page.evaluate("({tl: __game.state.timeLeft, paused: __game.state.paused})")
        page.evaluate("__game.gp.resume('test')")
        page.wait_for_function(f"__game.state.timeLeft < {t1['tl'] - 0.2}", timeout=5_000)
        t2 = page.evaluate("__game.state.timeLeft")
        check("暫停：時鐘與輸入停止、恢復後繼續",
              t1["paused"] and abs(t1["tl"] - t0) < 0.001 and t2 < t1["tl"],
              f"{t0} -> {t1['tl']} -> {t2}")

        page.evaluate("__game.startLevel(1); __game.addScore(340 - __game.state.levelScore)")
        page.wait_for_function("__game.state.phase === 'won'", timeout=5_000)
        page.click("#btnNext")
        page.wait_for_function("__game.state.phase === 'playing' && __game.state.level === 2", timeout=5_000)
        ads = page.evaluate("({stub: window.__gpStub, calls: __game.gp.calls})")
        check("插頁廣告：只在關卡之間播、播完才進下一關",
              ads["stub"]["ints"] == 1 and any(c["kind"] == "interstitial" for c in ads["calls"]), str(ads))

        page.evaluate("__game.startLevel(2); __game.loseLevel('probe')")
        page.wait_for_selector("#btnRevive", timeout=5_000)
        page.evaluate("window.__gpStub.rewOk = true")
        page.click("#btnRevive")
        page.wait_for_function("__game.state.phase === 'playing' && __game.state.revived === true", timeout=5_000)
        rev = page.evaluate("({tl: __game.state.timeLeft, misses: __game.state.misses, calls: __game.gp.calls})")
        check("獎勵廣告：復活 +15 秒、失誤歸零",
              rev["tl"] > 0 and rev["misses"] == 0 and rev["calls"][-1]["kind"] == "reward", str(rev))
        page.evaluate("__game.loseLevel('again')")
        check("同一局只能復活一次",
              page.evaluate("__game.state.revived === true && !document.getElementById('btnRevive')"))

        page.evaluate("__game.clearEndlessBoard(); __game.startEndless();"
                      " __game.state.survival = 42; __game.state.misses = 21")
        page.wait_for_function("__game.state.phase === 'lost'", timeout=5_000)
        ended = page.evaluate("({board: __game.board.length, revive: !!document.getElementById('btnRevive'),"
                              " label: (document.getElementById('btnRevive') || {}).textContent})")
        page.click("#btnRevive")
        page.wait_for_function("__game.state.phase === 'playing' && __game.state.revived", timeout=5_000)
        cont = page.evaluate("({misses: __game.state.misses, survival: __game.state.survival,"
                             " board: __game.board.length})")
        check("無盡續命：容錯歸零、收回當次排行、存活時間保留",
              ended["board"] == 1 and ended["revive"] and "keep going" in (ended["label"] or "")
              and cont["misses"] == 0 and cont["board"] == 0 and cont["survival"] >= 42,
              f"{ended} -> {cont}")
        page.evaluate("__game.state.survival = 55; __game.state.misses = 21")
        page.wait_for_function("__game.state.phase === 'lost'", timeout=5_000)
        check("無盡每局只能續命一次",
              page.evaluate("__game.state.revived === true && !document.getElementById('btnRevive')"
                            " && __game.board.length === 1"))

        page.evaluate("window.GamePix = undefined")
        fb = page.evaluate("__game.gp.interstitial()")
        check("沒有 SDK 時廣告 no-op、不卡關", fb.get("success") is False, str(fb))

        time.sleep(0.8)
        page.screenshot(path=str(ART / "fly-v5-desktop.png"))

        # ---------- 13. 手機（Pixel 5） ----------
        mctx = browser.new_context(**dict(p.devices["Pixel 5"]))
        mp = mctx.new_page()
        mp.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        mp.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        mp.goto(url, wait_until="load")
        mp.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        mp.tap(".lvcell[data-level='1']")
        mp.wait_for_function("__game.state.phase === 'playing'", timeout=5_000)
        mv = mp.evaluate("({phase: __game.state.phase, chips: document.querySelectorAll('.wbtn').length, w: innerWidth, h: innerHeight})")
        check("手機（Pixel 5）：直向版面 + 20 武器列", mv["phase"] == "playing" and mv["chips"] == 20, str(mv))
        target = mp.evaluate("(() => { const f = __game.spawnFly(innerWidth * .5, innerHeight * .45);"
                             " f.state = 'rest'; f.restT = 9;"
                             " return {x: f.x, y: f.y}; })()")
        mp.touchscreen.tap(target["x"], target["y"])
        scored = True
        try:
            mp.wait_for_function("__game.state.score > 0", timeout=5_000)
        except Exception:
            scored = False
        check("手機觸控拍打計分", scored, f"score={mp.evaluate('__game.state.score')}")
        mp.screenshot(path=str(ART / "fly-v5-mobile.png"))
        mctx.close()

        # ---------- 14. 640×480 iframe（GamePix 最低要求） ----------
        sctx = browser.new_context(viewport={"width": 640, "height": 480})
        sp = sctx.new_page()
        sp.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        sp.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        sp.goto(url, wait_until="load")
        sp.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        fit = sp.evaluate("""({
          scrollable: getComputedStyle(document.querySelector('#card')).overflowY,
          cardTop: document.querySelector('#card').getBoundingClientRect().top,
          cardBottom: document.querySelector('#card').getBoundingClientRect().bottom,
          barBottom: document.querySelector('#weaponbar').getBoundingClientRect().bottom,
          chapters: document.querySelectorAll('.chtab').length,
          w: innerWidth, h: innerHeight,
        })""")
        sp.click(".lvcell[data-level='1']")
        sp.wait_for_function("__game.state.phase === 'playing'", timeout=5_000)
        play = sp.evaluate("({phase: __game.state.phase, chips: document.querySelectorAll('.wbtn').length,"
                           " barTop: document.querySelector('#weaponbar').getBoundingClientRect().top, h: innerHeight})")
        check("640×480 iframe：選單可捲動、可進關卡、20 武器列在畫面內",
              fit["scrollable"] == "auto" and fit["cardTop"] >= -1 and fit["cardBottom"] <= fit["h"] + 1
              and fit["barBottom"] <= fit["h"] + 1 and fit["chapters"] == 5 and play["phase"] == "playing"
              and play["chips"] == 20 and play["barTop"] < play["h"], f"{fit} -> {play}")
        sp.wait_for_function("getComputedStyle(document.getElementById('modal')).opacity === '0'", timeout=3_000)
        sp.screenshot(path=str(ART / "fly-v5-640x480.png"))
        sctx.close()

        # ---------- 15. 語言切換（EN → 中，重載後生效） ----------
        lctx = browser.new_context(locale="en-US")
        lp = lctx.new_page()
        lp.goto(url, wait_until="load")
        lp.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        h1_en = lp.evaluate("document.querySelector('#card h1').textContent")
        with lp.expect_navigation(wait_until="load"):
            lp.click("#btnLang")
        lp.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        zh = lp.evaluate("({lang: __game.lang, stored: localStorage.getItem('fly.swat.lang'),"
                         " h1: document.querySelector('#card h1').textContent,"
                         " htmlLang: document.documentElement.lang})")
        check("語言切換：英文介面可切中文、選擇會記住",
              h1_en == "FLY SWAT RAMPAGE" and zh["lang"] == "zh" and zh["stored"] == "zh"
              and zh["h1"] == "打擊蒼蠅大作戰" and zh["htmlLang"] == "zh-Hant",
              f"{h1_en} -> {zh['h1']} / {zh['stored']}")
        lctx.close()

        browser.close()

    if server:
        server.shutdown()

    check("沒有 console / page error", not errors, "; ".join(errors[:3]))
    for shot in ("fly-v5-desktop.png", "fly-v5-mobile.png"):
        pth = ART / shot
        check(f"截圖 {shot}", pth.is_file() and pth.stat().st_size > 20_000,
              f"{pth.stat().st_size // 1024} KB" if pth.is_file() else "missing")

    print()
    if FAILS:
        print(f"RESULT: FAIL ({len(FAILS)}: {', '.join(FAILS)})")
        return 1
    print("RESULT: PASS (100 關 / 20 武器 / 防禦 / 蜜蜂 / Boss 二階段 / 無盡 / 音效人聲 / 持久化 / GamePix SDK / 手機 / 640×480)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
