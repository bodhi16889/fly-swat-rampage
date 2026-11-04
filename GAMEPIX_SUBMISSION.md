# GamePix 上架包 — Fly Swat Rampage

單檔 HTML5（Canvas 2D）直向打蒼蠅遊戲（V5：20 武器、100 關）。已接 GamePix SDK v3（manual lifecycle），
英文為預設語言、中文僅在 `zh*` 系統顯示。這份文件是「照著填 / 照著傳」的清單。

- 遊戲本體：`index.html`（約 266 KB，零圖檔／零音檔，全部內嵌）
- 上傳檔：`dist/fly-swat-rampage-gamepix.zip`（約 137 KB，ZIP 根目錄只有 `index.html`）
- 素材：`gamepix/assets/`
- 驗證：`python3 verify_smoke.py`（85 項，全部 PASS，含對 ZIP 解壓後的版本跑過一次）

---

## 1. 整合 GamePix SDK（已完成）

`index.html` `<head>` 先設 config 再載 SDK：

```html
<script>window.GamePixConfig = { lifecycle: 'manual' };</script>
<script src="https://integration.gamepix.com/sdk/v3/gamepix.sdk.js"></script>
```

| SDK 呼叫 | 遊戲中的時機 | 行為 |
| :--- | :--- | :--- |
| `GamePix.lifecycle.loading(5/60/100)` | 開機 → 選單畫完 → 首兩帧 | 驅動 GamePix 載入條 |
| `GamePix.lifecycle.loaded()` | 首兩帧後 | 收起載入畫面（`#loading`） |
| `GamePix.lifecycle.gameStart()` | 第一次 `startLevel()` / `startEndless()` | 只送一次 |
| `GamePix.events.on('pause'/'resume')` | SDK 播廣告、Player 覆蓋層 | 停遊戲時鐘／輸入，`AudioContext.suspend()`；恢復時依原靜音設定還原 |
| `GamePix.ads.interstitial()` | 結算畫面的「下一關／重新挑戰／進入無盡」 | 只在關卡之間，播完 Promise 才進下一關 |
| `GamePix.ads.reward()` | 失敗／無盡結束的「看廣告復活／續命」 | 關卡：+15 秒、空拍／蜜蜂歸零、可頌衛生度至少 50；無盡：容錯歸零並收回剛才寫入的排行，存活時間保留；每局一次 |
| `GamePix.happyMoment('level_complete'/'boss_defeated')` | 通關／擊倒蠅王 | 玩家正向訊號 |
| `GamePix.sadMoment('level_failed'/'game_over')` | 失敗／無盡結束 | 玩家負向訊號 |

沒有 SDK（`file://`、直接開頁、CDN 掛掉）時全部 no-op：廣告回 `{success:false}`、遊戲照常可玩。
本機可在網址加 `?gpx_inspector=1` 看 SDK 模擬狀態；廣告結果用
`?gpx_ad=nofill|error`、`?gpx_reward=cancel|success` 強制測試。
**本機測廣告要同時加 `?gpx_ads=1`**（例如 `?gpx_ads=1&gpx_ad=success&gpx_reward=success&gpx_user=guest`），
因為公開 demo（GitHub Pages 頂層頁）不啟用廣告，避免 SDK 在非 Player 環境模擬假廣告；
在 GamePix Player／iframe 或 gamepix.com 會自動啟用。

存檔使用 `localStorage`，key 固定為 `fly.swat.progress`、`fly.swat.score`、`fly.swat.endless`、
`fly.swat.muted`（GamePix 只會同步固定 key 的讀寫，不列舉）。

## 2. Game Properties（後台欄位建議值）

| 欄位 | 建議值 |
| :--- | :--- |
| Title | `Fly Swat Rampage` |
| Orientation | `Any`（已決定；遊戲直向設計，但橫向 iframe 也能玩、無「請旋轉」提示；已測 640×480 與 1920×1080） |
| Resolution | `1080 × 1920`（直向；responsive，已測 640×480 以上） |
| Category | `Arcade`（次要：`Casual`） |
| Technology | HTML5 / JavaScript（Canvas 2D） |
| Tags | fly swat, insect, arcade, casual, one finger, boss fight, weapons, 100 levels, endless, hyper casual |
| Languages | English（預設）、Traditional Chinese |
| Age rating | Everyone |
| Allow Distribution | 建議開啟（增加第三方通路收益；你可在後台自行決定） |

