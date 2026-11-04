#!/usr/bin/env python3
"""打出 GamePix 可上傳的 ZIP，並驗證結構。

規則：
  - ZIP 根目錄必須直接是 index.html（不能多一層資料夾）
  - 只放遊戲本體（index.html）；README、測試、素材、git 都不進包
  - 唯一允許的外部資源是 GamePix SDK

    python3 build_gamepix.py
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "index.html"
DIST = ROOT / "dist"
ZIP = DIST / "fly-swat-rampage-gamepix.zip"
ALLOWED_HOST = "integration.gamepix.com"


def main() -> int:
    if not SRC.is_file():
        print(f"FAIL: 找不到 {SRC}")
        return 1

    html = SRC.read_text(encoding="utf-8")
    problems: list[str] = []

    if "gamepix.sdk.js" not in html:
        problems.append("index.html 沒有 GamePix SDK script")
    if "GamePixConfig" not in html:
        problems.append("index.html 沒有先設 GamePixConfig（manual lifecycle）")
    for m in re.finditer(r"https?://[^\"' )]+", html):
        url = m.group(0)
        host = re.sub(r"^https?://", "", url).split("/")[0]
        if host != ALLOWED_HOST:
            problems.append(f"外部資源不在白名單：{url}")

    DIST.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(SRC, arcname="index.html")

    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        bad = z.testzip()
    if names != ["index.html"]:
        problems.append(f"ZIP 根目錄結構錯誤：{names}")
    if bad:
        problems.append(f"ZIP 損壞：{bad}")

    print(f"build: {ZIP.relative_to(ROOT)}  {ZIP.stat().st_size // 1024} KB")
    print(f"entries: {names}")
    print(f"index.html: {SRC.stat().st_size // 1024} KB")
    if problems:
        print("FAIL")
        for p in problems:
            print("  -", p)
        return 1
    print("PASS: index.html 在 ZIP 根目錄、只依賴 GamePix SDK、無其他外部連結")
    return 0


if __name__ == "__main__":
    sys.exit(main())
