#!/usr/bin/env python3
"""把 verify_smoke.py 改成「無限關卡 + 3 把重型武器」版本。可重複執行。"""
import io, os, sys

P = os.path.expanduser('~/fly-swat-rampage/verify_smoke.py')
src = io.open(P, encoding='utf-8').read()
done = 0


def rep(tag, old, new, count=1):
    global src, done
    n = src.count(old)
    if n == 0:
        if new[:80] in src:
            print('  - 已套用:', tag); return
        raise SystemExit(f'✗ 找不到錨點 {tag}')
    if n != count:
        raise SystemExit(f'✗ 錨點 {tag} 出現 {n} 次（預期 {count}）')
    src = src.replace(old, new, count)
    done += 1
    print('  ✓', tag)


# ============ 1. 選單段（100 關 → 無限關卡） ============
old_menu_start = src.index('        # ---------- 2. 選單：100 關 / 20 武器 / 5 章 ----------')
old_menu_end = src.index('        profile = page.evaluate(')
NEW_MENU = '''        # ---------- 2. 選單：無限關卡 / 3 把重型武器 ----------
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
              and inf[0]["chapter"] == 1 and inf[1]["loop"] == 3 and inf[2]["loop"] == 5
              and inf[3]["loop"] == 6 and inf[3]["hpMul"] > inf[0]["hpMul"]
              and inf[1]["goal"] == "boss" and inf[1]["bossHp"] > 0, str(inf))

        diff = page.evaluate("""({
          spawn: [1, 25, 49, 75, 99].map(n => +__game.levelCfg(n).spawnEvery.toFixed(3)),
          boss: [10, 50, 100].map(n => __game.levelCfg(n).bossHp),
          times: [1, 50, 100].map(n => __game.levelCfg(n).time),
        })""")
        check("難度遞增：生成間隔變短、Boss HP 變高",
              all(a > b for a, b in zip(diff["spawn"], diff["spawn"][1:]))
              and all(a < b for a, b in zip(diff["boss"], diff["boss"][1:])), str(diff))

'''
src = src[:old_menu_start] + NEW_MENU + src[old_menu_end:]
done += 1
print('  ✓ 選單段改寫')

# ============ 2. 武器段（4 + 5）改寫成三把重型武器 ============
old_w_start = src.index('        # ---------- 4. 武器庫：前 8 把機制 ----------')
old_w_end = src.index('        # ---------- 5b. 每關 PB / 本機排行 ----------')
NEW_W = '''        # ---------- 4. 三把重型武器：機制 + 無限升級 ----------
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
          for (let i = 0; i < 200; i++) __game.buyWeaponUpgrade(0);   // 衝到 230 級，證明沒有上限
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
          const f = __game.spawnFly(300, 400, 'bottle'); f.state = 'rest'; f.restT = 9;
          __game.attack(300, 400);
          return {dmg: __game.currentWeapon().damage, hp: f.hp, dead: !!f.dead};
        })()""")
        page.evaluate("__game.state.bank = 1e9; for (let i=0;i<6;i++) __game.buyWeaponUpgrade(0)")
        strong = page.evaluate("""(() => {
          __game.startLevel(1); __game.flies.length = 0; __game.state.cool = 0;
          const f = __game.spawnFly(300, 400, 'bottle'); f.state = 'rest'; f.restT = 9;
          __game.attack(300, 400);
          return {dmg: __game.currentWeapon().damage, hp: f.hp, dead: !!f.dead};
        })()""")
        check("升級效果是真的：Lv0 打不死 2HP 綠頭蠅，Lv6 一擊帶走",
              weak["dead"] is False and weak["hp"] > 0
              and (strong["dead"] is True or strong["hp"] <= 0), f"{weak} -> {strong}")

        # Boss：電漿炮穿透護盾削弱
        goto_level(10)
        page.evaluate("__game.state.weaponIndex = 2; __game.state.cool = 0")
        pierce = page.evaluate("""(() => {
          const b = __game.boss;
          __game.attack(innerWidth / 2, b.y);
          return {hp0: b.maxHp, hp1: b.hp};
        })()""")
        check("電漿炮：穿透護盾削弱 Boss（10 傷 × 等級倍率）", pierce["hp1"] < pierce["hp0"], str(pierce))

'''
src = src[:old_w_start] + NEW_W + src[old_w_end:]
done += 1
print('  ✓ 武器段改寫')

# ============ 3. 後續零散引用 ============
rep('Boss 雷射索引', "__game.state.weaponIndex = 7; __game.state.cool = 0;",
    "__game.state.weaponIndex = 2; __game.state.cool = 0;", count=2)

