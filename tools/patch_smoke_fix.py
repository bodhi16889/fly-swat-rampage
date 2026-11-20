#!/usr/bin/env python3
"""修正三個測試問題：音效測試被自動攻擊干擾、轉生斷言寫錯、GP loading 等待。"""
import io, os, sys

P = os.path.expanduser('~/fly-swat-rampage/verify_smoke.py')
src = io.open(P, encoding='utf-8').read()
n = 0

# 1) 音效測試：先關自動攻擊，避免多打一隻造成 voice:kill 計數不是 1
old = """        page.evaluate("__game.audio.log.length = 0; __game.voice.log.length = 0")"""
new = """        page.evaluate("__game.state.auto = false; __game.state.autoT = 0")   # 音效斷言需要只有玩家這一下
        page.evaluate("__game.audio.log.length = 0; __game.voice.log.length = 0")"""
if old in src and new not in src:
    src = src.replace(old, new, 1); n += 1

# 2) 轉生斷言：應該是「重置後倍率 = 1 + 1%×精華」，不是跟轉生前比
old = """              and done["rebirths"] == 1 and done["deepest"] == 0
              and done["mult"] > done["before"] and done["phase"] == "menu", str(done))"""
new = """              and done["rebirths"] == 1 and done["deepest"] == 0
              and abs(done["mult"] - (1 + 0.01 * done["gain"])) < 1e-9
              and done["phase"] == "menu", str(done))"""
if old in src:
    src = src.replace(old, new, 1); n += 1

# 3) 自動攻擊：加上診斷欄位，方便看卡在哪
old = """          const k0 = s.kills;
          await new Promise(r => setTimeout(r, 3000));
          return {k0, k1: s.kills, flies: s.flies.filter(f => !f.dead && !f.friendly).length,
                  interval: __game.autoInterval()};"""
new = """          const k0 = s.kills, f0 = __game.frame;
          await new Promise(r => setTimeout(r, 3000));
          const t = __game.nearestEnemy();
          return {k0, k1: s.kills, flies: s.flies.filter(f => !f.dead && !f.friendly).length,
                  interval: __game.autoInterval(), frames: __game.frame - f0,
                  auto: s.auto, paused: s.paused, phase: s.phase, cool: +s.cool.toFixed(2),
                  autoT: +s.autoT.toFixed(2), lock: +s.weaponLockT.toFixed(2),
                  target: t ? [Math.round(t.x), Math.round(t.y)] : null,
                  weapon: __game.weapon, score: s.score};"""
if old in src:
    src = src.replace(old, new, 1); n += 1

# 4) 重載後等 GP SDK 就緒（否則 loading:100 / loaded 還沒寫進 log）
old = """        page.reload(wait_until="load")
        page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        page.evaluate("__game.startLevel(1, false)")
        kept = page.evaluate("""
new = """        page.reload(wait_until="load")
        page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        page.wait_for_function("__game.gp.log.includes('loaded')", timeout=15_000)
        page.evaluate("__game.startLevel(1, false)")
        wait_frames(page, 3)
        kept = page.evaluate("""
if old in src:
    src = src.replace(old, new, 1); n += 1

io.open(P, 'w', encoding='utf-8').write(src)
print('修正', n, '處')
