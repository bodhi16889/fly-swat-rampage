#!/usr/bin/env python3
"""把 idle 層（轉生／自動攻擊／分數升級）的 E2E 斷言插進 verify_smoke.py。可重複執行。"""
import io, os, sys

P = os.path.expanduser('~/fly-swat-rampage/verify_smoke.py')
src = io.open(P, encoding='utf-8').read()

ANCHOR = """        # ---------- 12. GamePix SDK（生命週期／暫停／廣告／復活／續命／無 SDK） ----------"""

NEW = '''        # ---------- 11c. idle 層：轉生 / 自動攻擊 / 分數升級 ----------
        page.evaluate("try { ['fly.swat.meta','fly.swat.score','fly.swat.progress']"
                      ".forEach(k => localStorage.removeItem(k)); } catch (e) {}")
        page.reload(wait_until="load")
        page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        wait_frames(page, 5)

        m0 = page.evaluate("({auto: __game.state.auto, bank: __game.state.bank,"
                           " upg: __game.state.upg, essence: __game.state.essence})")
        check("idle：預設開自動攻擊、點數 0、無升級、無精華",
              m0["auto"] is True and m0["bank"] == 0
              and m0["upg"] == {"dmg": 0, "rate": 0, "coin": 0} and m0["essence"] == 0, str(m0))

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
          const before = {bank: __game.state.bank, lv: __game.state.upg.dmg, mult: __game.dmgMult()};
          const ok = __game.buyUpgrade('dmg');
          return {ok, before, cost: __game.upgCost('dmg'),
                  after: {bank: __game.state.bank, lv: __game.state.upg.dmg, mult: __game.dmgMult()}};
        })()""")
        check("idle：買威力會扣點、等級 +1、傷害倍率提高",
              buy["ok"] is True and buy["after"]["lv"] == buy["before"]["lv"] + 1
              and abs(buy["after"]["bank"] - (buy["before"]["bank"] - 80)) < 1e-6
              and buy["after"]["mult"] > buy["before"]["mult"], str(buy))

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
          __game.startLevel(1, false);
          const k0 = s.kills;
          await new Promise(r => setTimeout(r, 3000));
          return {k0, k1: s.kills, flies: s.flies.filter(f => !f.dead && !f.friendly).length,
                  interval: __game.autoInterval()};
        }""")
        check("自動攻擊：完全不點擊也會自己清掉蒼蠅",
              auto_on["k1"] > auto_on["k0"] and auto_on["interval"] <= 1.25,
              f"kills {auto_on['k0']} -> {auto_on['k1']}, interval={auto_on['interval']:.2f}s, 場上 {auto_on['flies']}")

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
              and done["upg"] == {"dmg": 0, "rate": 0, "coin": 0}
              and done["essence"] == done["gain"] and done["saved"] == done["gain"]
              and done["rebirths"] == 1 and done["deepest"] == 0
              and done["mult"] > done["before"] and done["phase"] == "menu", str(done))

        page.reload(wait_until="load")
        page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        page.evaluate("__game.startLevel(1, false)")
        kept = page.evaluate("({essence: __game.state.essence, rebirths: __game.state.rebirths,"
                             " score: __game.state.score, mult: __game.dmgMult()})")
        check("idle：精華／轉生次數重載後仍保留、分數歸零",
              kept["essence"] == done["gain"] and kept["rebirths"] == 1
              and kept["score"] == 0 and kept["mult"] > 1.0, str(kept))

'''

if '11c. idle 層' in src:
    print('已套用，跳過')
    sys.exit(0)
if src.count(ANCHOR) != 1:
    raise SystemExit(f'✗ 錨點出現 {src.count(ANCHOR)} 次')
src = src.replace(ANCHOR, NEW + ANCHOR, 1)

# 更新結尾 RESULT 說明
old_res = '本機 PB / 全球榜 / GamePix SDK / 手機 / 640×480'
new_res = '本機 PB / 全球榜 / 轉生 / 自動攻擊 / 分數升級 / GamePix SDK / 手機 / 640×480'
if old_res in src:
    src = src.replace(old_res, new_res, 1)

io.open(P, 'w', encoding='utf-8').write(src)
print('✓ 已插入 11c 共 8 項新斷言')
