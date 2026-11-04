#!/usr/bin/env node
/* Offline tests for the Worker's crypto + validation.
 * Run: node server/test_worker.mjs
 * No Cloudflare account or D1 needed. Uses a local JWKS server and a test RSA key.
 */
import http from 'node:http';
import { generateKeyPairSync, sign } from 'node:crypto';
import {
  verifyToken, validateScore, goalType, levelTime, sanitizeName, compareScore,
} from './worker.js';

let pass = 0;
let fail = 0;
function check(name, fn) {
  try {
    fn();
    pass++;
    console.log('[PASS] ' + name);
  } catch (e) {
    fail++;
    console.log('[FAIL] ' + name + ' — ' + (e && e.message ? e.message : e));
  }
}
async function checkAsync(name, fn) {
  try {
    await fn();
    pass++;
    console.log('[PASS] ' + name);
  } catch (e) {
    fail++;
    console.log('[FAIL] ' + name + ' — ' + (e && e.message ? e.message : e));
  }
}
function assert(cond, msg) { if (!cond) throw new Error(msg || 'assert'); }

const b64url = (buf) => Buffer.from(buf).toString('base64url');
const { publicKey, privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
const jwk = publicKey.export({ format: 'jwk' });
jwk.kid = 'test-key';
jwk.alg = 'RS256';
jwk.use = 'sig';

const jwksServer = http.createServer((req, res) => {
  res.setHeader('content-type', 'application/json');
  res.end(JSON.stringify({ keys: [jwk] }));
});
await new Promise((resolve) => jwksServer.listen(0, '127.0.0.1', resolve));
const env = {
  GAMEPIX_GAME_ID: 'game123',
  JWKS_URL: `http://127.0.0.1:${jwksServer.address().port}/jwks.json`,
};

function token(payload, key = privateKey, alg = 'RS256') {
  const header = { alg, typ: 'JWT', kid: 'test-key' };
  const head = b64url(JSON.stringify(header));
  const body = b64url(JSON.stringify(payload));
  const data = head + '.' + body;
  const sig = alg === 'none' ? '' : sign('RSA-SHA256', Buffer.from(data), key);
  return data + '.' + b64url(sig);
}
const now = () => Math.floor(Date.now() / 1000);
const base = () => ({
  iss: 'https://auth.gamepix.com',
  aud: 'gpx:game:game123',
  sub: 'user-1',
  gid: 'game123',
  iat: now() - 5,
  exp: now() + 600,
});

await checkAsync('JWT：合法 token 驗證成功並取回 sub', async () => {
  const p = await verifyToken(token(base()), env);
  assert(p.sub === 'user-1');
});
await checkAsync('JWT：aud 必須是 gpx:game:<gameId>', async () => {
  let threw = false;
  try { await verifyToken(token({ ...base(), aud: 'gpx:game:other' }), env); } catch (e) { threw = true; }
  assert(threw);
});
await checkAsync('JWT：gid 必須符合 gameId', async () => {
  let threw = false;
  try { await verifyToken(token({ ...base(), gid: 'other' }), env); } catch (e) { threw = true; }
  assert(threw);
});
await checkAsync('JWT：過期 token 拒絕', async () => {
  let threw = false;
  try { await verifyToken(token({ ...base(), exp: now() - 10 }), env); } catch (e) { threw = true; }
  assert(threw);
});
await checkAsync('JWT：簽章被改拒絕', async () => {
  const good = token(base());
  const parts = good.split('.');
  const other = token({ ...base(), sub: 'attacker' }).split('.')[2];
  let threw = false;
  try { await verifyToken(parts[0] + '.' + parts[1] + '.' + other, env); } catch (e) { threw = true; }
  assert(threw);
});
await checkAsync('JWT：alg=none 拒絕', async () => {
  let threw = false;
  try { await verifyToken(token(base(), privateKey, 'none'), env); } catch (e) { threw = true; }
  assert(threw);
});

check('關卡型別與遊戲一致的前哨（1/2/10/41/42/60/81/100）', () => {
  const got = [1, 2, 10, 41, 42, 60, 81, 100].map(goalType).join(',');
  assert(got === 'score,kills,boss,defend,defend,boss,score,boss', got);
});
check('分數關合法成績', () => {
  const s = validateScore({ level: 1, value: 340, timeMs: 5000, misses: 0, revived: 0 });
  assert(s.type === 'score' && s.value === 340);
});
check('分數超過上限拒絕', () => {
  let threw = false;
  try { validateScore({ level: 1, value: 10_000_000, timeMs: 5000 }); } catch (e) { threw = true; }
  assert(threw);
});
check('擊殺關 value 必須等於時間', () => {
  let threw = false;
  try { validateScore({ level: 2, value: 1234, timeMs: 30_000 }); } catch (e) { threw = true; }
  assert(threw);
  const ok = validateScore({ level: 2, value: 30_000, timeMs: 30_000, misses: 3 });
  assert(ok.type === 'kills');
});
check('防禦關血量上限 100', () => {
  let threw = false;
  try { validateScore({ level: 41, value: 101, timeMs: levelTime(41) * 1000 }); } catch (e) { threw = true; }
  assert(threw);
});
check('名稱去除標籤並限長', () => {
  assert(sanitizeName('<b>Adan</b>') === 'Adan');
  assert(sanitizeName('  ').length > 0);
  assert(sanitizeName('x'.repeat(40)).length === 16);
});
check('排名比較：分數高者優先、同分時間短優先', () => {
  const a = { value: 900, time_ms: 5000, misses: 0, updated_at: 1 };
  const b = { value: 500, time_ms: 1000, misses: 0, updated_at: 1 };
  assert(compareScore(a, b, 'score') < 0);
  const c = { value: 900, time_ms: 1000, misses: 0, updated_at: 1 };
  assert(compareScore(c, a, 'score') < 0);
});
check('排名比較：擊殺時間短者優先', () => {
  const a = { value: 30_000, time_ms: 30_000, misses: 4, updated_at: 1 };
  const b = { value: 40_000, time_ms: 40_000, misses: 0, updated_at: 1 };
  assert(compareScore(a, b, 'kills') < 0);
});

jwksServer.close();
console.log(`\nRESULT: ${fail === 0 ? 'PASS' : 'FAIL'} (${pass} passed, ${fail} failed)`);
process.exit(fail === 0 ? 0 : 1);
