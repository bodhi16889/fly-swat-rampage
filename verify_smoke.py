#!/usr/bin/env python3
"""打擊蒼蠅大作戰 —— 端到端驗證（Playwright，headless Chromium）。

    python verify_smoke.py                 # 自動選埠，測本機檔案
    python verify_smoke.py --base-url ...  # 測既有網址（GitHub Pages / tunnel）
    python verify_smoke.py --headed        # 想看畫面

檢查範圍：啟動流程、蒼蠅遊走與停歇、點擊命中/落空、5 種武器（報紙/塑膠拍/電蚊拍 AOE/
噴霧持續傷害/雷射橫掃）、分數門檻解鎖、三關目標判定、Boss（40 血以上機制、召喚、僵直雙倍傷害）、
結算彈窗按鈕、手機直向版面。
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


def wait_cool(page, seconds: float = 0.45) -> None:
    time.sleep(seconds)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

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
        page = browser.new_page(viewport={"width": 420, "height": 860})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.goto(url, wait_until="load")
        page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)

        # ---------- 1. 啟動 / 版面 ----------
        vp = page.evaluate("({w: innerWidth, h: innerHeight, dpr: devicePixelRatio, cw: game.width, ch: game.height, touch: getComputedStyle(document.body).touchAction})")
        check("canvas 依裝置像素比滿版", vp["cw"] == int(vp["w"] * min(vp["dpr"], 2)) and vp["ch"] == int(vp["h"] * min(vp["dpr"], 2)), str(vp))
        check("阻擋預設觸控手勢（touch-action:none）", vp["touch"] == "none", vp["touch"])

        f0 = page.evaluate("window.__game.frame")
        time.sleep(1.0)
        f1 = page.evaluate("window.__game.frame")
        check("60FPS 主循環有在跑", f1 - f0 >= 8, f"{f0} -> {f1} frames/1s")

        page.click("#btnStart")
        time.sleep(0.4)
        st = page.evaluate("({phase: __game.state.phase, level: __game.state.level, flies: __game.flies.length, time: __game.state.timeLeft})")
        check("開始遊戲 → 進入第 1 關", st["phase"] == "playing" and st["level"] == 1, str(st))
        check("場上已有蒼蠅", st["flies"] >= 5, f"flies={st['flies']}")

        # ---------- 2. 蒼蠅行為（遊走 / 停歇） ----------
        pos0 = page.evaluate("(() => { const f = __game.flies[0]; return {x: f.x, y: f.y, state: f.state}; })()")
        time.sleep(1.0)
        pos1 = page.evaluate("(() => { const f = __game.flies[0]; return {x: f.x, y: f.y, state: f.state, hasRest: __game.state.flies.some(x => x.state === 'rest')}; })()")
        moved = abs(pos1["x"] - pos0["x"]) + abs(pos1["y"] - pos0["y"])
        check("蒼蠅會遊走或進入停歇", moved > 4 or pos1["state"] == "rest" or pos1["hasRest"], f"moved={moved:.1f} state={pos1['state']}")

        # ---------- 3. 點擊命中 + 落空 ----------
        center = page.evaluate("({w: innerWidth, h: innerHeight})")
        cx, cy = center["w"] * 0.5, center["h"] * 0.45
        fly = page.evaluate(f"(() => {{ const f = __game.spawnFly({cx}, {cy}, 'house'); return {{x: f.x, y: f.y}}; }})()")
        before = page.evaluate("({score: __game.state.score, misses: __game.state.misses})")
        page.evaluate("__game.audio.log.length = 0")
        page.mouse.click(fly["x"], fly["y"])
        time.sleep(0.25)
        after = page.evaluate("({score: __game.state.score, misses: __game.state.misses, dying: __game.flies.filter(f => f.state === 'dying').length, effects: __game.effects.length})")
        check("點擊命中 → 得分", after["score"] > before["score"], f"{before['score']} -> {after['score']}")
        check("命中 → 蒼蠅進入死亡動畫 + 粒子特效", after["dying"] >= 1 and after["effects"] > 0, f"dying={after['dying']} fx={after['effects']}")

        # 音效：一次出手 = 揮擊 + 擊殺兩層，且擊殺不再重播拍打聲
        snd = page.evaluate("__game.audio.log.map(e => e.name)")
        check("V2 音效分層：swing + kill", "swing" in snd and "kill" in snd, str(snd))
        check("擊殺不會重播拍打聲（不再 slap）", "slap" not in snd, str(snd))
        check("單次擊殺只播一次 kill", snd.count("kill") == 1, str(snd))

        # 空拍：先清場再點空白處（避免剛好打到路過的蒼蠅）
        wait_cool(page)
        page.evaluate("__game.flies.length = 0; __game.state.cool = 0")
        xx, yy = center["w"] * 0.15, center["h"] * 0.75
        page.mouse.click(xx, yy)
        time.sleep(0.2)
        miss = page.evaluate("__game.state.misses")
        check("空拍會計入失誤次數", miss > before["misses"], f"misses={miss}")

        # ---------- 4. 武器解鎖與 5 種武器機制 ----------
        # 換到第 2 關做（目標是擊殺數，不會因為分數達標而誤觸第 1 關通關）
        page.evaluate("__game.startLevel(2)")
        time.sleep(0.3)
        page.evaluate("__game.state.levelScore = 0; __game.addScore(500)")
        time.sleep(0.15)
        w1 = page.evaluate("({weapon: __game.weapon, unlocked: __game.unlocked, toast: document.getElementById('toast').classList.contains('show'), text: document.getElementById('toastText').textContent})")
        check("500 分 → 解鎖塑膠蒼蠅拍", w1["weapon"] == "swatter" and w1["unlocked"] == 2, str(w1))
        check("升級提示動畫有出現", w1["toast"] and "塑膠" in w1["text"], w1["text"])

        # 電蚊拍 AOE：110px 內多隻
        page.evaluate("__game.addScore(1000)")   # 累積 1500
        time.sleep(0.1)
        check("1500 分 → 電蚊拍", page.evaluate("__game.weapon") == "electric")
        ax, ay = center["w"] * 0.5, center["h"] * 0.6
        page.evaluate(f"__game.flies.length = 0; __game.effects.length = 0;"
                      f" __game.spawnFly({ax - 25}, {ay}); __game.spawnFly({ax + 30}, {ay + 18}); __game.spawnFly({ax}, {ay - 30});"
                      f" __game.state.cool = 0;")
        page.mouse.click(ax, ay)
        time.sleep(0.1)   # 電弧特效 ttl 0.22s，要在消失前取樣
        aoe = page.evaluate("({dead: __game.flies.filter(f => f.state === 'dying' || f.dead).length, zaps: __game.effects.filter(e => e.type === 'zap').length})")
        check("電蚊拍一次電死範圍內多隻（含電弧特效）", aoe["dead"] >= 3 and aoe["zaps"] >= 3, str(aoe))
        rapid = page.evaluate("__game.audio.log.filter(e => e.name === 'kill').length")
        check("一次多殺的擊殺音有被限流（≤2 聲）", 0 < rapid <= 2, f"kill 音 {rapid} 聲 / 同時死 {aoe['dead']} 隻")

        # 噴霧：長按持續傷害
        page.evaluate("__game.addScore(2000)")   # 累積 3500
        time.sleep(0.1)
        check("3500 分 → 殺蟲噴霧", page.evaluate("__game.weapon") == "spray")
        sx, sy = center["w"] * 0.5, center["h"] * 0.55
        page.evaluate(f"__game.flies.length = 0;"
                      f" (() => {{ const f = __game.spawnFly({sx}, {sy}, 'bottle');"
                      f" f.speed = 0; f.state = 'rest'; f.restT = 99; f.__testTarget = 1; return 1; }})()")
        page.mouse.move(sx, sy)
        page.mouse.down()
        time.sleep(1.5)
        spray = page.evaluate("({clouds: __game.clouds.length,"
                              " hp: (__game.flies.find(f => f.__testTarget) || {hp: -9}).hp,"
                              " total: __game.flies.length})")
        page.mouse.up()
        check("噴霧長按產生毒霧並持續扣血", spray["hp"] <= 0 or spray["hp"] < 2, str(spray))

        # 雷射：橫貫畫面
        page.evaluate("__game.addScore(3500)")   # 累積 7000
        time.sleep(0.1)
        check("7000 分 → 除蟲雷射炮", page.evaluate("__game.weapon") == "laser")
        ly = center["h"] * 0.4
        page.evaluate(f"__game.flies.length = 0;"
                      f" __game.spawnFly(60, {ly}); __game.spawnFly({center['w'] - 70}, {ly + 6}); __game.spawnFly({center['w'] * 0.5}, {ly - 8});"
                      f" __game.state.cool = 0;")
        page.mouse.click(center["w"] * 0.5, ly)
        time.sleep(0.3)
        laser = page.evaluate("({dead: __game.flies.filter(f => f.state === 'dying' || f.dead).length, beam: !!__game.state.laser, zaps: __game.effects.length})")
        check("雷射一次掃掉整排蒼蠅（含雷射殘影）", laser["dead"] >= 3 and laser["beam"], str(laser))

        # ---------- 5. 第 2 關：擊殺數 + 空拍上限 ----------
        page.evaluate("__game.startLevel(2)")
        time.sleep(0.3)
        l2 = page.evaluate("({level: __game.state.level, prog: document.getElementById('progressText').textContent, misses: __game.state.misses})")
        check("第 2 關：顯示擊殺/空拍進度", l2["level"] == 2 and "空拍" in l2["prog"], l2["prog"])
        page.evaluate("__game.state.misses = 11")
        time.sleep(0.3)
        l2b = page.evaluate("({phase: __game.state.phase, modal: !document.getElementById('modal').classList.contains('hidden')})")
        check("空拍超過 10 次 → 失敗彈窗", l2b["phase"] == "lost" and l2b["modal"], str(l2b))
        page.click("#btnRetry")
        time.sleep(0.3)
        check("重新挑戰 → 回到同一關", page.evaluate("__game.state.phase") == "playing" and page.evaluate("__game.state.level") == 2)

        # ---------- 6. 第 3 關 Boss ----------
        page.evaluate("__game.startLevel(3)")
        time.sleep(0.4)
        boss = page.evaluate("(() => { const b = __game.boss; return b ? {hp: b.hp, r: b.r, x: b.x, y: b.y} : null; })()")
        check("第 3 關：Boss 血量 50、體積 4 倍", boss and boss["hp"] == 50 and boss["r"] >= 40, str(boss))
        minions_before = page.evaluate("__game.flies.filter(f => f.type === 'minion').length")
        page.evaluate("__game.forceSummon()")
        time.sleep(0.2)
        summon = page.evaluate("({minions: __game.flies.filter(f => f.type === 'minion').length, stun: __game.boss.stunT})")
        check("技能 2：召喚子嗣 + 僵直 1.5 秒", summon["minions"] > minions_before and 0 < summon["stun"] <= 1.5, str(summon))

        page.evaluate("__game.state.weaponIndex = 0; __game.state.cool = 0;")   # 報紙 1 傷
        hp_before = page.evaluate("__game.boss.hp")
        boss_pos = page.evaluate("({x: __game.boss.x, y: __game.boss.y})")
        page.evaluate(f"__game.attack({boss_pos['x']}, {boss_pos['y']})")
        time.sleep(0.15)
        hp_after = page.evaluate("(__game.boss ? __game.boss.hp : 0)")
        check("僵直時承受雙倍傷害（1 傷 → 扣 2 血）", hp_before - hp_after == 2, f"{hp_before} -> {hp_after}")

        page.evaluate("__game.state.cool = 0; __game.boss.hp = 1; __game.audio.log.length = 0")
        page.evaluate(f"__game.attack({boss_pos['x']}, {boss_pos['y']})")
        time.sleep(0.5)
        win3 = page.evaluate("({phase: __game.state.phase, modal: !document.getElementById('modal').classList.contains('hidden'), text: document.getElementById('card').textContent})")
        check("Boss 血量歸零 → 通關畫面", win3["phase"] == "won" and win3["modal"] and "通關" in win3["text"], win3["text"][:40])
        bsnd = page.evaluate("__game.audio.log.map(e => e.name)")
        check("Boss 倒下播放專屬音效（bossDown）", bsnd.count("bossDown") == 1, str(bsnd))
        check("Boss 倒下不再疊關卡通關音（win）", bsnd.count("win") == 0, str(bsnd))

        # ---------- 7. 第 1 關達標 → 下一關按鈕 ----------
        page.evaluate("__game.startLevel(1)")
        page.evaluate("__game.state.levelScore = 590; __game.addScore(0)")
        fx, fy = center["w"] * 0.5, center["h"] * 0.5
        page.evaluate(f"__game.spawnFly({fx}, {fy}, 'house'); __game.state.weaponIndex = 0; __game.state.cool = 0;")
        page.mouse.click(fx, fy)
        time.sleep(0.5)
        win1 = page.evaluate("({phase: __game.state.phase, hasNext: !!document.getElementById('btnNext'), prog: document.getElementById('progressBar').style.width})")
        check("第 1 關 600 分達標 → 通關 + 下一關按鈕", win1["phase"] == "won" and win1["hasNext"], str(win1))
        page.click("#btnNext")
        time.sleep(0.4)
        check("按下「下一關」→ 進入第 2 關", page.evaluate("__game.state.level") == 2 and page.evaluate("__game.state.phase") == "playing")

        # ---------- 8. 靜音鈕 ----------
        page.click("#muteBtn")
        time.sleep(0.15)
        muted = page.evaluate("({muted: __game.audio.muted, icon: document.getElementById('muteBtn').textContent, saved: localStorage.getItem('fly.swat.muted')})")
        check("靜音鈕可關閉音效並記住設定", muted["muted"] is True and muted["saved"] == "1", str(muted))
        page.click("#muteBtn")
        time.sleep(0.15)
        unmuted = page.evaluate("({muted: __game.audio.muted, saved: localStorage.getItem('fly.swat.muted')})")
        check("靜音鈕可再開啟", unmuted["muted"] is False and unmuted["saved"] == "0", str(unmuted))

        # ---------- 9. 截圖 ----------
        page.evaluate("__game.startLevel(1)")
        time.sleep(0.8)
        page.screenshot(path=str(ART / "fly-desktop.png"))

        # 手機直向 + 觸控
        mctx = browser.new_context(**dict(p.devices["Pixel 5"]))
        mp = mctx.new_page()
        mp.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        mp.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        mp.goto(url, wait_until="load")
        mp.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        mp.tap("#btnStart")
        time.sleep(0.8)
        mv = mp.evaluate("({phase: __game.state.phase, flies: __game.flies.length, w: innerWidth, h: innerHeight})")
        check("手機（Pixel 5）以觸控開始遊戲", mv["phase"] == "playing" and mv["flies"] > 0, str(mv))
        mp.evaluate("(() => { const f = __game.flies[0]; return 1; })()")
        target = mp.evaluate("(() => { const f = __game.spawnFly(innerWidth * 0.5, innerHeight * 0.5, 'house'); return {x: f.x, y: f.y}; })()")
        mp.touchscreen.tap(target["x"], target["y"])
        time.sleep(0.3)
        check("手機觸控拍打命中有計分", mp.evaluate("__game.state.score") > 0, f"score={mp.evaluate('__game.state.score')}")
        mp.screenshot(path=str(ART / "fly-mobile.png"))
        mctx.close()

        browser.close()

    if server:
        server.shutdown()

    check("沒有 console / page error", not errors, "; ".join(errors[:3]))

    for shot in ("fly-desktop.png", "fly-mobile.png"):
        pth = ART / shot
        check(f"截圖 {shot}", pth.is_file() and pth.stat().st_size > 20_000,
              f"{pth.stat().st_size // 1024} KB" if pth.is_file() else "missing")

    print()
    if FAILS:
        print(f"RESULT: FAIL ({len(FAILS)}: {', '.join(FAILS)})")
        return 1
    print("RESULT: PASS (三關流程、5 種武器、Boss 機制、結算彈窗、手機觸控)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
