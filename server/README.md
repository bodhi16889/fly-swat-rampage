# 全球每關排行榜後端（Cloudflare Worker + D1）

前端在 `index.html`，這個目錄只放後端。**預設不啟用**：`LB_URL` 空字串時，`?lb=on` 也不會連網、不會出現 UI，送審與離線玩法完全不受影響。

## 1. 資料流

```
GamePix Player / 網站
  └─ index.html
       ├─ GamePix.user.getUser() → user.id + displayName + Game Token（JWT, 15 分鐘）
       ├─ POST /v1/scores        Authorization: Bearer <token>
       └─ GET  /v1/leaderboard?level=42&revived=0
             ↓
Cloudflare Worker（worker.js）
  ├─ 驗 RS256 JWT（JWKS: auth.gamepix.com）
  ├─ 驗關卡型別／數值上限／時間上限
  ├─ 每人每關每個榜只留最佳一筆
  └─ D1（SQLite）
```

- 身分只用 JWT 的 `sub`（Xsolla ID，跨裝置穩定）。
- `displayName` **不在 JWT 裡**（GamePix 文件明說 nickname 未簽章），所以名字只當顯示文字，伺服器會去標籤、限 16 字，不能當身分。
- 訪客可以玩、可以看榜，但**不能上傳**；要上傳必須在 GamePix 登入。這是刻意的：訪客身分無法驗證，開放會直接被洗榜。

## 2. API

### `POST /v1/scores`

```json
{
  "level": 42,
  "value": 1234,
  "timeMs": 38200,
  "misses": 3,
  "revived": 0,
  "name": "Adan"
}
```

- `value`：分數關＝分數、防禦關＝剩餘衛生度、擊殺／Boss＝通關毫秒數（必須等於 `timeMs`）。
- `revived`：0＝一般榜、1＝含復活榜。
- 回傳：`{"ok":true,"level":42,"revived":0,"rank":7,"name":"Adan"}`。
- 401＝沒登入／token 無效；429＝超過速率（20 次/分鐘）；400＝數值不合理。

### `GET /v1/leaderboard?level=42&revived=0&limit=50`

- 公開讀取，不需要 token。
- 有 token 時多回 `me`（自己的名次）；`rows[].you` 標記自己。
- 排序：
  - 分數／防禦：`value DESC, time_ms ASC`
  - 擊殺／Boss：`time_ms ASC, misses ASC`

### `DELETE /v1/me`

帶 token，刪除自己的所有成績與速率紀錄（隱私／刪除請求用）。

### `GET /v1/health`

`{"ok":true,"configured":true}`，不吐任何秘密。

## 3. 部署

```bash
cd server
npx wrangler d1 create fly-swat-lb
# 把回傳的 database_id 填進 wrangler.toml
npx wrangler d1 execute fly-swat-lb --remote --file schema.sql
# 把 GamePix 後台的 gameId 填進 wrangler.toml 的 GAMEPIX_GAME_ID
npx wrangler deploy
curl https://fly-swat-lb.<你的帳號>.workers.dev/v1/health
```

然後在 `index.html`：

```js
const LB_URL = 'https://fly-swat-lb.<你的帳號>.workers.dev';
const LB_ENABLED_DEFAULT = false; // 先維持 false，用 ?lb=on 測試
```

送審期間保持 `false`。要正式預設開啟再改 `true`；`?lb=off` 仍可強制關閉。

### 本機測試（不需要 Cloudflare 帳號）

```bash
python3 server/mock_server.py --port 8790
# 另開
python3 -m http.server 8080
# 瀏覽器
http://127.0.0.1:8080/index.html?lb=on&lb_url=http://127.0.0.1:8790&lb_token=test-alice
```

`mock_server.py` 只接受 `test-<id>` / `gpx-local-mock-token`，**不要部署**。

## 4. 驗證

```bash
node server/test_worker.mjs     # JWT 簽章/aud/exp、數值驗證、排名比較（14 項）
python3 verify_smoke.py         # 前端 E2E，含全球榜上傳/排序/分榜/訪客/離線 fallback
```

Worker 測試會自己起一個本機 JWKS 與測試 RSA key，不需要 GamePix 帳號。

## 5. 安全與限制

- **JWT**：只接受 `RS256`、`iss=https://auth.gamepix.com`、`aud=gpx:game:<GAMEPIX_GAME_ID>`、`gid` 相符、未過期；金鑰快取 1 小時。
- **速率**：每人每分鐘 20 次上傳；超過 429。KV/D1 滑動視窗，夠休閒榜使用。
- **數值**：每關算合理上限（分數、時間、衛生度、空拍），伺服器不接受客戶端自由宣稱的分數。
- **仍可作弊**：客户端永遠不可信；時間／分數是回報值，伺服器只能擋離譜值，不能證明真的玩過。若要做高價值競賽，需要伺服器重播/telemetry，成本高很多。
- **名字**：`displayName` 未簽章、可被客户端替換；只做顯示與長度/標籤清理，不當身分。GamePix 平台本身會管帳號名稱。
- **隱私**：只存 `sub`、顯示名、成績、時間；`DELETE /v1/me` 可刪。上線前仍建議在隱私說明寫清楚。
- **GamePix 合規**：SDK 文件明說「複雜資料用自家後端、用 token 驗身分」，但 `Guidelines` 對外部服務有規範。**正式開啟前先問 GamePix support**：自家排行榜 API 是否允許、送審要不要備註。前端已做成可完全關閉，不影響審核。
- **CORS**：`*`，只用 Authorization header，不用 cookie；worker 不記錄 token。
- **成本**：Workers/D1 免費額度對小型休閒遊戲足夠；D1 只存最佳一筆/人/關/榜。

## 6. 檔案

| 檔案 | 用途 |
|---|---|
| `worker.js` | Cloudflare Worker（JWT、驗證、排名、D1） |
| `schema.sql` | D1 資料表與索引 |
| `wrangler.toml` | 部署設定（database_id / gameId 待填） |
| `mock_server.py` | 本機 mock API（E2E 用） |
| `test_worker.mjs` | Worker 純函式與 JWT 測試 |
