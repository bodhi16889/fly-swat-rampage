#!/usr/bin/env python3
"""打出 GamePix 可上傳的 ZIP，並驗證結構。

規則：
  - ZIP 根目錄必須直接是 index.html（不能多一層資料夾）
  - 只放遊戲本體（index.html）；README、測試、素材、git 都不進包
  - 允許的外部資源：GamePix SDK、自家排行榜 API（預設關閉）

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
ALLOWED_HOSTS = {
    "integration.gamepix.com",
    "fly-swat-lb.chenkaiting18.workers.dev",  # 自家排行榜 API，預設關閉
}
# 送審包只留 GamePix SDK：自家排行榜 Worker 需事先向 GamePix 申報才能留，
# 未申報前一律清空 LB_URL（預設 default=false 本來就不會呼叫）。
SUBMISSION_ALLOWED_HOSTS = {"integration.gamepix.com"}


def make_submission_html(html: str, problems: list[str]) -> str:
    """送審版：把 LB_URL 清成空字串，確保 ZIP 內不殘留任何自家後端網址。"""
    if "LB_ENABLED_DEFAULT" not in html:
        problems.append("index.html 找不到 LB_ENABLED_DEFAULT（預期預設關閉）")
    out, n = re.subn(r"(LB_URL\s*=\s*)'https?://[^']*'", r"\1''", html)
    if n == 0 and "LB_URL" in html:
        problems.append("LB_URL 存在但無法清空（格式改變？）")
    return out


def check_urls(html: str, hosts: set[str], label: str, problems: list[str]) -> None:
    for m in re.finditer(r"https?://[^\"' )]+", html):
        url = m.group(0)
        host = re.sub(r"^https?://", "", url).split("/")[0]
        if host not in hosts:
            problems.append(f"{label} 外部資源不在白名單：{url}")


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
    check_urls(html, ALLOWED_HOSTS, "頁面版", problems)
    if "LB_ENABLED_DEFAULT = false" not in html:
        problems.append("LB_ENABLED_DEFAULT 不是 false（全球榜應預設關閉）")

    sub_html = make_submission_html(html, problems)
    check_urls(sub_html, SUBMISSION_ALLOWED_HOSTS, "送審版", problems)

    DIST.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("index.html", sub_html)

    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        bad = z.testzip()
        packed = z.read("index.html").decode("utf-8")
    if names != ["index.html"]:
        problems.append(f"ZIP 根目錄結構錯誤：{names}")
    if bad:
        problems.append(f"ZIP 損壞：{bad}")
    check_urls(packed, SUBMISSION_ALLOWED_HOSTS, "ZIP", problems)
    if "LB_URL = ''" not in packed:
        problems.append("ZIP 內 LB_URL 未清空")

    page_lb = re.search(r"LB_URL\s*=\s*'([^']*)'", html)
    zip_lb = re.search(r"LB_URL\s*=\s*'([^']*)'", packed)
    print(f"build: {ZIP.relative_to(ROOT)}  {ZIP.stat().st_size // 1024} KB")
    print(f"entries: {names}")
    print(f"index.html: {SRC.stat().st_size // 1024} KB")
    print(f"LB_URL → 頁面版: {page_lb.group(1) if page_lb else '(none)'!r} | 送審版: {zip_lb.group(1) if zip_lb else '(none)'!r}")

    if problems:
        print("FAIL")
        for p in problems:
            print("  -", p)
        return 1
    print("PASS: ZIP 根目錄只有 index.html、外部資源僅 GamePix SDK、LB_URL 已清空（不需向 GamePix 申報自家後端）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
