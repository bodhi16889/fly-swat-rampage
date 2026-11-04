# 打擊蒼蠅大作戰 · Fly Swat Rampage — **V5（20 武器 · 100 關 · 無盡模式）**

手機 H5 單指觸控打蒼蠅遊戲。**單一 `index.html`、零依賴、Canvas 2D + Web Audio 合成音效 + SAPI 人聲**，
直向滿版（`viewport-fit=cover` + `touch-action: none`），手機瀏覽器打開就能玩。

> 🌐 線上版：<https://bodhi16889.github.io/fly-swat-rampage/>
> 🎮 GamePix 上架包：`dist/fly-swat-rampage-gamepix.zip`（ZIP 根目錄即 `index.html`，約 140 KB）；
> 素材在 `gamepix/assets/`；填表文案與合規自查見 [`GAMEPIX_SUBMISSION.md`](GAMEPIX_SUBMISSION.md)。
> 另有 Three.js 3D 作品：[台北機甲拆除模擬器](https://bodhi16889.github.io/mech-taipei-h5/)

## 玩法

| 操作 | 說明 |
| :--- | :--- |
| 點擊 / 輕觸 | 依當前武器判定（單點 / AOE / 扇形 / 陷阱 / 射線 / 波 / 誘餌 / 火箭 / 無人機 / 全域） |
| 長按滑動 | 噴霧、冰霧、火焰：按住連續輸出 |
| 底部武器列 | 已解鎖的 20 把武器常駐（可橫向捲動），可隨時點選；解鎖進度存在 `localStorage` |
| 選關卡 | 5 章 × 20 關；通過第 100 關解鎖無盡模式 |

## 玩家 / PB / 本機排行 / 語系

- **暱稱**：首次進入自動產生（如 `Player#4821`／`玩家#4821`），可在選單改名；上限 12 字、移除 HTML 標籤、只存在本機。
- **每關 PB**：通關自動記錄。分數關比分數；擊殺／Boss 比通關時間；防禦關比剩餘衛生度；平手比失誤。成績會標記是否用過復活。
- **本機排行榜**：選單「🏆 本機排行」→ 當前章節 20 關一覽 → 點關卡看前 5 名；同一裝置可用不同暱稱上榜。
- **語系**：抓系統語系（`zh*` 繁體中文、其餘英文），選單可手動切換（🌐）並記住；`?lang=zh|en` 供測試覆寫。
- 本機資料存在 `localStorage`：`fly.swat.profile`（暱稱）、`fly.swat.best`（每關前 5）、`fly.swat.lang`（語言）；本機榜沒有後端。
- 另有**選用**的全球每關排行（見下節），預設關閉，不影響本機玩法。

## 全球每關排行（選用，預設關閉）

- 後端：`server/`（Cloudflare Worker + D1 + GamePix Game Token 驗證），已部署在 `https://fly-swat-lb.chenkaiting18.workers.dev`；部署步驟見 `server/README.md`。
- 前端：`?lb=on` 才啟用；預設 `?lb=off`／不帶參數＝完全沒有 UI、不連網。
- 只有 **GamePix 登入玩家**能上傳（身分取 JWT `sub`）；訪客可玩、可看榜、不能上傳。
- 一般榜與「含復活」榜分開；排序規則與本機 PB 相同。
- 上線前先向 GamePix support 確認自家 API 的申報方式；未確認前保持 `LB_ENABLED_DEFAULT = false`。

## 武器（V5：20 把）

| # | 武器 | 解鎖 | 判定 | 機制 |
| --: | :--- | --: | :--- | :--- |
| 1 | 📰 報紙 | 0 | 40 px 單點 | 基礎單體 |
| 2 | 🏓 塑膠拍 | 400 | 70 px 單點 | 範圍更大 |
| 3 | 🪤 黏蠅紙 | 1,000 | 120 px 陷阱 | 定身 2s＋1.5 倍易傷 |
| 4 | ⚡ 電蚊拍 | 1,800 | 100 px AOE | 連鎖 2 隻 |
| 5 | 🧂 鹽槍 | 3,000 | 60°/180 px 扇形 | 扇心 3 傷、扇緣 1 傷 |
| 6 | 🧴 噴霧 | 4,500 | 160 px 持續 | 毒霧每 0.3s 扣 1 |
| 7 | ⚡⚡ 雙持電拍 | 6,500 | 雙點各 90 px | 左右各一次電爆 |
| 8 | 🔫 雷射 | 9,000 | 80 px 帶狀 | 穿透、Boss 8 傷 |
| 9 | 🕸️ 高壓電擊網 | 12,000 | 150 px AOE | 連鎖 3 隻 |
| 10 | ❄️ 急凍噴射器 | 15,500 | 170 px 持續 | 傷害＋定身 0.8s |
| 11 | 🏓 三連拍 | 19,500 | 三點各 65 px | 一次拍三個位置 |
| 12 | 🔊 音波震盪器 | 24,000 | 230 px 擴散波 | 每隻只吃一次 |
| 13 | 🍯 誘餌陷阱 | 29,000 | 230 px 吸引 → 160 px 爆炸 | 2.2s 後 2 傷 |
| 14 | 🔥 火焰噴射器 | 34,500 | 70°/210 px 持續 | 每 0.2s 結算 |
| 15 | 🧲 磁力吸塵器 | 40,500 | 240 px | 拉到中心＋2 傷＋短定身 |
| 16 | 🚀 火箭除蟲炮 | 47,000 | 110 px 爆炸 | 3 傷 |
| 17 | 🔆 等離子切割槍 | 54,500 | 60 px 帶狀 | 穿透、Boss 12 傷 |
| 18 | 🧊 急凍陷阱板 | 63,000 | 140 px 陷阱 | 定身 3.5s |
| 19 | 🛸 無人機 | 73,000 | 260 px 自動射擊 | 6 秒、每 0.35s 1 傷 |
| 20 | ☢️ 全域殲滅 | 85,000 | 全畫面 | 一般蟲秒殺、Boss 15 傷 |

**精準爆發流**：報紙 / 塑膠拍 / 黏紙 / 鹽槍 / 三連 / 誘餌 / 火箭 / 冰紙
**範圍清場流**：電蚊拍 / 噴霧 / 雙持 / 雷射 / 電網 / 冰霧 / 音波 / 火焰 / 磁力 / 電漿 / 無人機 / 殲滅

## 關卡（100 關 = 5 章 × 20 關 + 無盡）

| 章 | 場景 | 關卡 | 主要目標 | 機制 |
| --: | :--- | --: | :--- | :--- |
| 1 | 夏日客廳 | 1–20 | 分數／擊殺 | 西瓜停駐雙倍分；第 5 關起綠頭蠅、第 8 關起果蠅群 |
| 2 | 傳統菜市場 | 21–40 | 擊殺＋空拍上限 | 目標數與空拍上限逐關變嚴 |
| 3 | 麵包店櫥窗 | 41–60 | 防禦可頌 | `eating` 每秒扣衛生度（隨關卡提高） |
| 4 | 露營野餐墊 | 61–80 | 擊殺＋蜜蜂 | 誤擊蜜蜂 −200／凍結；側風每 9–16 秒 |
| 5 | 後巷廚餘桶 | 81–100 | 分數／擊殺／Boss | 每 10 關蠅王；P2 俯衝後力竭雙倍傷害 |

- 難度：`spawnEvery` 0.944 → 0.356、Boss HP 80 → 395、目標數與時間同步調整（資料由 `makeLevel(n)` 生成，避免 100 筆手寫漂移）。
- 每 10 關（10, 20, …, 100）是 Boss 關；第 100 關為最終蠅王。
- 通關第 100 關解鎖無盡模式（容錯 20、每 60 秒迷你王、本機 top 5）。

## 音效與人聲

- 分層音效：`swing` → `hit` → `kill`（60ms 限流）→ `bossDown`。
- 中文人聲（SAPI 預先合成、base64 內嵌）：擊殺「什麼意思」、蠅王「你有病喔」；英文用瀏覽器 TTS。
- 母帶 `master 0.4 → DynamicsCompressor(-18dB/ratio 6)`；🔊/🔇 記憶在 `localStorage`。

## 快速啟動

```bash
cd ~/fly-swat-rampage
python3 -m http.server 8099
# http://127.0.0.1:8099/index.html
```

> 直接開 `file://` 也能跑：沒有外部圖檔／音檔；預設沒有 fetch，只有 `?lb=on` 且 `LB_URL` 有值才會連排行榜。
> 手機測試：`ipconfig getifaddr en0`（macOS）→ 手機開 `http://<IP>:8099/index.html`。

## 驗證（Playwright，可重跑）

```bash
python3 -m pip install --user playwright   # 第一次
python3 -m playwright install chromium     # 第一次
python3 verify_smoke.py                    # 自動選空閒埠
python3 verify_smoke.py --headed           # 想看畫面
python3 verify_smoke.py --base-url https://bodhi16889.github.io/fly-swat-rampage/index.html
```

覆蓋範圍（96 項檢查）：

- 版面 / 主循環 / 暖機後 fps
- 選單：100 關、5 章 × 20 格、20 武器、四種目標型別、無盡未解鎖
- 難度曲線：生成間隔遞減、Boss HP 80 → 220 → 395
- 前 8 把武器機制（黏紙／電蚊拍／鹽槍／噴霧／雙持／雷射）
- 後 12 把新機制：三連、音波、誘餌、磁力、火箭、無人機、全域、急凍陷阱、冰霧、火焰
- 防禦關（第 41 關）、蜜蜂＋突風（第 61 關）
- Boss（第 10 關）：80 HP、護盾 8、雷射穿透 −8、Phase 2、力竭雙傷、通關存進度
- 無盡：第 100 關才解鎖、存活計時、迷你王
- 武器解鎖持久化：85,000 分→20 把、重載仍保留、重置歸零
- 本機暱稱：自動產生、改名去標籤、重載保留
- 每關 PB：通關記錄、較高分刷新、較差分不覆蓋、結果畫面顯示
- 本機排行：章節 20 關列表、單關前 5、同裝置多暱稱
- 語言切換：英文介面按 🌐 切中文、存 localStorage、重載生效
- 全球榜：100 關型別與後端一致、預設關閉、上傳/名次、排序與自己標記、復活分榜、章節 20 關、訪客不可上傳、API 失敗 fallback
- GamePix SDK：manual lifecycle、pause/resume、插頁廣告時機、關卡復活＋無盡續命、無 SDK 退路
- 語系：英文預設、`zh` 中文
- 640×480 iframe、Pixel 5 直向、20 武器列
- 全程無 console / page error

判定時間一律用 `wait_for_function`（等狀態變化）而不是固定 `sleep`：
headless + SwiftShader 前 1–2 秒只有 1–2 fps，用睡眠會量到暖機或拍到舊座標。

最近一次結果：

```
[PASS] V5：100 關 + 20 武器 + 5 章（每章 20 關）
[PASS] 武器解鎖門檻符合 V5 規格 / 底部武器列 20 把
[PASS] 關卡目標四型都有（score 23 / kills 55 / defend 12 / boss 10）
[PASS] 難度遞增：spawn 0.944→0.356、Boss HP 80→220→395
[PASS] 前 8 把武器機制 + 後 12 把新機制
[PASS] 防禦關 / 蜜蜂＋突風 / Boss 二階段＋力竭雙傷
[PASS] 第 100 關解鎖無盡 / 迷你王
[PASS] 85,000 分→20 把武器、重載保留、重置歸零
[PASS] GamePix：插頁／復活／續命／無 SDK no-op
[PASS] 全球榜：上傳／排序／復活分榜／訪客／離線 fallback
[PASS] 手機 Pixel 5 / 640×480 iframe
RESULT: PASS
```

截圖：`artifacts/fly-v5-mobile.png`、`fly-v5-desktop.png`、`fly-v5-640x480.png`

## 程式結構（`index.html` + 選用 `server/`）

| 區塊 | 內容 |
| :--- | :--- |
| 0b / 0c | 語系 `I18N`／`t()`、GamePix `GP`（lifecycle／pause／廣告／復活） |
| 1 / 1b | `Sfx`、`Voice` |
| 2 | `WEAPONS`（20）、`FLY_TYPES`、`CHAPTERS`＋`makeLevel(n)`→`LEVELS`（100）、`ENDLESS_CFG` |
| 3 | `state`：分數、解鎖、陷阱、毒霧、波、誘餌、火箭、無人機、可頌、蜜蜂、突風、Combo |
| 4 | `Fly`：遊走／停歇／定身／`eating`／偽裝／Boss 二階段／俯衝／力竭 |
| 5 | 分數、解鎖、存檔（`fly.swat.progress`／`fly.swat.score`／`fly.swat.endless`）、暱稱（`fly.swat.profile`）、每關 PB（`fly.swat.best`）、語言（`fly.swat.lang`） |
| 5b | 選用全球榜（`LB_URL`／`LB_ENABLED_DEFAULT`、`?lb=on|off`、`sendScore`、全球章節／單關前 50）；後端在 `server/` |
| 6 | `attack()` 模式分派：tap／fan／hold／holdFan／trap／laser／wave／decoy／magnet／rocket／drone／screen → `damageFly` |
| 7 | 粒子與特效（環、電弧、扇形、文字、閃光） |
| 8 | 5 種程序化場景（每章共用） |
| 9 | 蒼蠅繪製（蜜蜂、金斑偽裝、Boss 護盾／Phase 2） |
| 10 | `update()`：生成、突風、毒霧、陷阱、波、誘餌、火箭、無人機、護盾、目標判定 |
| 11 | HUD、章節選單（暱稱／改名／語言切換／5×20 格）、本機排行（章節＋單關前 5）、全球排行（章節＋前 50）、結算（PB／全球名次／復活／續命） |
| 12–14 | 輸入、繪製、啟動與 `window.__game` 測試鉤子 |

測試鉤子：`startLevel(n)`、`startEndless()`、`showStart()`、`addScore(n)`、`spawnFly(x,y,type)`、
`spawnBee()`、`forceSummon()`、`forceDive()`、`forceExhaust(t)`、`forceGust()`、`forcePhase2()`、
`setTimeLeft(t)`、`attack(x,y)`、`clearScore()`，以及 `state / flies / boss / defend / traps / clouds /
waves / decoys / rockets / drones / effects / weapon / progress / board / frame / audio / voice / gp`。

## GamePix 打包與上架

```bash
python3 build_gamepix.py        # dist/fly-swat-rampage-gamepix.zip（根目錄只有 index.html）
python3 gamepix/make_assets.py  # icon 512 / cover 1920×1080 / 5 張 1080×1920 截圖（另產 1 張封面主視覺）
python3 verify_smoke.py         # 96 項
```

SDK：`GamePixConfig = { lifecycle:'manual' }`、`loading→loaded→gameStart`、`pause/resume`（停時鐘＋音訊）、
關卡間插頁、獎勵廣告復活（關卡 +15s／無盡容錯歸零並收回排行，每局一次）。
廣告只在真正 Player（iframe 或 gamepix.com）啟用；GitHub Pages demo 不呼叫（避免 SDK 模擬假廣告）；
本機測廣告加 `?gpx_ads=1`。語言：`zh*` 中文、其餘英文。詳 `GAMEPIX_SUBMISSION.md`。

## 發佈到 GitHub Pages

```bash
git push origin main          # 本站由 main / root 自動部署
```

## 已知限制

- 沒有 Service Worker；本機榜每關前 5、同裝置多暱稱。全球榜需自行部署 `server/`，且只有登入玩家能上傳。
- 全球榜仍無法完全防作弊（客户端回報時間／分數，只能擋離譜值）；訪客不進全球榜。
- 改名只影響之後的成績；舊紀錄保留當時的暱稱。
- 單點類武器取最近一隻；蜜蜂只對點擊類武器有懲罰（噴霧／雷射／波會跳過友軍）。
- 鹽槍／火焰方向為「點擊點 → 畫面中心」。
- 場景為程序化繪製（無圖檔）；換美術可改 `drawBackground()`。
- 100 關數值由生成器調整，個別關卡可能仍需實玩微調（`makeLevel` 是單一調整點）。
