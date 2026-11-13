#!/usr/bin/env python3
"""驗證 GamePix 送審包：只有 index.html、不含自家後端網址、LB_URL 已清空。

CI 用（也刻意可在本機直接跑）：`python tools/assert_submission_zip.py [zip 路徑]`
失敗時以非 0 結束並印出原因。
"""
from __future__ import annotations

import glob
import sys
import zipfile

DEFAULT = "dist/fly-swat-rampage-gamepix.zip"
ALLOWED_HOST = "integration.gamepix.com"
FORBIDDEN_SUBSTR = ("workers.dev", "fly-swat-lb")


def main(argv):
    path = argv[1] if len(argv) > 1 else None
    if not path:
        found = glob.glob(DEFAULT)
        if not found:
            print(f"FAIL 找不到 {DEFAULT}（先跑 build_gamepix.py）")
            return 2
        path = found[0]

    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        bad = z.testzip()
        if bad:
            print(f"FAIL zip 損壞於 {bad}")
            return 1
        if names != ["index.html"]:
            print(f"FAIL zip 根目錄必須只有 index.html，實際：{names}")
            return 1
        html = z.read("index.html").decode("utf-8", errors="replace")

    problems = []
    if "LB_URL" not in html:
        problems.append("找不到 LB_URL 設定（送審版必須顯式清空而不是移除）")
    for s in FORBIDDEN_SUBSTR:
        if s in html:
            problems.append(f"含自家後端字串「{s}」——送審版不得出現")

    hosts = sorted({h for h in __import__("re").findall(r"https?://([\w.-]+)", html)})
    extra = [h for h in hosts if h != ALLOWED_HOST]
    if extra:
        problems.append(f"外部網址超出白名單：{extra}（只允許 {ALLOWED_HOST}）")

    if problems:
        for p in problems:
            print(f"FAIL {p}")
        return 1

    print(f"PASS {path}")
    print(f"     內容：{names}｜外部網址：{hosts or '（無）'}｜testzip：OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