### 短描述（給列表卡片）

```
One-thumb fly-swatting arcade: 20 weapons, 100 levels across 5 chapters, a two-phase Fly King and an endless rampage.
```

### 長描述（給商店頁）

```
Grab the swatter and take back the house! Fly Swat Rampage is a fast, one-thumb arcade game
about clearing a never-ending invasion of flies — from a watermelon on the living-room table
to a back-alley showdown with the Fly King.

Tap to strike, hold to spray, and unlock 20 weapons: rolled newspaper, plastic swatter,
flypaper trap, electric zapper, salt shotgun, insect spray, dual zappers, extermination laser,
electric net, cryo sprayer, triple swatter, sonic shocker, honey decoy, flame thrower,
magnetic vacuum, rocket launcher, plasma cutter, freeze trap, patrol drone and total
extermination. Fight through 100 levels in 5 chapters — living room, market, bakery defence,
campsite and back alley — with a Fly King every 10 levels, then survive the endless rampage.

Easy to learn, quick to play, and full of chain lightning, sticky traps, sonic waves, drones
and double-damage windows for players who like to optimise their swats. Track a personal best
on every level and climb the local leaderboard with your own nickname.
```

### 操作說明（若有獨立欄位）

```
Tap / click: attack with the selected weapon.
Hold: spray insecticide.
Bottom bar: switch between unlocked weapons.
```

## 3. Media Assets（已產好，直接上傳）

| 用途 | 檔案 | 尺寸 | 大小 |
| :--- | :--- | :--- | --: |
| Game Icon | `gamepix/assets/icon-512.png` | 512×512 | 234 KB |
| Cover / Banner | `gamepix/assets/cover-1920x1080.png` | 1920×1080 | 773 KB |
| Screenshot 1（章節選關＋暱稱） | `gamepix/assets/screenshots/01-menu.png` | 1080×1920 | 492 KB |
| Screenshot 2（電蚊拍連鎖） | `gamepix/assets/screenshots/02-action.png` | 1080×1920 | 404 KB |
| Screenshot 3（麵包店防禦） | `gamepix/assets/screenshots/03-defend.png` | 1080×1920 | 190 KB |
| Screenshot 4（蠅王＋護盾＋雷射） | `gamepix/assets/screenshots/04-boss.png` | 1080×1920 | 185 KB |
| Screenshot 5（無盡蟲群） | `gamepix/assets/screenshots/05-endless.png` | 1080×1920 | 227 KB |
| （封面主視覺，不上傳） | `gamepix/assets/screenshots/00-hero.png` | 1080×1920 | 275 KB |

封面與圖示上的標題都是 `FLY SWAT RAMPAGE`，與上架名稱一致；素材內無網址、無外部連結。
要重產：`python3 gamepix/make_assets.py`（Playwright，會起本機伺服器、用真實遊戲畫面截圖）。

## 4. Build（ZIP 已產好）

```bash
python3 build_gamepix.py
# build: dist/fly-swat-rampage-gamepix.zip  137 KB
# entries: ['index.html']
# PASS: index.html 在 ZIP 根目錄、只依賴 GamePix SDK、無其他外部連結
```

ZIP 結構（已驗證）：

```
fly-swat-rampage-gamepix.zip
└── index.html      ← 必須在根目錄，沒有多一層資料夾
```

上傳到 Build 頁後，用後台 **Preview / Test** 測以下項目（若是在本機瀏覽器直接開，廣告網址要帶 `gpx_ads=1`；在 Player／Testkit 內不用）：

- [ ] 載入條出現後消失，選單正常顯示（`loaded` 有送達）
- [ ] 進第 1 關後 Player 收到 `gameStart`
- [ ] 過關 → 「下一關」會先播插頁廣告，廣告期間遊戲時鐘停止、音效暫停，結束後才進下一關
- [ ] 失敗 → 「看廣告復活」：廣告取消（`?gpx_reward=cancel`）不復活、按鈕可再按；
      成功（`?gpx_reward=success`）復活且只給一次
- [ ] 無盡模式容錯用完 → 「看廣告續命」：成功後容錯歸零、排行退回、存活時間接續；同局不再出現續命按鈕
- [ ] 廣告沒 fill（`?gpx_ad=nofill`）時仍能正常進下一關
- [ ] 640×480 iframe 可選關、可玩、武器列不被裁切
- [ ] Console 無 error

