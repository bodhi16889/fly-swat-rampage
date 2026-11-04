# 打擊蒼蠅大作戰 · Fly Swat Rampage

手機 H5 單指觸控打蒼蠅遊戲。**單一 `index.html`、零依賴、Canvas 2D + Web Audio 即時合成音效**，
直向滿版（`viewport-fit=cover` + `touch-action: none`），用手機瀏覽器打開就能玩。

> 🌐 線上版：<https://bodhi16889.github.io/fly-swat-rampage/>
> （另有 Three.js 3D 作品：[台北機甲拆除模擬器](https://bodhi16889.github.io/mech-taipei-h5/)）

## 玩法

| 操作 | 說明 |
| :--- | :--- |
| 點擊 / 輕觸 | 拍打（依當前武器的判定半徑） |
| 長按滑動 | 只有「殺蟲噴霧」需要：按住拖曳連續噴射毒霧 |
| 底部武器列 | 已解鎖的武器可隨時點選切換 |

## 武器（依累積分數解鎖）

| 武器 | 解鎖分數 | 判定 | CD | 行為 |
| :--- | ---: | :--- | ---: | :--- |
| 📰 捲起來的報紙 | 初始 | 40 px | 0.35s | 單體，最近的一隻 |
| 🏓 傳統塑膠蒼蠅拍 | 500 | 70 px | 0.25s | 單體、範圍更大，附網格震動 |
| ⚡ 電蚊拍 | 1,500 | 110 px | 0.20s | **AOE**：範圍內所有蒼蠅一起電死（藍色電弧） |
| 🧴 強效殺蟲噴霧 | 3,500 | 160 px | 0.10s | 按住連發，毒霧滯留 1.7 秒持續扣血 |
| 🔫 終極除蟲雷射炮 | 7,000 | 全螢幕 | 1.0s | 以點擊高度為準，橫貫畫面掃掉整排（含殘影／灰化） |

## 關卡

| 關 | 場景 | 時間 | 通關條件 | 特殊機制 |
| :-- | :--- | ---: | :--- | :--- |
| 1 | 夏日客廳的西瓜切片 | 40s | 600 分 | 蒼蠅偶爾停在西瓜上搓腳 → 擊殺**分數雙倍** |
| 2 | 熱鬧的傳統菜市場 | 50s | 擊殺 40 隻 | 空拍超過 10 次即失敗；綠頭大蒼蠅 2 HP（被打中會慌亂加速）；果蠅群 5–8 隻成群高速移動 |
| 3 | 後巷的廚餘垃圾桶 | 60s | 擊敗蠅王（50 HP）| Boss 體積 4 倍、25% 機率超音速閃避瞬移、每 10 秒召喚 5–7 隻子嗣；施放後**僵直 1.5 秒，受傷雙倍** |

結算彈窗提供「重新挑戰」／「下一關」／（全破）「再玩一次」。

## 快速啟動

```powershell
cd C:\node24\fly-swat-rampage
python -m http.server 8099          # 或 python -m http.server 8787（8099 被佔用時）
# 開 http://127.0.0.1:8099/index.html
```

> 不要用 8080（本機被 java 服務佔用會 `WinError 10013`）。直接雙擊 `index.html` 用 `file://` 也能跑
> （沒有任何外部資源與 fetch），但 touch/pointer 行為在 http 下較一致，建議用 server。
>
> 用手機測：`ipconfig | findstr /i IPv4` 取區網 IP → 手機開 `http://<IP>:8099/index.html`。
> 公司 Wi-Fi 常有 client isolation，連不到就改開 **Windows 行動熱點**（手機連 PC）或直接玩線上版。

## 驗證（Playwright，可重跑）

```powershell
python verify_smoke.py                                # 本機檔案，自動選空閒埠
python verify_smoke.py --headed                       # 想看畫面
python verify_smoke.py --base-url https://bodhi16889.github.io/fly-swat-rampage/index.html
```

檢查項目（節錄）：

- 版面：canvas 依 DPR 滿版、`touch-action: none`、主循環持續推進
- 蒼蠅：會遊走、會進入停歇狀態
- 打擊：點擊命中 → 得分 + 死亡動畫 + 粒子；空拍 → 失誤數 +1
- 武器：500/1500/3500/7000 分依序解鎖並自動切換、升級提示動畫；電蚊拍一次電死 3 隻（含電弧）、
  噴霧長按產生毒霧並以 DoT 打死 2 HP 綠頭蠅、雷射一次掃掉整排（含殘影）
- 關卡：第 2 關顯示「擊殺 / 空拍」進度且空拍 >10 立即失敗；重新挑戰回到同一關
- Boss：50 HP、體積 4 倍、召喚 5–7 隻子嗣並僵直 1.5 秒、僵直期 1 點傷害實扣 2 血、歸零後通關
- 流程：第 1 關 600 分達標 → 通關 → 「下一關」真的進第 2 關
- 手機：Pixel 5（觸控、393×727）以 `touchscreen.tap` 開始遊戲並拍中蒼蠅計分
- 全程沒有 console / page error；截圖 `artifacts/fly-mobile.png`、`artifacts/fly-desktop.png`

最近一次結果：

```
[PASS] 開始遊戲 → 進入第 1 關 / 場上已有蒼蠅 / 蒼蠅會遊走或進入停歇
[PASS] 點擊命中 → 得分 / 死亡動畫 + 粒子特效 / 空拍會計入失誤次數
[PASS] 500 分 → 塑膠拍（含升級提示動畫）
[PASS] 電蚊拍一次電死範圍內多隻（含電弧特效） {'dead': 3, 'zaps': 3}
[PASS] 噴霧長按產生毒霧並持續扣血 {'clouds': 13, 'hp': -9}
[PASS] 雷射一次掃掉整排蒼蠅（含雷射殘影）
[PASS] 第 2 關：顯示擊殺/空拍進度 / 空拍超過 10 次 → 失敗彈窗 / 重新挑戰
[PASS] 第 3 關：Boss 血量 50、體積 4 倍 / 召喚子嗣 + 僵直 1.5 秒
[PASS] 僵直時承受雙倍傷害（1 傷 → 扣 2 血） 50 -> 48
[PASS] Boss 血量歸零 → 通關畫面
[PASS] 第 1 關 600 分達標 → 通關 + 下一關按鈕 → 進入第 2 關
[PASS] 手機（Pixel 5）以觸控開始遊戲 / 手機觸控拍打命中有計分
RESULT: PASS
```

## 程式結構（都在 `index.html`）

| 區塊 | 內容 |
| :--- | :--- |
| 1. 音效 | `Sfx`：Web Audio 即時合成拍擊／電擊／噴霧／雷射／升級／勝敗音，無外部音檔 |
| 2. 資料 | `WEAPONS`（5 種）、`FLY_TYPES`（家蠅／綠頭蠅／果蠅／子嗣／蠅王）、`LEVELS`（3 關） |
| 3. 狀態 | `state`：分數、解鎖進度、計時、毒霧、特效、Boss 等 |
| 4. 蒼蠅 | `Fly` 類別：角度擾動遊走 + 邊界轉向；`rest` 停歇搓腳；`dying` 下墜漸隱；Boss 的閃避／召喚／僵直 |
| 5. 分數 | `addScore` / `checkUnlock`（門檻自動解鎖並切換） |
| 6. 攻擊 | `attack`（tap/遠近判定）、`spawnCloud`（毒霧 DoT）、`fireLaser`（橫貫掃射） |
| 7. 特效 | 粒子、衝擊環、電弧、網格震動、雷射殘影、畫面震動 |
| 8. 場景 | 三關程序化背景（客廳西瓜／菜市場吊燈／雨夜後巷廚餘桶） |
| 9–10. 主循環 | `update`（生成／計時／目標判定）、`render`（含螢幕震動） |
| 11. HUD | 倒數、進度條、分數、武器 chip、Boss 血條、升級 toast、結算彈窗 |
| 12–14 | 輸入（Pointer Events + capture）、啟動、`window.__game` 測試鉤子 |

測試鉤子（給自動化用，不影響玩法）：`__game.startLevel(n)`、`addScore(n)`、`spawnFly(x,y,type)`、
`forceSummon()`、`forceStun(t)`、`setTimeLeft(t)`、`attack(x,y)`，以及 `state / flies / boss / clouds / effects / weapon / frame`。

## 發佈到 GitHub Pages

```powershell
# token 放在 repo 外（沿用既有設定）
# %LOCALAPPDATA%\mech-taipei-tunnel\gh-token.txt  ← 一行 PAT
.\publish-pages.ps1 -Owner bodhi16889 -Repo fly-swat-rampage
.\publish-pages.ps1 -DryRun      # 只看要上傳哪些檔案
```

發佈後用同一支測試對公開網址驗一次：

```powershell
python verify_smoke.py --base-url https://bodhi16889.github.io/fly-swat-rampage/index.html
```

## 已知限制

- 沒有排行榜／存檔（重新整理即重來）；沒有 Service Worker（離線需自行加）。
- 音效靠瀏覽器 `AudioContext`，iOS 需先有觸控手勢才會開聲（已綁在第一下 pointerdown）。
- 命中判定是圓對圓，蒼蠅重疊時以「最近的一隻」為目標（電蚊拍除外，全範圍）。
- 佈景為程序化繪製（無圖檔），風格偏幾何；要換美術可把 `drawBackground()` 換成貼圖。
