#!/usr/bin/env python3
"""探測：自動攻擊為什麼沒擊殺。"""
import sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

url = (Path.home() / 'fly-swat-rampage' / 'index.html').as_uri()
with sync_playwright() as pw:
    b = pw.chromium.launch(args=['--use-gl=swiftshader', '--enable-unsafe-swiftshader'])
    ctx = b.new_context(viewport={'width': 900, 'height': 700})
    p = ctx.new_page()
    errs = []
    p.on('pageerror', lambda e: errs.append(str(e)))
    p.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' else None)
    p.goto(url, wait_until='load')
    p.wait_for_function('window.__game && window.__game.ready', timeout=30000)
    p.evaluate("try{localStorage.clear()}catch(e){}")
    p.reload(wait_until='load')
    p.wait_for_function('window.__game && window.__game.ready', timeout=30000)

    p.evaluate("""() => {
      window.__calls = [];
      const orig = window.attack;
      window.attack = function (x, y) { window.__calls.push([Math.round(x), Math.round(y)]); return orig(x, y); };
      const s = __game.state;
      s.auto = true; s.autoT = 0;
      __game.startLevel(1, false);
    }""")
    print('開局:', p.evaluate("({auto: __game.state.auto, phase: __game.state.phase, flies: __game.state.flies.length})"))
    time.sleep(3.2)
    print('3.2 秒後:', p.evaluate("""({
      autoT: +__game.state.autoT.toFixed(2), cool: +__game.state.cool.toFixed(2),
      kills: __game.state.kills, calls: window.__calls.length, sample: window.__calls.slice(0, 5),
      nearest: (() => { const f = __game.nearestEnemy(); return f ? [Math.round(f.x), Math.round(f.y), f.hp, f.dead] : null; })(),
      flies: __game.state.flies.map(f => [Math.round(f.x), Math.round(f.y), f.hp, f.dead ? 'dead' : 'alive']).slice(0, 6),
      frame: __game.frame
    })"""))
    print('錯誤:', errs[:5])
    b.close()
