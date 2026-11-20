#!/usr/bin/env python3
"""修正第二階段改造後的殘留：開局武器索引、重玩解鎖、測試期望值。"""
import io, os

def patch(path, pairs):
    src = io.open(path, encoding='utf-8').read()
    n = 0
    for old, new, cnt in pairs:
        c = src.count(old)
        if c != cnt:
            raise SystemExit(f'✗ {os.path.basename(path)}: 錨點出現 {c} 次（預期 {cnt}）\n{old[:100]}')
        src = src.replace(old, new, cnt)
        n += cnt
    io.open(path, 'w', encoding='utf-8').write(src)
    print(f'{os.path.basename(path)}: 修 {n} 處')

HOME = os.path.expanduser('~')

patch(HOME + '/fly-swat-rampage/index.html', [
    # 開局預設第一把（重錘），不要挑最後一把
    ("state.weaponIndex = state.unlocked - 1;\nrenderWeaponBar();",
     "state.weaponIndex = 0;   // 三把都開，預設拿重錘\nrenderWeaponBar();", 1),
    # 從第 1 關重來：只清分數，武器維持全開
    ("  if (resetRun) { state.score = 0; state.unlocked = 1; state.weaponIndex = 0; saveScore(); }",
     "  if (resetRun) { state.score = 0; state.unlocked = WEAPONS.length; state.weaponIndex = 0; saveScore(); }", 1),
])

patch(HOME + '/fly-swat-rampage/verify_smoke.py', [
    # 1) 無限升級：每次補滿點數，證明沒有等級上限
    ("""          for (let i = 0; i < 200; i++) __game.buyWeaponUpgrade(0);   // 衝到 230 級，證明沒有上限""",
     """          for (let i = 0; i < 200; i++) { s.bank = 1e15; __game.buyWeaponUpgrade(0); }   // 衝到 230 級，證明沒有上限""", 1),
    # 2) 升級效果：改成比較傷害（4 → 11），不假設 Lv0 打不死
    ("""        page.evaluate("__game.state.wlv = [0,0,0]; __game.state.weaponIndex = 0")
        weak = page.evaluate(\"\"\"(() => {
          __game.startLevel(1); __game.flies.length = 0; __game.state.cool = 0;
          const f = __game.spawnFly(300, 400, 'bottle'); f.state = 'rest'; f.restT = 9;
          __game.attack(300, 400);
          return {dmg: __game.currentWeapon().damage, hp: f.hp, dead: !!f.dead};
        })()\"\"\")
        page.evaluate("__game.state.bank = 1e9; for (let i=0;i<6;i++) __game.buyWeaponUpgrade(0)")
        strong = page.evaluate(\"\"\"(() => {
          __game.startLevel(1); __game.flies.length = 0; __game.state.cool = 0;
          const f = __game.spawnFly(300, 400, 'bottle'); f.state = 'rest'; f.restT = 9;
          __game.attack(300, 400);
          return {dmg: __game.currentWeapon().damage, hp: f.hp, dead: !!f.dead};
        })()\"\"\")
        check("升級效果是真的：Lv0 打不死 2HP 綠頭蠅，Lv6 一擊帶走",
              weak["dead"] is False and weak["hp"] > 0
              and (strong["dead"] is True or strong["hp"] <= 0), f"{weak} -> {strong}")""",
     """        page.evaluate("__game.state.wlv = [0,0,0]; __game.state.weaponIndex = 0")
        weak = page.evaluate(\"\"\"(() => {
          __game.startLevel(1); __game.flies.length = 0; __game.state.cool = 0;
          const f = __game.spawnFly(300, 400, 'house'); f.state = 'rest'; f.restT = 9;
          __game.attack(300, 400);
          return {dmg: __game.currentWeapon().damage, hp: f.hp, dead: !!f.dead};
        })()\"\"\")
        page.evaluate("__game.state.bank = 1e9; for (let i=0;i<6;i++) __game.buyWeaponUpgrade(0)")
        strong = page.evaluate(\"\"\"(() => {
          __game.startLevel(1); __game.flies.length = 0; __game.state.cool = 0;
          const f = __game.spawnFly(300, 400, 'house'); f.state = 'rest'; f.restT = 9;
          __game.attack(300, 400);
          return {dmg: __game.currentWeapon().damage, hp: f.hp, dead: !!f.dead};
        })()\"\"\")
        check("升級效果是真的：傷害 4→11、命中即清掉該格蒼蠅",
              weak["dmg"] == 4 and strong["dmg"] > weak["dmg"] * 2
              and (weak["dead"] is True or weak["hp"] <= 0)
              and (strong["dead"] is True or strong["hp"] <= 0), f"{weak} -> {strong}")""", 1),
    # 3) Boss 穿透：電漿炮 bossDamage 10（不是舊雷射的 8）
    ("""        check("電漿炮：穿透護盾削弱 Boss（10 傷 × 等級倍率）", pierce["hp1"] < pierce["hp0"], str(pierce))""",
     """        check("電漿炮：穿透護盾削弱 Boss（每級 +30%，至少 10 傷）",
              pierce["hp1"] <= pierce["hp0"] - 10, str(pierce))""", 1),
    # 4) 力竭雙倍傷害：改成相對當前武器傷害
    ("""          __game.state.weaponIndex = 0; __game.state.cool = 0;
          const hp0 = b.hp;
          __game.attack(b.x, b.y);
          return {hp0, hp1: b.hp, exhaust: b.exhaustT};""",
     """          __game.state.weaponIndex = 0; __game.state.cool = 0;
          const hp0 = b.hp, dmg = __game.currentWeapon().damage;
          __game.attack(b.x, b.y);
          return {hp0, hp1: b.hp, exhaust: b.exhaustT, dmg};""", 1),
    ("""        check("力竭期間受到雙倍傷害（1 傷 → 2）", crit["hp0"] - crit["hp1"] == 2, str(crit))""",
     """        crit_dmg = crit["hp0"] - crit["hp1"]
        check("力竭期間受到雙倍傷害", crit_dmg >= 2 * crit["dmg"] - 1,
              f\"{crit} → 實際 {crit_dmg}\")""", 1),
    # 5) 轉生後 upg 只剩 rate/coin
    ("""              and done["upg"] == {"dmg": 0, "rate": 0, "coin": 0}""",
     """              and done["upg"] == {"rate": 0, "coin": 0}""", 1),
    # 6) 買武器升級：明確指定第一把
    ("""        buy = page.evaluate(\"\"\"(() => {
          const s = __game.state, cost = __game.wCost(0);""",
     """        buy = page.evaluate(\"\"\"(() => {
          const s = __game.state; s.weaponIndex = 0; s.wlv = [0, 0, 0];
          const cost = __game.wCost(0);""", 1),
    # 7) 語言測試：武器名改成重錘
    ("""              and zhst["h1"] == "Fly Swatter" and "\\u5831\\u7d19" in zhst["chip"]""",
     """              and zhst["h1"] == "Fly Swatter" and "\\u91cd\\u9318" in zhst["chip"]""", 1),
    ("""              and "lang=zh" in zh["url"] and "\\u5831\\u7d19" in zh["chip"],""",
     """              and "lang=zh" in zh["url"] and "\\u91cd\\u9318" in zh["chip"],""", 1),
])
