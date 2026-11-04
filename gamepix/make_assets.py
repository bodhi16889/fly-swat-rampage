#!/usr/bin/env python3
"""GamePix 上架素材產生器。

輸出（gamepix/assets/）：
  icon-512.png            512×512   遊戲圖示
  cover-1920x1080.png     1920×1080 橫版封面（右側手機 mock）
  screenshots/01..05.png  1080×1920 直向實際遊戲畫面

    python3 gamepix/make_assets.py
"""
from __future__ import annotations

import functools
import http.server
import socketserver
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "gamepix" / "assets"
SHOTS = OUT / "screenshots"


def serve() -> socketserver.TCPServer:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a, **k: None

    class Server(socketserver.TCPServer):
        allow_reuse_address = True

    server = Server(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def wait_ready(page) -> None:
    page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
    page.wait_for_function("getComputedStyle(document.getElementById('modal')).opacity === '0'"
                           " || !document.getElementById('modal').classList.contains('hidden')"
                           " || true", timeout=5_000)


def shot(page, path: Path, wait: float = 1.0) -> None:
    time.sleep(wait)
    page.screenshot(path=str(path))
    print(f"  {path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB")


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    server = serve()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    url = f"{base}/index.html?lang=en"

    with sync_playwright() as p:
        browser = p.chromium.launch(args=[
            "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
            "--autoplay-policy=no-user-gesture-required", "--force-color-profile=srgb",
        ])

        # ---- 遊戲畫面（1920×1080） ----
        # 遊戲是直向設計，用 1080×1920 截圖才不會在大橫屏變成一片空白
        page = browser.new_page(viewport={"width": 540, "height": 960}, device_scale_factor=2)
        page.goto(url, wait_until="load")
        page.wait_for_function("window.__game && window.__game.ready", timeout=30_000)
        time.sleep(1.2)

        # 01 選關卡（用「全破」存檔：★ 與無盡解鎖，比全鎖畫面好看）
        page.evaluate("""(() => {
          for (let i = 1; i <= 100; i++) __game.saveProgress(i);
          __game.addScore(85000 - __game.state.score);
          __game.state.menuChapter = 1;
          __game.showStart();
        })()""")
        shot(page, SHOTS / "01-menu.png", 0.5)

        # 00 封面用主視覺：第 1 關客廳、電蚊拍電弧
        page.evaluate("""(() => {
          __game.startLevel(1, true);
          __game.addScore(1800);
          __game.state.weaponIndex = 3;
          const w = innerWidth, h = innerHeight;
          for (let i = 0; i < 5; i++) __game.spawnFly(w * 0.5 + (i - 2) * 44, h * 0.55 + (i % 2) * 34, 'house');
          __game.state.cool = 0;
          __game.attack(w * 0.5, h * 0.55);
          __game.gp.pause('shot');
          document.getElementById('toast').classList.remove('show');
        })()""")
        page.wait_for_function("getComputedStyle(document.getElementById('modal')).opacity === '0'", timeout=5_000)
        shot(page, SHOTS / "00-hero.png", 0.25)
        page.evaluate("__game.gp.resume('shot')")

        # 02 第 21 關：水果攤場景＋電蚊拍連鎖（先觸發特效再凍結畫面截圖）
        page.evaluate("""(() => {
          __game.startLevel(21, true);         // 重設成新局：1800 分解鎖電蚊拍
          __game.addScore(1800 - __game.state.score);
          __game.state.weaponIndex = 3;
          __game.startLevel(21);
          const cx = innerWidth / 2, cy = innerHeight * 0.45;
          for (let i = 0; i < 5; i++) __game.spawnFly(cx + (i - 2) * 54, cy + (i % 2) * 36);
          __game.state.cool = 0;
          __game.attack(cx, cy);
          __game.gp.pause('shot');
          document.getElementById('toast').classList.remove('show');
        })()""")
        page.wait_for_function("getComputedStyle(document.getElementById('modal')).opacity === '0'", timeout=5_000)
        shot(page, SHOTS / "02-action.png", 0.25)
        page.evaluate("__game.gp.resume('shot')")

        # 03 第 3 關：麵包店防禦（蒼蠅在吃可頌）
        page.evaluate("""(() => {
          __game.startLevel(41);
          for (let i = 0; i < 3; i++) __game.spawnFly(innerWidth * .5, innerHeight * .45, 'gold');
        })()""")
        page.wait_for_function("getComputedStyle(document.getElementById('modal')).opacity === '0'", timeout=5_000)
        shot(page, SHOTS / "03-defend.png", 2.6)

        # 04 第 5 關：蠅王 + 護盾 + 雷射光束（凍結）
        page.evaluate("""(() => {
          __game.addScore(85000 - __game.state.score);
          __game.state.weaponIndex = 7;
          __game.startLevel(10);
          __game.forceSummon();
          __game.boss.x = innerWidth / 2;
          __game.boss.y = innerHeight * 0.42;
          __game.state.cool = 0;
          __game.attack(innerWidth / 2, __game.boss.y);
          __game.gp.pause('shot');
          document.getElementById('toast').classList.remove('show');
        })()""")
        page.wait_for_function("getComputedStyle(document.getElementById('modal')).opacity === '0'", timeout=5_000)
        shot(page, SHOTS / "04-boss.png", 0.25)
        page.evaluate("__game.gp.resume('shot')")

        # 05 無盡模式：全武器解鎖 + 密集蟲群
        page.evaluate("""(() => {
          __game.addScore(85000 - __game.state.score);
          __game.state.weaponIndex = 7;
          __game.startEndless();
          for (let i = 0; i < 14; i++) {
            __game.spawnFly(innerWidth * (0.2 + Math.random() * 0.6),
                            innerHeight * (0.22 + Math.random() * 0.5),
                            i % 3 === 0 ? 'bottle' : 'house');
          }
        })()""")
        page.wait_for_function("getComputedStyle(document.getElementById('modal')).opacity === '0'", timeout=5_000)
        shot(page, SHOTS / "05-endless.png", 0.8)
        page.close()

        # ---- 圖示 512×512 ----
        icon = browser.new_page(viewport={"width": 512, "height": 512})
        icon.goto(f"{base}/gamepix/icon.html", wait_until="load")
        time.sleep(0.5)
        icon.screenshot(path=str(OUT / "icon-512.png"))
        print(f"  gamepix/assets/icon-512.png  {(OUT / 'icon-512.png').stat().st_size // 1024} KB")
        icon.close()

        # ---- 封面 1920×1080（用剛拍的 Boss 畫面合成） ----
        cover = browser.new_page(viewport={"width": 1920, "height": 1080})
        cover.goto(f"{base}/gamepix/cover.html", wait_until="load")
        cover.wait_for_function("document.images.length > 0 && document.images[0].complete", timeout=10_000)
        time.sleep(0.5)
        cover.screenshot(path=str(OUT / "cover-1920x1080.png"))
        print(f"  gamepix/assets/cover-1920x1080.png  {(OUT / 'cover-1920x1080.png').stat().st_size // 1024} KB")
        cover.close()

        browser.close()

    server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