## 5. 上架流程（你在後台操作）

1. **Create** 新專案，名稱 `Fly Swat Rampage`。
2. **Game Properties** 照上表填（Orientation / Resolution / Category / 描述 / 標籤）。
3. **Media** 上傳 icon、cover、5 張截圖（檔名與用途對照上表）。
4. **Build** 上傳 `dist/fly-swat-rampage-gamepix.zip`，先 Preview / Test 跑上面清單。
5. **Submit** 送審；審核期間可用測試連結（`?gpx_inspector=1`）確認環境。

專案已註冊，這 5 步都在 GamePix 後台完成；本機檔案已就緒，不需要再改程式。

## 合規自查（對照 GamePix Guidelines）

| 規定 | 狀態 | 證據 |
| :--- | :--: | :--- |
| 廣告期間暫停遊戲 | ✅ | `GP.pause()` → `state.paused`，`update()` 直接 return；實測時鐘不動 |
| 廣告期間暫停音訊 | ✅ | `Sfx.suspend()` 暫停 `AudioContext`；`resume` 依原靜音設定還原 |
| 廣告只在關卡之間 | ✅ | 只有結算畫面按鈕會呼叫 interstitial；無計時觸發 |
| 獎勵廣告需明示、可跳過 | ✅ | 按鈕文字寫明「+15 秒、失誤歸零、每局一次」；其他按鈕可關閉 |
| 載入畫面 | ✅ | `#loading`，`loaded()` 後淡出 |
| 640×480 iframe 可玩 | ✅ | Playwright 實測（選單可捲動、可進關、武器列在畫面內） |
| 無外部連結／外部分析／第三方 SDK | ✅ | `index.html` 內唯一外部 URL 是 GamePix SDK |
| 無 Quit 按鈕 | ✅ | 選單只有關卡與開始 |
| 不得要求旋轉裝置 | ✅ | 無此提示；直向／橫向都可玩 |
| 語言預設英文 | ✅ | 非 `zh*` 一律英文；`zh*` 顯示繁中 |
| 標題一致性 | ✅ | 選單、icon、cover、上架名稱皆 `FLY SWAT RAMPAGE` |

## 已知限制／風險

- 英文語音走瀏覽器 `speechSynthesis`（部分裝置可能沒聲音）；中文仍用內嵌 SAPI 音檔。
- icon 使用系統 emoji 蒼蠅（Apple/Google 渲染略有差異）；若審核對美術有要求，需換成客製插畫。
- 沒有雲端排行榜、沒有 Service Worker；進度只存在 `localStorage`（GamePix 會同步）。
- 遊戲是直向設計；在超寬橫向 iframe 會看到較空的兩側，但仍可正常遊玩（已測 640×480 與 1920×1080）。
- 排行榜是本機（同裝置、可多暱稱、每關前 5），沒有跨裝置／全球榜；全球榜需要後端與 GamePix 身分驗證。

## 驗證記錄（本機實跑）

- `python3 verify_smoke.py`：**85 / 85 PASS**，連跑 2 次；同一份 ZIP 解壓後再跑 1 次也 **85 / 85**。
- 真 SDK（非 stub）本機模擬：
  - `?gpx_ad=success` → 過關按「下一關」播完後進第 2 關；`?gpx_ad=nofill` → 不播廣告仍進第 2 關（`{success:false}`）。
  - `?gpx_reward=success` → 關卡失敗後復活（`phase=playing`, `timeLeft=65`, `revived=true`）。
  - 無盡續命（stub）：結束時排行 1 筆 → 續命後 0 筆、misses=0、survival 保留；再死一次只寫 1 筆且不再給續命。
  - 全程 console / pageerror 為 0。
- 素材尺寸以 `sips` 驗過：icon 512×512、cover 1920×1080、5 張截圖 1080×1920。

## 本機指令

```bash
# 85 項 E2E（含 20 武器機制、100 關資料、暱稱／PB／本機排行、語言切換、SDK／廣告、640×480）
python3 verify_smoke.py

# 打包並驗證 ZIP 結構
python3 build_gamepix.py

# 重產上架素材
python3 gamepix/make_assets.py
```