# ============ 4. 武器持久化段 ============
old_p_start = src.index('        # ---------- 11. 武器解鎖持久化（20 把 / 85,000 分） ----------')
old_p_end = src.index('        # ---------- 11c. idle 層')
NEW_P = '''        # ---------- 11. 重型武器等級持久化（無限升級） ----------
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

'''
src = src[:old_p_start] + NEW_P + src[old_p_end:]
done += 1
print('  ✓ 持久化段改寫')

# ============ 5. 11c：商店改成武器升級 ============
rep('11c 預設值',
    '''        m0 = page.evaluate("({auto: __game.state.auto, bank: __game.state.bank,"
                           " upg: __game.state.upg, essence: __game.state.essence})")
        check("idle：預設開自動攻擊、點數 0、無升級、無精華",
              m0["auto"] is True and m0["bank"] == 0
              and m0["upg"] == {"dmg": 0, "rate": 0, "coin": 0} and m0["essence"] == 0, str(m0))''',
    '''        m0 = page.evaluate("({auto: __game.state.auto, bank: __game.state.bank,"
                           " upg: __game.state.upg, wlv: __game.state.wlv,"
                           " essence: __game.state.essence})")
        check("idle：預設開自動攻擊、點數 0、武器 0 級、無精華",
              m0["auto"] is True and m0["bank"] == 0 and m0["wlv"] == [0, 0, 0]
              and m0["upg"] == {"rate": 0, "coin": 0} and m0["essence"] == 0, str(m0))''')

rep('11c 買升級',
    '''        buy = page.evaluate("""(() => {
          const before = {bank: __game.state.bank, lv: __game.state.upg.dmg, mult: __game.dmgMult()};
          const ok = __game.buyUpgrade('dmg');
          return {ok, before, cost: __game.upgCost('dmg'),
                  after: {bank: __game.state.bank, lv: __game.state.upg.dmg, mult: __game.dmgMult()}};
        })()""")
        check("idle：買威力會扣點、等級 +1、傷害倍率提高",
              buy["ok"] is True and buy["after"]["lv"] == buy["before"]["lv"] + 1
              and abs(buy["after"]["bank"] - (buy["before"]["bank"] - 80)) < 1e-6
              and buy["after"]["mult"] > buy["before"]["mult"], str(buy))''',
    '''        buy = page.evaluate("""(() => {
          const s = __game.state, cost = __game.wCost(0);
          const before = {bank: s.bank, lv: s.wlv[0], dmg: __game.currentWeapon().damage};
          const ok = __game.buyWeaponUpgrade(0);
          return {ok, cost, before,
                  after: {bank: s.bank, lv: s.wlv[0], dmg: __game.currentWeapon().damage}};
        })()""")
        check("idle：買重錘升級會扣點、等級 +1、傷害倍率提高",
              buy["ok"] is True and buy["after"]["lv"] == buy["before"]["lv"] + 1
              and abs(buy["after"]["bank"] - (buy["before"]["bank"] - buy["cost"])) < 1e-6
              and buy["after"]["dmg"] > buy["before"]["dmg"], str(buy))''')

# ============ 6. 手機 / 640×480 的武器格數 ============
rep('手機 chips', 'check("手機（Pixel 5）：直向版面 + 20 武器列", mv["phase"] == "playing" and mv["chips"] == 20, str(mv))',
    'check("手機（Pixel 5）：直向版面 + 3 把重型武器列", mv["phase"] == "playing" and mv["chips"] == 3, str(mv))')
rep('640 chips', 'and play["chips"] == 20 and play["barTop"] < play["h"], f"{fit} -> {play}")',
    'and play["chips"] == 3 and play["barTop"] < play["h"], f"{fit} -> {play}")')

# ============ 7. 自動攻擊測試裡的 unlocked = 1 ============
rep('自動攻擊 unlocked',
    "          s.score = 0; s.unlocked = 1; s.weaponIndex = 0;   // 用最基本的報紙，確定自動攻擊會擊殺",
    "          s.score = 0; s.unlocked = 3; s.weaponIndex = 0;   // 用重錘，確定自動攻擊會擊殺")

# ============ 8. 檔頭說明與結尾字樣 ============
rep('檔頭說明',
    """涵蓋：100 關（5 章 × 20 關、難度遞增、Boss 每 10 關）、20 把武器（前 8 把機制、
後 12 把新機制：三連/音波/誘餌/磁力/火箭/無人機/全域/冰凍/火焰/冰霧/電網/電漿）、""",
    """涵蓋：無限關卡（1–100 關手寫、之後程序生成，章節循環、每 100 關一階）、
3 把可無限升級的重型武器（重錘／火焰／電漿）、轉生與點數升級、""")

rep('結尾字樣', '100 關 / 100 場景 / 20 武器', '無限關卡 / 100 場景 / 3 把重型武器')

io.open(P, 'w', encoding='utf-8').write(src)
print('完成，共', done, '項')
