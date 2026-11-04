# 打擊蒼蠅大作戰 · Fly Swat Rampage — **V4（8 武器 · 5 關 · 無盡模式）**

手機 H5 單指觸控打蒼蠅遊戲。**單一 `index.html`、零依賴、Canvas 2D + Web Audio 合成音效 + SAPI 人聲**，
直向滿版（`viewport-fit=cover` + `touch-action: none`），手機瀏覽器打開就能玩。

> 🌐 線上版：<https://bodhi16889.github.io/fly-swat-rampage/>
> 另有 Three.js 3D 作品：[台北機甲拆除模擬器](https://bodhi16889.github.io/mech-taipei-h5/)

## 玩法

| 操作 | 說明 |
| :--- | :--- |
| 點擊 / 輕觸 | 依當前武器判定（單點 / AOE / 扇形 / 陷阱 / 射線） |
| 長按滑動 | 殺蟲噴霧：按住連續噴出毒霧 |
| 底部武器列 | 已解鎖的 8 把武器常駐，可隨時點選切換 |
| 選關卡 | 開場卡片可選已解鎖關卡；通過第 5 關解鎖無盡模式 |

## 武器（V4：8 把，雙分支）

**精準爆發流**：報紙 → 塑膠拍 → 黏蠅紙 → 鹽槍　　**範圍清場流**：電蚊拍 → 噴霧 → 雙持電拍 → 雷射

| # | 武器 | 解鎖 | 判定 | CD | 機制 |
| --: | :--- | --: | :--- | --: | :--- |
| 1 | 📰 捲起來的報紙 | 初始 | 40 px 單點 | 0.35s | 單體最近，空拍無懲罰 |
| 2 | 🏓 塑膠蒼蠅拍 | 400 | 70 px 單點 | 0.25s | 範圍更大＋網狀波紋粒子 |
| 3 | 🪤 黏蠅紙陷阱板 | 1,000 | 120 px 延時區 | 1.20s | 放置 4 秒黏紙；路過蒼蠅**定身 2 秒**且受到 **1.5 倍傷害** |
| 4 | ⚡ 電蚊拍 | 1,800 | 100 px AOE | 0.20s | 命中後**連鎖閃電**跳到最近 2 隻 |
| 5 | 🧂 散彈鹽槍 | 3,000 | 60° / 180 px 扇形 | 0.45s | 槍口＝點擊點、朝畫面中心噴；**扇心 3 傷、扇緣 1 傷** |
| 6 | 🧴 強效殺蟲噴霧 | 4,500 | 160 px 持續 | 0.20s | 毒霧 1.5 秒，**每 0.3 秒扣 1 血** |
| 7 | ⚡⚡ 雙持高壓電蚊拍 | 6,500 | 雙點各 90 px | 0.15s | 點擊左右各一次電爆（清密集蟲群） |
| 8 | 🔫 終極除蟲雷射炮 | 9,000 | 80 px 帶狀 | 0.80s | **穿透護盾/障礙**，一般蟲秒殺、Boss 8 傷（力竭雙倍） |

## 關卡（5 關 + 無盡）

| 關 | 場景 | 時間 | 通關條件 | 新機制 |
| --: | :--- | --: | :--- | :--- |
| 1 | 夏日客廳的西瓜切片 | 40s | 500 分 | 蒼蠅停在西瓜上搓腳 → 擊殺**雙倍分數** |
| 2 | 熱鬧的傳統菜市場 | 50s | 擊殺 35 隻 | 空拍 >8 失敗；綠頭蠅 2HP、被打就狂暴加速；果蠅群 5–8 隻整團直線穿越 |
| 3 | 麵包店的櫥窗保衛戰 | 60s | 守住可頌 60s | **防禦模式**：蒼蠅主動飛向可頌，抵達即 `eating`、每隻每秒扣 5 衛生度（100 起）；金斑麗蠅靜止時幾乎隱形（alpha 0.2） |
| 4 | 戶外露營區的野餐墊 | 60s | 擊殺 50 隻 | **干擾陷阱**：蜜蜂是友軍，誤擊 −200 分＋武器凍結 1 秒，>2 次失敗；每 15 秒**突風**把蒼蠅掃向一側 |
| 5 | 後巷廚餘桶的決戰 | 90s | 擊敗蠅王（80 HP）| **二階段**：P1「蒼蠅風暴」召喚 10 隻護盾子嗣（清光才能傷到王）；P2（≤50%）眼紅、速度 ×1.5、解鎖「音速俯衝」，衝完**力竭 2 秒受傷雙倍** |
| ∞ | 無盡狂暴模式 | 無上限 | 容錯 20 次空拍 | 刷新速度隨時間上升、每 60 秒迷你蠅王、Combo 統計、**本機排行（存活秒數）** |

## 音效與人聲（V2 / V3）

- 分層音效：`swing`（出手）→ `hit`（命中未死）→ `kill`（擊殺，60ms 限流）→ `bossDown`（Boss 倒下專屬，0.42s 後才進勝利動機）。
- 人聲（Windows SAPI `Microsoft Hanhan zh-TW` 預先合成、base64 內嵌）：擊殺喊「什麼意思」、擊倒蠅王喊「你有病喔」；320ms 限流避免多殺疊音。
- 母帶：`master 0.4 → DynamicsCompressor(-18dB/ratio 6)`；右上角 🔊/🔇 一鍵靜音（`localStorage` 記憶），靜音時人聲與音效都不播。

## 快速啟動

```powershell
cd C:\node24\fly-swat-rampage
python -m http.server 8099          # 8099 被佔用時改 8787
# 開 http://127.0.0.1:8099/index.html
```

> 不要用 8080（本機被 java 服務佔用，會 `WinError 10013`）。
> 直接雙擊 `index.html`（`file://`）也能跑：沒有外部圖檔／音檔、沒有 fetch。
> 手機測試：`ipconfig | findstr /i IPv4` → 手機開 `http://<IP>:8099/index.html`；
> 公司 Wi-Fi 常有 client isolation，連不到就用線上版或開 Windows 行動熱點。

## 驗證（Playwright，可重跑）

```powershell
python verify_smoke.py                                  # 本機，自動選空閒埠
python verify_smoke.py --headed                         # 想看畫面
python verify_smoke.py --base-url https://bodhi16889.github.io/fly-swat-rampage/index.html
```

覆蓋範圍（48 項檢查）：

- 版面 / 主循環 / 選關卡（5 關 + 無盡未解鎖）/ 8 武器列
- 武器門檻 `[0,400,1000,1800,3000,4500,6500,9000]`
- 每把武器機制：黏蠅紙定身＋1.5 倍易傷、電蚊拍 AOE＋連鎖（3 隻）、鹽槍扇心 3 傷／扇緣 1 傷、
  噴霧毒霧 tick、雙持左右兩擊、雷射穿透清場
- 擊殺計數（第 2/4 關目標）
- 第 3 關：可頌衛生度被 `eating` 扣血、守住 60 秒通關
- 第 4 關：誤擊蜜蜂 −200＋武器凍結（凍結期間無法出擊）、突風物件
- 第 5 關：80 HP、護盾 10 隻時 Boss 免疫、雷射穿透 −8、Phase 2 俯衝後力竭、
  力竭期間 1 傷實扣 2、通關寫入進度並解鎖無盡
- 無盡：存活計時、迷你蠅王、容錯用完寫入排行
- 音效分層＋人聲（擊殺／蠅王）＋靜音完全靜音
- 手機 Pixel 5：直向版面、8 武器列、觸控拍打計分
- 全程無 console / page error

最近一次結果：

```
[PASS] V4：8 把武器 + 5 個關卡 + 無盡（未解鎖） / 武器解鎖門檻符合規格 / 底部常駐 8 個武器切換鈕
[PASS] 擊殺音效分層 + 人聲 / 空拍計入失誤
[PASS] 黏蠅紙：定身 2 秒 / 受 1.5 倍傷害（2HP → 0.5）
[PASS] 電蚊拍：AOE + 連鎖閃電（3 隻） / 擊殺計數會累加
[PASS] 鹽槍：扇心 3 傷打死、扇緣只 1 傷 — {'centre': -4, 'edge': 1}
[PASS] 噴霧：毒霧每 0.3 秒結算、2HP 被打死
[PASS] 雙持：左右兩側各一次電爆 / 雷射：80px 帶狀穿透清場
[PASS] 第 3 關：可頌衛生度滿、含偽裝金斑麗蠅 / 蒼蠅抵達可頌後 eating 扣血 / 守住 60 秒通關
[PASS] 誤擊蜜蜂：-200 分、武器凍結 1 秒 / 凍結期間無法出擊 / 突風
[PASS] 第 5 關：蠅王 80 HP、體積 4 倍
[PASS] Phase 1：召喚 10 隻護盾，護盾期間 Boss 免疫 — {'shield': 10, 'hp0': 80, 'hp1': 80}
[PASS] 雷射：穿透護盾削弱 Boss（8 傷） — {'hp0': 80, 'hp1': 72}
[PASS] Phase 2：HP ≤ 50% 狂暴、俯衝後力竭 2 秒
[PASS] 力竭期間受到雙倍傷害（1 傷 → 2） — {'hp0': 32, 'hp1': 30}
[PASS] Boss 倒下 → 通關並存進度（解鎖無盡） / 擊倒蠅王有人聲「你有病喔」
[PASS] 通關第 5 關後解鎖無盡模式 / 無盡模式啟動 / 迷你蠅王會出現 / 容錯用完寫入排行
[PASS] 靜音：音效與人聲都不播
[PASS] 手機（Pixel 5）：直向版面 + 8 武器列 / 手機觸控拍打計分
RESULT: PASS
```

截圖：`artifacts/fly-v4-mobile.png`、`fly-v4-desktop.png`、`fly-v4-menu.png`（選關卡）

## 程式結構（都在 `index.html`）

| 區塊 | 內容 |
| :--- | :--- |
| 1 / 1b | `Sfx`（分層音效＋壓縮器＋靜音）、`Voice`（內嵌 SAPI 人聲） |
| 2 | `WEAPONS`（8）、`FLY_TYPES`（8 種含蜜蜂/金斑/迷你王）、`LEVELS`（5）、`ENDLESS_CFG` |
| 3 | `state`：分數、解鎖、陷阱、毒霧、可頌、蜜蜂、突風、Combo、無盡計時 |
| 4 | `Fly`：遊走／停歇／定身／`targetPos`→`eating`／偽裝透明度／Boss 二階段／俯衝／力竭 |
| 5 | 分數、解鎖、進度存檔（`localStorage`）、無盡排行 |
| 6 | `attack()` 七種模式分派 → `tapStrike`（單點/AOE/連鎖/雙持）、`fireSalt`、`placeTrap`、`spawnCloud`、`fireLaser`、`damageFly`（易傷/護盾/階段集中處理） |
| 7 | 粒子與特效（環、電弧、扇形、文字、閃光） |
| 8 | 5 種程序化場景（客廳／菜市場／麵包店櫥窗／露營草地／雨夜後巷） |
| 9 | 蒼蠅繪製（蜜蜂條紋、金斑偽裝、Boss 護盾與 Phase 2 眼紅） |
| 10 | `update()`：生成、突風、毒霧 tick、陷阱、可頌扣血、護盾環繞、目標判定、無盡節奏 |
| 11 | HUD（倒數/進度/可頌衛生度/Boss/Combo）、選關卡、結算、無盡排行 |
| 12–14 | 輸入（Pointer Events）、繪製、啟動與 `window.__game` 測試鉤子 |

測試鉤子：`startLevel(n)`、`startEndless()`、`showStart()`、`addScore(n)`、`spawnFly(x,y,type)`、
`spawnBee()`、`forceSummon()`、`forceDive()`、`forceExhaust(t)`、`forceGust()`、`forcePhase2()`、
`setTimeLeft(t)`、`attack(x,y)`，以及 `state / flies / boss / defend / traps / clouds / effects / weapon / progress / board / frame / audio / voice`。

## 發佈到 GitHub Pages

```powershell
# token：%LOCALAPPDATA%\mech-taipei-tunnel\gh-token.txt（repo 外，一行 PAT）
.\publish-pages.ps1 -Owner bodhi16889 -Repo fly-swat-rampage
.\publish-pages.ps1 -DryRun      # 只看要上傳哪些檔案
```

## 已知限制

- 沒有 Service Worker（離線需自行加）；沒有雲端排行榜（只有本機 `localStorage` top 5）。
- 命中判定：單點類取最近一隻；蜜蜂只對「點擊類」武器有懲罰（噴霧／雷射會自動跳過友軍）。
- 鹽槍扇形以「點擊點 → 畫面中心」定向，點在正中央時預設朝上。
- 佈景為程序化繪製（無圖檔）；要換美術可把 `drawBackground()` 換成貼圖。
