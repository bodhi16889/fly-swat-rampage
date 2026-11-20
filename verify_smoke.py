#!/usr/bin/env python3
"""打擊蒼蠅大作戰 V5 —— 端到端驗證（Playwright）。

涵蓋：無限關卡（1–100 關手寫、之後程序生成，章節循環、每 100 關一階）、
3 把可無限升級的重型武器（重錘／火焰／電漿）、轉生與點數升級、
防禦關、蜜蜂/突風、Boss 二階段、無盡模式、廣告復活/續命、持久化、本機 PB/排行、
全球榜（mock API：上傳/排序/復活分榜/訪客/離線 fallback）、手機與 640×480。

時間判定一律用 wait_for_function 等狀態，不用固定 sleep：
headless + SwiftShader 前 1–2 秒只有 1–2 fps，睡眠會量到暖機或舊座標。

    python verify_smoke.py [--base-url URL] [--headed]
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import socketserver
import sys
import threading
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "server"))
import mock_server  # noqa: E402  (local mock API used by the global-board tests)
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

    lb_server = mock_server.start(0)
    lb_url = f"http://127.0.0.1:{lb_server.server_address[1]}"
    print(f"mock leaderboard on {lb_url}")

    def lb_reset() -> None:
        req = urllib.request.Request(lb_url + "/v1/reset", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()

    def lb_post(uid: str, body: dict) -> dict:
        req = urllib.request.Request(
            lb_url + "/v1/scores", data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "Authorization": "Bearer test-" + uid},
        )
        return json.loads(urllib.request.urlopen(req, timeout=5).read())

    errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not args.headed,
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                  "--autoplay-policy=no-user-gesture-required"],
        )
        # 固定 en-US：整套檢查都假設英文文案。browser.new_page() 會繼承宿主 OS
        # locale，在 zh-TW 機器上按鈕文字變中文，英文斷言（如 "keep going"）就會失敗。
        dctx = browser.new_context(locale="en-US", viewport={"width": 430, "height": 880})
        page = dctx.new_page()
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

        # ---------- 2. 選單：無限關卡 / 3 把重型武器 ----------
        menu = page.evaluate("""({
          authored: Object.keys(__game.LEVELS).length,
          weapons: __game.WEAPONS.map(w => [w.id, w.name]),
          chips: document.querySelectorAll('.wbtn').length,
          shopW: document.querySelectorAll('[data-wup]').length,
          nextLv: !!document.getElementById('btnNextLv'),
          cells: document.querySelectorAll('.lvcell').length,
          tabs: document.querySelectorAll('.chtab').length,
          endlessLocked: document.getElementById('btnEndlessMenu').disabled,
          goals: Object.values(__game.LEVELS).reduce((a, l) => { a[l.goal.type] = (a[l.goal.type] || 0) + 1; return a; }, {}),
        })""")
        check("無限關卡：選單只有「下一關」入口，沒有固定關卡格",
              menu["nextLv"] is True and menu["cells"] == 0 and menu["tabs"] == 0
              and menu["authored"] == 100, str({k: menu[k] for k in ("nextLv", "cells", "tabs", "authored")}))
        check("三把重型武器：武器列 3 格、商店 3 個可升級武器",
              [w[0] for w in menu["weapons"]] == ["hammer", "flame", "plasma"]
              and menu["chips"] == 3 and menu["shopW"] == 3,
              f"{menu['weapons']} chips={menu['chips']} shop={menu['shopW']}")
        check("關卡目標四型都有（score / kills / defend / boss）",
              all(menu["goals"].get(k, 0) > 0 for k in ("score", "kills", "defend", "boss"))
              and sum(menu["goals"].values()) == 100, str(menu["goals"]))

        inf = page.evaluate("""(() => {
          const pick = (n) => {
            const c = __game.levelCfg(n);
            return {n, chapter: c.chapter, stage: c.stage, loop: c.loop, hpMul: c.hpMul,
                    goal: c.goal.type, time: c.time, spawn: +c.spawnEvery.toFixed(3),
                    targets: c.targetCount, bossHp: c.bossHp || null, name: c.name};
          };
          return [pick(101), pick(250), pick(1000), pick(1001)];
        })()""")
        check("無限關卡：超過 100 關照樣生成（章節循環、每 100 關一階更硬）",
              all(x["loop"] >= 2 for x in inf)
              and inf[0]["chapter"] == 1 and inf[1]["loop"] == 3 and inf[2]["loop"] == 10
              and inf[3]["loop"] == 11 and inf[3]["hpMul"] > inf[0]["hpMul"]
              and inf[1]["goal"] == "boss" and inf[1]["bossHp"] > 0, str(inf))

        diff = page.evaluate("""({
          spawn: [1, 25, 49, 75, 99].map(n => +__game.levelCfg(n).spawnEvery.toFixed(3)),
          boss: [10, 50, 100].map(n => __game.levelCfg(n).bossHp),
          times: [1, 50, 100].map(n => __game.levelCfg(n).time),
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

        scenes = page.evaluate("Array.from({length:100}, (_, i) => {"
                               " const n = i + 1, s = __game.sceneSpec(n);"
                               " return {n, chapter: s.chapter, name: s.name, en: s.name_en,"
                               " key: s.key, hash: __game.sceneHash(n)}; })")
        names = {s["name"] for s in scenes}
        ens = {s["en"] for s in scenes}
        keys = {s["key"] for s in scenes}
        hashes = {s["hash"] for s in scenes}
        per_chapter = {c: sum(1 for s in scenes if s["chapter"] == c) for c in range(1, 6)}
        check("100 關場景：每關都有獨立名稱與場景 key",
              len(scenes) == 100 and len(names) == 100 and len(ens) == 100 and len(keys) == 100
              and all(v == 20 for v in per_chapter.values()), f"{len(names)}/{len(keys)} {per_chapter}")
        check("100 關場景：像素指紋全部不同（不是同一張換色）",
              len(hashes) == 100, f"unique={len(hashes)}")

        # ---------- 2b. 回歸：動態層（雨／霓虹／第4章日光／營火）不得拋錯 ----------
        # 2026-11-05 真實缺陷：drawSceneFx 用了未宣告的 g（實際叫 ctx），
        # 只有 scene time 為 rain/neon 的關卡會走到該分支 → 每 3 關壞一關（含第 43 關）。
        # 症狀不只「畫面空」：rAF 第一帧就抛錯 → __game.frame 完全不再前進（整個遊戲凍結）。
        def frames_advance(n_frames: int = 3, budget_s: float = 2.0) -> bool:
            start = page.evaluate("__game.frame")
            deadline = time.time() + budget_s
            while time.time() < deadline:
                if page.evaluate("__game.frame") >= start + n_frames:
                    return True
                time.sleep(0.05)
            return False

        rain_levels = []
        for n in range(1, 101):
            t = page.evaluate(f"__game.sceneSpec({n}).time.id")
            if t in ("rain", "neon"):
                rain_levels.append(n)

        err_before = len(errors)
        stuck = []
        for n in rain_levels:
            page.evaluate(f"__game.startLevel({n})")
            if not frames_advance(3):
                stuck.append(n)
        new_errs = errors[err_before:]
        check("雨／霓虹關卡（含第 43 關）動態層可繪製、主循環不中斷",
              not stuck and not new_errs and 43 in rain_levels,
              f"{len(rain_levels)} 關; stuck={stuck[:4]}; errs={new_errs[:2]}")

        page.evaluate("__game.startLevel(43)")
        lv43 = page.evaluate("({phase: __game.state.phase, level: __game.state.level, flies: __game.flies.length})")
        check("第 43 關可進入、生成目標、frame 持續前進",
              lv43["phase"] == "playing" and lv43["level"] == 43 and lv43["flies"] > 0 and frames_advance(5),
              str(lv43))

        # 回到選單，否則後續對 .lvcell 的點擊會被 canvas 攔走（pointer-events 被遊戲吃掉）
        page.evaluate("__game.showStart()")
        page.wait_for_selector("#btnNextLv", state="visible", timeout=10_000)
        time.sleep(0.3)

        page.click("#btnNextLv")
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

        page.evaluate("__game.state.auto = false; __game.state.autoT = 0")   # 音效斷言需要只有玩家這一下
        page.evaluate("__game.audio.log.length = 0; __game.voice.log.length = 0")
        # headless 第一次點擊只會被 AudioContext 拿去解鎖，先空點一下再量
        page.mouse.click(20, 20)
        time.sleep(0.2)
        fly = page.evaluate("(() => { __game.startLevel(1); __game.flies.length = 0;"
                            " __game.state.cool = 0;"
                            " const f = __game.spawnFly(innerWidth * .5, innerHeight * .45, 'house');"
                            " f.hp = f.maxHp = 1; f.state = 'rest'; f.restT = 9;"
                            " return {x: f.x, y: f.y}; })()")
        page.evaluate("__game.audio.log.length = 0; __game.voice.log.length = 0")
        page.mouse.click(fly["x"], fly["y"])
        time.sleep(0.35)
        snd = page.evaluate("({a: __game.audio.log.map(e => e.name), v: __game.voice.log.map(e => e.name)})")
        check("擊殺音效分層 + 人聲", "swing" in snd["a"] and "kill" in snd["a"] and snd["v"].count("voice:kill") == 1, str(snd))

        page.evaluate("__game.flies.length = 0; __game.state.cool = 0")
        miss_before = page.evaluate("__game.state.misses")
        page.mouse.click(30, page.evaluate("innerHeight") * 0.8)
        time.sleep(0.2)
        check("空拍計入失誤", page.evaluate("__game.state.misses") > miss_before)

        # ---------- 4. 三把重型武器：機制 + 無限升級 ----------
        def goto_level(n: int):
            page.evaluate(f"__game.startLevel({n})")
            time.sleep(0.35)

        def clear():
            page.evaluate(
                "__game.flies.length = 0; __game.clouds.length = 0; __game.traps.length = 0;"
                " __game.state.waves.length = 0; __game.state.decoys.length = 0;"
                " __game.state.rockets.length = 0; __game.state.drones.length = 0;"
                " __game.effects.length = 0; __game.state.cool = 0")

        def dead_all(timeout: int = 8_000) -> bool:
            try:
                page.wait_for_function(
                    "window.__probe && window.__probe.every(f => f.dead || f.state === 'dying' || f.hp <= 0)",
                    timeout=timeout)
                return True
            except Exception:
                return False

        def probe_attack(idx: int, points, at, timeout: int = 8_000) -> bool:
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
        check("重型碎蠅錘：半徑 120 內一次全清",
              probe_attack(0, [[W/2-85, H/2], [W/2+85, H/2], [W/2, H/2-95]], (W/2, H/2)))
        check("重型火焰噴射器：74° 扇形內多隻同時燒掉",
              probe_attack(1, [[W/2, H/2-140], [W/2+80, H/2-110]], (W/2, H/2)))
        check("重型電漿炮：整條橫幅穿透清場",
              probe_attack(2, [[80, H*0.55], [W-80, H*0.55], [W/2, H*0.56]], (W/2, H*0.55)))

        # 三把武器都能無限升級：30 級仍可買、傷害與成本同步成長
        grow = page.evaluate("""(() => {
          const s = __game.state;
          s.wlv = [0, 0, 0]; s.weaponIndex = 0; s.bank = 1e12;
          const d0 = __game.currentWeapon().damage, c0 = __game.wCost(0);
          for (let i = 0; i < 5; i++) __game.buyWeaponUpgrade(0);
          const d5 = __game.currentWeapon().damage, c5 = __game.wCost(0);
          for (let i = 0; i < 25; i++) __game.buyWeaponUpgrade(0);
          const r = {d0, d5, d30: __game.currentWeapon().damage, lv: s.wlv[0], c0, c5, c30: __game.wCost(0)};
          for (let i = 0; i < 200; i++) { s.bank = 1e30; __game.buyWeaponUpgrade(0); }   // 衝到 230 級，證明沒有等級上限
          r.lvHigh = s.wlv[0]; r.dHigh = __game.currentWeapon().damage;
          return r;
        })()""")
        check("重型武器無限升級：Lv30 仍可買、Lv230 也行、傷害與成本同步成長",
              grow["lv"] == 30 and grow["lvHigh"] == 230
              and grow["d5"] > grow["d0"] and grow["d30"] > grow["d5"] and grow["dHigh"] > grow["d30"]
              and grow["c5"] > grow["c0"] and grow["c30"] > grow["c5"], str(grow))
        check("傷害公式：每級 +30%（Lv30 → 基礎 4 變 40）",
              abs(grow["d30"] - 40) <= 1, f"d30={grow['d30']}")

        # 升級真的讓擊殺變快：把等級歸零後 2HP 綠頭蠅打不死，升幾級後一擊帶走
        page.evaluate("__game.state.wlv = [0,0,0]; __game.state.weaponIndex = 0")
        weak = page.evaluate("""(() => {
          __game.startLevel(1); __game.flies.length = 0; __game.state.cool = 0;
          const f = __game.spawnFly(300, 400, 'house'); f.state = 'rest'; f.restT = 9;
          __game.attack(300, 400);
          return {dmg: __game.currentWeapon().damage, hp: f.hp, dead: !!f.dead};
        })()""")
        page.evaluate("__game.state.bank = 1e9; for (let i=0;i<6;i++) __game.buyWeaponUpgrade(0)")
        strong = page.evaluate("""(() => {
          __game.startLevel(1); __game.flies.length = 0; __game.state.cool = 0;
          const f = __game.spawnFly(300, 400, 'house'); f.state = 'rest'; f.restT = 9;
          __game.attack(300, 400);
          return {dmg: __game.currentWeapon().damage, hp: f.hp, dead: !!f.dead};
        })()""")
        check("升級效果是真的：傷害 4→11、命中即清掉該格蒼蠅",
              weak["dmg"] == 4 and strong["dmg"] > weak["dmg"] * 2
              and (weak["dead"] is True or weak["hp"] <= 0)
              and (strong["dead"] is True or strong["hp"] <= 0), f"{weak} -> {strong}")

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
          __game.state.weaponIndex = 2; __game.state.cool = 0;
          __game.attack(innerWidth / 2, b.y);
          return {hp0, hp1: b.hp, shield: b.shieldCount};
        })()""")
        check("電漿炮：穿透護盾削弱 Boss（每級 +30%，基礎 10 傷）",
              pierce["hp1"] <= pierce["hp0"] - 8, str(pierce))

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
          const hp0 = b.hp, dmg = __game.currentWeapon().damage;
          __game.attack(b.x, b.y);
          return {hp0, hp1: b.hp, exhaust: b.exhaustT, dmg};
        })()""")
        crit_dmg = crit["hp0"] - crit["hp1"]
        check("力竭期間受到雙倍傷害", crit_dmg >= 2 * crit["dmg"] - 1,
              f"{crit} → 實際 {crit_dmg}")

        page.evaluate("""(() => {
          const b = __game.boss;
          __game.state.weaponIndex = 2; __game.state.cool = 0;
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

        # ---------- 11. 重型武器等級持久化（無限升級） ----------
        page.evaluate("""(() => {
          const s = __game.state;
          s.bank = 1e9; s.wlv = [0, 0, 0]; s.weaponIndex = 0;
          for (let i = 0; i < 4; i++) __game.buyWeaponUpgrade(0);
          __game.buyWeaponUpgrade(1);
          __game.saveMeta();
        })()""")
        before = page.evaluate("({lv: __game.state.wlv.slice(), weapon: __game.weapon,"
                               " dmg: __game.currentWeapon().damage})")
        page.reload(wait_until="load")
        page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        wait_frames(page, 5)
        after = page.evaluate("({lv: __game.state.wlv.slice(), weapon: __game.weapon,"
                              " chips: document.querySelectorAll('.wbtn').length,"
                              " dmg: __game.currentWeapon().damage,"
                              " label: document.getElementById('weaponName').textContent})")
        check("重型武器等級持久化：重載後 Lv 保留、傷害照算、HUD 顯示 Lv",
              before["lv"] == [4, 1, 0] and after["lv"] == [4, 1, 0]
              and after["weapon"] == "hammer" and after["chips"] == 3
              and after["dmg"] == before["dmg"] and "Lv4" in after["label"],
              f"{before} -> {after}")

        page.evaluate("__game.startLevel(1, true)")
        reset = page.evaluate("({score: __game.state.score, unlocked: __game.state.unlocked,"
                              " stored: localStorage.getItem('fly.swat.score'), level: __game.state.level})")
        check("從第 1 關重新開始只重置分數；武器等級保留到轉生為止",
              reset["score"] == 0 and reset["unlocked"] == 3 and reset["stored"] == "0"
              and reset["level"] == 1, str(reset))

        # ---------- 11c. idle 層：轉生 / 自動攻擊 / 分數升級 ----------
        page.evaluate("try { ['fly.swat.meta','fly.swat.score','fly.swat.progress']"
                      ".forEach(k => localStorage.removeItem(k)); } catch (e) {}")
        page.reload(wait_until="load")
        page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        wait_frames(page, 5)

        m0 = page.evaluate("({auto: __game.state.auto, bank: __game.state.bank,"
                           " upg: __game.state.upg, wlv: __game.state.wlv,"
                           " essence: __game.state.essence})")
        check("idle：預設開自動攻擊、點數 0、武器 0 級、無精華",
              m0["auto"] is True and m0["bank"] == 0 and m0["wlv"] == [0, 0, 0]
              and m0["upg"] == {"rate": 0, "coin": 0} and m0["essence"] == 0, str(m0))

        ui = page.evaluate("({bank: !!document.getElementById('bank'),"
                           " auto: !!document.getElementById('autoBtn'),"
                           " shop: !!document.getElementById('shopHost'),"
                           " rebirth: !!document.getElementById('btnRebirth')})")
        check("idle：HUD 有點數與自動鍵、選單有升級與轉生按鈕", all(ui.values()), str(ui))

        page.evaluate("__game.addScore(1000)")
        bank = page.evaluate("({score: __game.state.score, bank: __game.state.bank,"
                             " rate: __game.coinRate(),"
                             " saved: (JSON.parse(localStorage.getItem('fly.swat.meta') || '{}')).bank})")
        check("idle：得分會累積點數（基礎 20%）並寫進存檔",
              bank["score"] == 1000 and abs(bank["bank"] - 200) < 1 and bank["saved"] == 200, str(bank))

        buy = page.evaluate("""(() => {
          const s = __game.state; s.weaponIndex = 0; s.wlv = [0, 0, 0];
          const cost = __game.wCost(0);
          const before = {bank: s.bank, lv: s.wlv[0], dmg: __game.currentWeapon().damage};
          const ok = __game.buyWeaponUpgrade(0);
          return {ok, cost, before,
                  after: {bank: s.bank, lv: s.wlv[0], dmg: __game.currentWeapon().damage}};
        })()""")
        check("idle：買重錘升級會扣點、等級 +1、傷害倍率提高",
              buy["ok"] is True and buy["after"]["lv"] == buy["before"]["lv"] + 1
              and abs(buy["after"]["bank"] - (buy["before"]["bank"] - buy["cost"])) < 1e-6
              and buy["after"]["dmg"] > buy["before"]["dmg"], str(buy))

        poor = page.evaluate("""(() => {
          const s = __game.state, keep = s.bank;
          s.bank = 5;
          const ok = __game.buyUpgrade('coin');
          const r = {ok, lv: s.upg.coin, bank: s.bank};
          s.bank = keep + 300; return r;
        })()""")
        check("idle：點數不足買不了、也不會扣點",
              poor["ok"] is False and poor["lv"] == 0 and poor["bank"] == 5, str(poor))

        auto_on = page.evaluate("""async () => {
          const s = __game.state;
          s.auto = true; s.autoT = 0;
          s.score = 0; s.unlocked = 3; s.weaponIndex = 0;   // 用重錘，確定自動攻擊會擊殺
          __game.startLevel(1, false);
          const k0 = s.kills, f0 = __game.frame;
          await new Promise(r => setTimeout(r, 3000));
          const t = __game.nearestEnemy();
          return {k0, k1: s.kills, flies: s.flies.filter(f => !f.dead && !f.friendly).length,
                  interval: __game.autoInterval(), frames: __game.frame - f0,
                  auto: s.auto, paused: s.paused, phase: s.phase, cool: +s.cool.toFixed(2),
                  autoT: +s.autoT.toFixed(2), lock: +s.weaponLockT.toFixed(2),
                  target: t ? [Math.round(t.x), Math.round(t.y)] : null,
                  weapon: __game.weapon, score: s.score};
        }""")
        check("自動攻擊：完全不點擊也會自己清掉蒼蠅",
              auto_on["k1"] > auto_on["k0"] and auto_on["interval"] <= 1.25,
              f"kills {auto_on['k0']} -> {auto_on['k1']}, interval={auto_on['interval']:.2f}s, {auto_on}")

        auto_off = page.evaluate("""async () => {
          const s = __game.state;
          s.auto = false; s.autoT = 0;
          const k0 = s.kills;
          await new Promise(r => setTimeout(r, 1600));
          const k1 = s.kills;
          s.auto = true;
          return {k0, k1};
        }""")
        check("自動攻擊：關掉後不再自己出手", auto_off["k1"] == auto_off["k0"], str(auto_off))

        reb = page.evaluate("""(() => {
          const s = __game.state;
          s.deepest = 0; s.score = 100; s.essence = 0;
          const blocked = __game.rebirthGain();
          s.deepest = 20;
          const gain = __game.rebirthGain();
          return {blocked, gain};
        })()""")
        check("轉生：未達門檻（20 關或 30,000 分）不給精華，達標才給",
              reb["blocked"] == 0 and reb["gain"] >= 1, str(reb))

        done = page.evaluate("""(() => {
          const s = __game.state;
          s.deepest = 30; s.score = 40000; s.bank = 500;
          s.upg = {dmg: 5, rate: 2, coin: 1}; s.essence = 0; s.rebirths = 0;
          const before = __game.dmgMult();
          const gain = __game.doRebirth();
          return {gain, score: s.score, bank: s.bank, upg: s.upg, essence: s.essence,
                  rebirths: s.rebirths, deepest: s.deepest, phase: s.phase,
                  mult: __game.dmgMult(), before,
                  saved: JSON.parse(localStorage.getItem('fly.swat.meta') || '{}').essence};
        })()""")
        check("轉生：拿精華、分數/點數/升級/進度歸零、永久傷害加成生效、寫進存檔",
              done["gain"] >= 1 and done["score"] == 0 and done["bank"] == 0
              and done["upg"] == {"rate": 0, "coin": 0}
              and done["essence"] == done["gain"] and done["saved"] == done["gain"]
              and done["rebirths"] == 1 and done["deepest"] == 0
              and abs(done["mult"] - (1 + 0.01 * done["gain"])) < 1e-9
              and done["phase"] == "menu", str(done))

        page.reload(wait_until="load")
        page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        page.wait_for_function("__game.gp.log.includes('loaded')", timeout=15_000)
        kept = page.evaluate("({essence: __game.state.essence, rebirths: __game.state.rebirths,"
                             " score: __game.state.score, mult: __game.dmgMult()})")
        check("idle：精華／轉生次數重載後仍保留、分數歸零",
              kept["essence"] == done["gain"] and kept["rebirths"] == 1
              and kept["score"] == 0 and kept["mult"] > 1.0, str(kept))
        page.evaluate("__game.startLevel(1, false)")
        wait_frames(page, 3)

        # ---------- 12. GamePix SDK（生命週期／暫停／廣告／復活／續命／無 SDK） ----------
        gp = page.evaluate("({enabled: __game.gp.enabled, log: __game.gp.log,"
                           " hidden: document.getElementById('loading').classList.contains('hidden')})")
        check("GamePix：manual lifecycle 載入完成、loading 已收",
              gp["enabled"] and "loaded" in gp["log"] and "loading:100" in gp["log"] and gp["hidden"],
              str(gp["log"]))
        check("GamePix：開始關卡會送 gameStart", "gameStart" in page.evaluate("__game.gp.log"))
        check("GamePix：非 Player 的公開頁不呼叫廣告",
              page.evaluate("__game.gp.adsAllowed === false"))

        # ---------- 11b. 語系預設（GamePix 送審要求：一律英文）----------
        zctx = browser.new_context(locale="zh-TW")
        zp = zctx.new_page()
        zp.goto(url, wait_until="load")
        zp.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        dflt = zp.evaluate("({lang: __game.lang, htmlLang: document.documentElement.lang,"
                           " h1: document.querySelector('#card h1').textContent,"
                           " title: document.title,"
                           " chip: document.querySelector('.wbtn').textContent})")
        check("語系：系統是中文也預設英文（標題固定 Fly Swatter）",
              dflt["lang"] == "en" and dflt["htmlLang"] == "en"
              and dflt["h1"] == "Fly Swatter" and dflt["title"] == "Fly Swatter"
              and "\u5831\u7d19" not in dflt["chip"], str(dflt))

        VOICE_STUB = """(() => {
          window.__utt = [];
          const fake = { getVoices: () => [{lang: 'zh-TW', name: 'z'}, {lang: 'en-US', name: 'e'}],
                         speak: (u) => window.__utt.push(u.lang) };
          const real = window.speechSynthesis;
          Object.defineProperty(window, 'speechSynthesis', {value: fake, configurable: true});
          __game.voice.lastKillAt = -1e9;
          __game.voice.kill();
          Object.defineProperty(window, 'speechSynthesis', {value: real, configurable: true});
          return window.__utt;
        })()"""
        en_voice = zp.evaluate(VOICE_STUB)
        check("英文模式：人聲用英文聲音，不會出現 zh-TW",
              bool(en_voice) and all(x == "en-US" for x in en_voice), str(en_voice))

        zpz = zctx.new_page()
        zpz.goto(url + "?lang=zh", wait_until="load")
        zpz.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        zhst = zpz.evaluate("({lang: __game.lang, htmlLang: document.documentElement.lang,"
                            " h1: document.querySelector('#card h1').textContent,"
                            " chip: document.querySelector('.wbtn').textContent})")
        zh_voice = zpz.evaluate(VOICE_STUB)
        check("?lang=zh：介面中文、標題仍是 Fly Swatter、人聲是中文",
              zhst["lang"] == "zh" and zhst["htmlLang"] == "zh-Hant"
              and zhst["h1"] == "Fly Swatter" and "\u91cd\u9318" in zhst["chip"]
              and (not zh_voice or all(x.startswith("zh") for x in zh_voice)), str(zhst))
        zctx.close()

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

        # ---------- 12b. 全球排行榜（前端 + 本機 mock API） ----------
        types = page.evaluate("Object.keys(__game.LEVELS).map(n => [Number(n), __game.LEVELS[n].goal.type])")
        mismatch = [n for n, tp in types if mock_server.goal_type(n) != tp]
        check("全球榜：100 關排名型別與後端一致",
              len(types) == 100 and not mismatch, str(mismatch[:5]))

        page.evaluate("__game.showStart()")
        off = page.evaluate("({enabled: __game.lb.enabled, button: !!document.getElementById('btnGlobal')})")
        check("全球榜預設關閉：沒有入口、不初始化連線",
              off["enabled"] is False and off["button"] is False, str(off))

        off_ctx = browser.new_context(locale="en-US")
        op = off_ctx.new_page()
        op.goto(url + "?lb=off&lb_url=" + lb_url + "&lb_token=test-alice", wait_until="load")
        op.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        forced = op.evaluate("({enabled: __game.lb.enabled, button: !!document.getElementById('btnGlobal')})")
        check("全球榜：?lb=off 可強制關閉（即使有 LB_URL）",
              forced["enabled"] is False and forced["button"] is False, str(forced))
        off_ctx.close()

        lb_reset()
        gctx = browser.new_context(locale="en-US")
        gp = gctx.new_page()
        gp.on("pageerror", lambda e: errors.append(f"pageerror(global): {e}"))
        gp.goto(url + "?lb=on&lb_url=" + lb_url + "&lb_token=test-alice", wait_until="load")
        gp.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        on = gp.evaluate("({enabled: __game.lb.enabled, button: !!document.getElementById('btnGlobal')})")
        check("全球榜：?lb=on 才啟用並顯示入口", on["enabled"] and on["button"], str(on))

        gp.evaluate("__game.startLevel(1); __game.addScore(500 - __game.state.levelScore)")
        gp.wait_for_function("__game.state.phase === 'won'", timeout=5_000)
        gp.wait_for_function("__game.lb.lastResult && __game.lb.lastResult.status === 'ok'", timeout=10_000)
        sent = gp.evaluate("({res: __game.lb.lastResult,"
                           " ui: document.getElementById('globalResult').textContent.trim()})")
        check("全球送分：成功寫入並顯示名次",
              sent["res"]["rank"] == 1 and "Global #1" in sent["ui"], str(sent))

        lb_post("bob", {"level": 1, "value": 900, "timeMs": 1000,
                        "misses": 0, "revived": 0, "name": "Bob"})
        gp.evaluate("__game.showGlobalLevel(1, 0)")
        gp.wait_for_function("document.querySelectorAll('#globalList .brow').length >= 2", timeout=10_000)
        rows = gp.evaluate("[...document.querySelectorAll('#globalList .brow')]"
                           ".map(x => x.textContent.replace(/\s+/g, ' ').trim())")
        me = gp.evaluate("document.getElementById('globalMe').textContent.trim()")
        check("全球榜：分數排序、標記自己",
              "Bob" in rows[0] and "Alice" in rows[1] and "you" in me, f"{rows} / {me}")

        gp.evaluate("__game.startLevel(1); __game.state.revived = true;"
                    " __game.addScore(700 - __game.state.levelScore)")
        gp.wait_for_function("__game.lb.lastResult && __game.lb.lastResult.revived === 1"
                             " && __game.lb.lastResult.status === 'ok'", timeout=10_000)
        gp.evaluate("__game.showGlobalLevel(1, 1)")
        gp.wait_for_function("document.querySelectorAll('#globalList .brow').length >= 1", timeout=10_000)
        assisted = gp.evaluate("[...document.querySelectorAll('#globalList .brow')]"
                               ".map(x => x.textContent.replace(/\s+/g, ' ').trim())")
        gp.evaluate("__game.showGlobalLevel(1, 0)")
        gp.wait_for_function("document.querySelectorAll('#globalList .brow').length >= 2", timeout=10_000)
        normal = gp.evaluate("document.querySelectorAll('#globalList .brow').length")
        check("全球榜：復活成績分榜、不污染一般榜",
              len(assisted) == 1 and "revived" in assisted[0] and normal == 2,
              f"{assisted} / normal={normal}")

        gp.evaluate("__game.showGlobalBoard(1)")
        check("全球榜：章節 20 關入口",
              gp.evaluate("document.querySelectorAll('.brow[data-glevel]').length") == 20)
        gctx.close()

        guest_ctx = browser.new_context(locale="en-US")
        guest = guest_ctx.new_page()
        guest.on("pageerror", lambda e: errors.append(f"pageerror(guest): {e}"))
        guest.goto(url + "?lb=on&lb_url=" + lb_url, wait_until="load")
        guest.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        guest.evaluate("__game.startLevel(1); __game.addScore(500 - __game.state.levelScore)")
        guest.wait_for_function("__game.state.phase === 'won'", timeout=5_000)
        guest.wait_for_function("__game.lb.lastResult && __game.lb.lastResult.status === 'guest'", timeout=15_000)
        gres = guest.evaluate("({res: __game.lb.lastResult, auth: !!__game.lb.auth,"
                              " ui: document.getElementById('globalResult').textContent.trim()})")
        check("全球榜：訪客可玩、不上傳、提示登入",
              gres["res"]["status"] == "guest" and not gres["auth"] and "Sign in" in gres["ui"],
              str(gres))
        guest.evaluate("__game.showGlobalLevel(1, 0)")
        guest.wait_for_function("document.querySelectorAll('#globalList .brow').length >= 2", timeout=10_000)
        gboard = guest.evaluate("({login: !!document.getElementById('btnGlobalLogin'),"
                                " me: document.getElementById('globalMe').textContent.trim()})")
        check("全球榜：訪客看得到榜、有登入入口",
              gboard["login"] and "Sign in" in gboard["me"], str(gboard))
        guest_ctx.close()

        fail_ctx = browser.new_context(locale="en-US")
        fp = fail_ctx.new_page()
        ferrs: list[str] = []
        fp.on("pageerror", lambda e: ferrs.append(str(e)))
        fp.goto(url + "?lb=on&lb_url=http://127.0.0.1:1&lb_token=test-cara", wait_until="load")
        fp.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        fp.evaluate("__game.startLevel(1); __game.addScore(500 - __game.state.levelScore)")
        fp.wait_for_function("__game.state.phase === 'won'", timeout=5_000)
        fp.wait_for_function("__game.lb.lastResult && __game.lb.lastResult.status === 'error'", timeout=15_000)
        fail = fp.evaluate("({ui: document.getElementById('globalResult').textContent.trim(),"
                           " pb: !!__game.bests['1'], res: __game.lb.lastResult})")
        check("全球榜失敗：本機 PB 保留、顯示離線、不丟例外",
              fail["res"]["status"] == "error" and fail["pb"] and "unavailable" in fail["ui"] and not ferrs,
              str(fail))
        fail_ctx.close()

        # ---------- 13. 手機（Pixel 5） ----------
        mctx = browser.new_context(**dict(p.devices["Pixel 5"]))
        mp = mctx.new_page()
        mp.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        mp.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        mp.goto(url, wait_until="load")
        mp.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        mp.tap("#btnNextLv")
        mp.wait_for_function("__game.state.phase === 'playing'", timeout=5_000)
        mv = mp.evaluate("({phase: __game.state.phase, chips: document.querySelectorAll('.wbtn').length, w: innerWidth, h: innerHeight})")
        check("手機（Pixel 5）：直向版面 + 3 把重型武器列", mv["phase"] == "playing" and mv["chips"] == 3, str(mv))
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
          nextLv: !!document.getElementById('btnNextLv'),
          w: innerWidth, h: innerHeight,
        })""")
        sp.click("#btnNextLv")
        sp.wait_for_function("__game.state.phase === 'playing'", timeout=5_000)
        play = sp.evaluate("({phase: __game.state.phase, chips: document.querySelectorAll('.wbtn').length,"
                           " barTop: document.querySelector('#weaponbar').getBoundingClientRect().top, h: innerHeight})")
        check("640×480 iframe：選單可捲動、可進關卡、3 把重型武器列在畫面內",
              fit["scrollable"] == "auto" and fit["cardTop"] >= -1 and fit["cardBottom"] <= fit["h"] + 1
              and fit["barBottom"] <= fit["h"] + 1 and fit["nextLv"] is True and play["phase"] == "playing"
              and play["chips"] == 3 and play["barTop"] < play["h"], f"{fit} -> {play}")
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
                         " chip: document.querySelector('.wbtn').textContent,"
                         " htmlLang: document.documentElement.lang,"
                         " url: location.search})")
        check("語言切換：英文介面可切中文、選擇會記住",
              h1_en == "Fly Swatter" and zh["lang"] == "zh" and zh["stored"] == "zh"
              and zh["h1"] == "Fly Swatter" and zh["htmlLang"] == "zh-Hant"
              and "lang=zh" in zh["url"] and "\u91cd\u9318" in zh["chip"],
              f"{h1_en} -> {zh['h1']} / {zh['stored']} / {zh['url']}")
        lctx.close()
        dctx.close()

        browser.close()

    lb_server.shutdown()
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
    print("RESULT: PASS (無限關卡 / 100 場景 / 3 把重型武器 / 防禦 / 蜜蜂 / Boss 二階段 / 無盡 / 音效人聲 / 持久化 / 本機 PB / 全球榜 / 轉生 / 自動攻擊 / 分數升級 / GamePix SDK / 手機 / 640×480)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
