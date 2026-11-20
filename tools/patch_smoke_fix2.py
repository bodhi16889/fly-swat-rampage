#!/usr/bin/env python3
"""第二輪修正：印出自動攻擊診斷、持久化檢查改在選單狀態下讀。"""
import io, os

P = os.path.expanduser('~/fly-swat-rampage/verify_smoke.py')
src = io.open(P, encoding='utf-8').read()
n = 0

old = """        check("自動攻擊：完全不點擊也會自己清掉蒼蠅",
              auto_on["k1"] > auto_on["k0"] and auto_on["interval"] <= 1.25,
              f"kills {auto_on['k0']} -> {auto_on['k1']}, interval={auto_on['interval']:.2f}s, 場上 {auto_on['flies']}")"""
new = """        check("自動攻擊：完全不點擊也會自己清掉蒼蠅",
              auto_on["k1"] > auto_on["k0"] and auto_on["interval"] <= 1.25,
              f"kills {auto_on['k0']} -> {auto_on['k1']}, interval={auto_on['interval']:.2f}s, {auto_on}")"""
if old in src:
    src = src.replace(old, new, 1); n += 1

old = """        page.wait_for_function("__game.gp.log.includes('loaded')", timeout=15_000)
        page.evaluate("__game.startLevel(1, false)")
        wait_frames(page, 3)
        kept = page.evaluate("({essence: __game.state.essence, rebirths: __game.state.rebirths,"
                             " score: __game.state.score, mult: __game.dmgMult()})")
        check("idle：精華／轉生次數重載後仍保留、分數歸零",
              kept["essence"] == done["gain"] and kept["rebirths"] == 1
              and kept["score"] == 0 and kept["mult"] > 1.0, str(kept))"""
new = """        page.wait_for_function("__game.gp.log.includes('loaded')", timeout=15_000)
        kept = page.evaluate("({essence: __game.state.essence, rebirths: __game.state.rebirths,"
                             " score: __game.state.score, mult: __game.dmgMult()})")
        check("idle：精華／轉生次數重載後仍保留、分數歸零",
              kept["essence"] == done["gain"] and kept["rebirths"] == 1
              and kept["score"] == 0 and kept["mult"] > 1.0, str(kept))
        page.evaluate("__game.startLevel(1, false)")
        wait_frames(page, 3)"""
if old in src:
    src = src.replace(old, new, 1); n += 1

io.open(P, 'w', encoding='utf-8').write(src)
print('修正', n, '處')
