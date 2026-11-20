#!/usr/bin/env python3
"""截圖檢查：選單（升級商店＋轉生）與遊戲中 HUD。"""
import sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path.home() / 'fly-swat-rampage'
url = (root / 'index.html').as_uri()
out = root / 'artifacts'
out.mkdir(exist_ok=True)
SA = ['--use-gl=swiftshader', '--enable-unsafe-swiftshader']

with sync_playwright() as pw:
    b = pw.chromium.launch(args=SA)
    for name, vp, lang in (('idle-menu-640', {'width': 640, 'height': 480}, 'zh'),
                           ('idle-menu-desktop', {'width': 1000, 'height': 760}, 'zh')):
        ctx = b.new_context(viewport=vp)
        p = ctx.new_page()
        p.goto(url + ('?lang=zh' if lang == 'zh' else ''), wait_until='load')
        p.wait_for_function('window.__game && window.__game.ready', timeout=30000)
        # 造一點點數與進度，讓商店有得看
        p.evaluate("""() => {
          const s = __game.state;
          s.deepest = 24; s.score = 12000; s.bank = 640;
          s.upg = {dmg: 3, rate: 1, coin: 0}; s.essence = 12; s.rebirths = 2;
          __game.saveMeta();
          __game.showStart ? __game.showStart() : 0;
          if (typeof showStart === 'function') showStart();
        }""")
        time.sleep(0.6)
        p.screenshot(path=str(out / f'{name}.png'))
        print('拍下', name)

    # 遊戲中 HUD（點數＋自動鍵）
    ctx = b.new_context(viewport={'width': 640, 'height': 480})
    p = ctx.new_page()
    p.goto(url + '?lang=zh', wait_until='load')
    p.wait_for_function('window.__game && window.__game.ready', timeout=30000)
    p.evaluate("__game.state.bank = 1280; __game.startLevel(6, false)")
    time.sleep(2.5)
    p.screenshot(path=str(out / 'idle-playing-640.png'))
    print('拍下 idle-playing-640')
    b.close()
