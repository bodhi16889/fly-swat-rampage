/* Fly Swat Rampage — global per-level leaderboard
 * Cloudflare Worker + D1. Deploy steps: server/README.md
 *
 * Identity: GamePix Game Token (RS256 JWT). The player id is payload.sub.
 * The display name is NOT signed by GamePix (docs: no displayName claim), so
 * it is stored as display-only text, sanitized, never used as identity.
 */

const JWKS_URL = 'https://auth.gamepix.com/.well-known/jwks.json';
const ISSUER = 'https://auth.gamepix.com';
const MAX_LEVEL = 100;
const CACHE_TTL = 60 * 60 * 1000;

let jwksCache = { at: 0, keys: [] };

const CORS = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET,POST,DELETE,OPTIONS',
  'access-control-allow-headers': 'Authorization,Content-Type',
  'access-control-max-age': '86400',
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', ...CORS },
  });
}

class HttpError extends Error {
  constructor(status, code) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

/* Same level rules as index.html makeLevel(): score / kills / defend / boss. */
export function goalType(n) {
  const chapter = Math.floor((n - 1) / 20) + 1;
  const stage = ((n - 1) % 20) + 1;
  const isBoss = stage % 10 === 0;
  const isDefend = !isBoss && chapter === 3 && stage % 3 !== 0;
  const isKills = !isBoss && !isDefend && (chapter === 2 || chapter === 4 || stage % 2 === 0);
  return isBoss ? 'boss' : isDefend ? 'defend' : isKills ? 'kills' : 'score';
}

export function levelTime(n) {
  const chapter = Math.floor((n - 1) / 20) + 1;
  const stage = ((n - 1) % 20) + 1;
  const isBoss = stage % 10 === 0;
  const isDefend = !isBoss && chapter === 3 && stage % 3 !== 0;
  const isKills = !isBoss && !isDefend && (chapter === 2 || chapter === 4 || stage % 2 === 0);
  if (isBoss) return 80;
  if (isDefend) return Math.round(45 + Math.min(15, n * 0.12));
  if (isKills) return Math.round(45 + Math.min(20, n * 0.15));
  return Math.round(40 + Math.min(20, n * 0.15));
}

function maxScore(n) {
  return Math.max(2000, (300 + n * 40) * 20);
}

export function sanitizeName(raw) {
  const s = String(raw == null ? '' : raw)
    .replace(/<[^>]*>/g, '')
    .replace(/[\u0000-\u001f<>]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 16);
  return s || 'Player';
}

export function compareScore(a, b, type) {
  // returns negative when a is better than b
  if (type === 'score' || type === 'defend') {
    return (b.value - a.value) || (a.time_ms - b.time_ms) || (a.updated_at - b.updated_at);
  }
  return (a.time_ms - b.time_ms) || (a.misses - b.misses) || (a.updated_at - b.updated_at);
}

export function validateScore(body) {
  const level = Number(body.level);
  if (!Number.isInteger(level) || level < 1 || level > MAX_LEVEL) throw new HttpError(400, 'bad-level');
  const type = goalType(level);
  const value = Math.round(Number(body.value));
  const timeMs = Math.round(Number(body.timeMs));
  const misses = Math.round(Number(body.misses == null ? 0 : body.misses));
  const revived = body.revived ? 1 : 0;
  if (!Number.isFinite(value) || !Number.isFinite(timeMs) || !Number.isFinite(misses)) {
    throw new HttpError(400, 'bad-number');
  }
  if (value < 0 || timeMs < 0 || misses < 0 || misses > 999) throw new HttpError(400, 'bad-range');
  const maxTime = levelTime(level) * 1000 + 3000;
  if (timeMs > maxTime) throw new HttpError(400, 'time-too-long');
  if (type === 'score') {
    if (value > maxScore(level)) throw new HttpError(400, 'score-too-high');
  } else if (type === 'defend') {
    if (value > 100) throw new HttpError(400, 'hp-too-high');
    if (timeMs < 2000) throw new HttpError(400, 'time-too-short');
  } else {
    if (value !== timeMs) throw new HttpError(400, 'value-mismatch');
    if (timeMs < 3000) throw new HttpError(400, 'time-too-short');
  }
  return { level, type, value, timeMs, misses, revived };
}

function b64urlToBytes(input) {
  let s = String(input).replace(/-/g, '+').replace(/_/g, '/');
  const pad = s.length % 4;
  if (pad) s += '='.repeat(4 - pad);
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function decodePart(part) {
  return JSON.parse(new TextDecoder().decode(b64urlToBytes(part)));
}

async function getJwks(env) {
  if (jwksCache.keys.length && Date.now() - jwksCache.at < CACHE_TTL) return jwksCache.keys;
  const res = await fetch(env.JWKS_URL || JWKS_URL, { headers: { accept: 'application/json' } });
  if (!res.ok) throw new HttpError(503, 'jwks-unavailable');
  const data = await res.json();
  jwksCache = { at: Date.now(), keys: Array.isArray(data.keys) ? data.keys : [] };
  return jwksCache.keys;
}

export async function verifyToken(token, env) {
  const parts = String(token || '').split('.');
  if (parts.length !== 3) throw new HttpError(401, 'bad-token');
  let header;
  let payload;
  try {
    header = decodePart(parts[0]);
    payload = decodePart(parts[1]);
  } catch (e) {
    throw new HttpError(401, 'bad-token');
  }
  if (header.alg !== 'RS256') throw new HttpError(401, 'bad-alg');
  if (!env.GAMEPIX_GAME_ID) throw new HttpError(500, 'no-game-id-configured');
  let keys = await getJwks(env);
  let jwk = keys.find((k) => k.kid === header.kid);
  if (!jwk) {
    // Key rotation: refresh once, then require an exact kid match (no key confusion).
    jwksCache = { at: 0, keys: [] };
    keys = await getJwks(env);
    jwk = keys.find((k) => k.kid === header.kid);
  }
  if (!jwk) throw new HttpError(401, 'unknown-kid');
  let ok = false;
  try {
    const key = await crypto.subtle.importKey(
      'jwk', jwk,
      { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
      false, ['verify'],
    );
    ok = await crypto.subtle.verify(
      'RSASSA-PKCS1-v1_5', key,
      b64urlToBytes(parts[2]),
      new TextEncoder().encode(parts[0] + '.' + parts[1]),
    );
  } catch (e) {
    throw new HttpError(401, 'bad-signature');
  }
  if (!ok) throw new HttpError(401, 'bad-signature');
  const now = Math.floor(Date.now() / 1000);
  if (payload.iss !== ISSUER) throw new HttpError(401, 'bad-iss');
  const audience = `gpx:game:${env.GAMEPIX_GAME_ID}`;
  const aud = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (!aud.includes(audience)) throw new HttpError(401, 'bad-aud');
  if (!payload.exp || payload.exp <= now) throw new HttpError(401, 'expired');
  if (payload.nbf && payload.nbf > now + 60) throw new HttpError(401, 'not-yet-valid');
  if (payload.gid && payload.gid !== env.GAMEPIX_GAME_ID) throw new HttpError(401, 'bad-gid');
  if (!payload.sub) throw new HttpError(401, 'no-sub');
  return payload;
}

async function requirePlayer(req, env) {
  const header = req.headers.get('authorization') || '';
  if (!/^Bearer\s+/i.test(header)) throw new HttpError(401, 'login-required');
  return verifyToken(header.replace(/^Bearer\s+/i, ''), env);
}

async function optionalPlayer(req, env) {
  try {
    const header = req.headers.get('authorization') || '';
    if (!/^Bearer\s+/i.test(header)) return null;
    return await verifyToken(header.replace(/^Bearer\s+/i, ''), env);
  } catch (e) {
    return null;
  }
}

async function rankOf(db, level, revived, type, e) {
  const isValue = type === 'score' || type === 'defend';
  const sql = isValue
    ? 'SELECT COUNT(*) + 1 AS rank FROM scores WHERE level=? AND revived=? AND (value>? OR (value=? AND time_ms<?))'
    : 'SELECT COUNT(*) + 1 AS rank FROM scores WHERE level=? AND revived=? AND (time_ms<? OR (time_ms=? AND misses<?))';
  const args = isValue
    ? [level, revived, e.value, e.value, e.time_ms]
    : [level, revived, e.time_ms, e.time_ms, e.misses];
  const row = await db.prepare(sql).bind(...args).first();
  return row ? row.rank : 1;
}

async function rateLimit(db, playerId) {
  const now = Date.now();
  await db.prepare('DELETE FROM rate WHERE ts < ?').bind(now - 3600_000).run();
  const count = await db.prepare('SELECT COUNT(*) AS n FROM rate WHERE player_id=? AND ts>?')
    .bind(playerId, now - 60_000).first();
  if (count && count.n >= 20) throw new HttpError(429, 'rate-limited');
  await db.prepare('INSERT INTO rate(player_id, ts) VALUES(?,?)').bind(playerId, now).run();
}

async function postScore(req, env) {
  const payload = await requirePlayer(req, env);
  let body;
  try { body = await req.json(); } catch (e) { throw new HttpError(400, 'bad-json'); }
  const s = validateScore(body);
  const playerId = String(payload.sub);
  const name = sanitizeName(body.name || payload.username || payload.name);
  await rateLimit(env.DB, playerId);
  const existing = await env.DB.prepare(
    'SELECT value,time_ms,misses,revived,updated_at FROM scores WHERE level=? AND player_id=? AND revived=?',
  ).bind(s.level, playerId, s.revived).first();
  const next = {
    value: s.value, time_ms: s.timeMs, misses: s.misses, revived: s.revived, updated_at: Date.now(),
  };
  const better = !existing || compareScore(next, existing, s.type) < 0;
  if (better) {
    await env.DB.prepare(
      `INSERT INTO scores(level,player_id,name,value,time_ms,misses,revived,updated_at)
       VALUES(?,?,?,?,?,?,?,?)
       ON CONFLICT(level,player_id,revived) DO UPDATE SET
         name=excluded.name, value=excluded.value, time_ms=excluded.time_ms,
         misses=excluded.misses, updated_at=excluded.updated_at`,
    ).bind(s.level, playerId, name, s.value, s.timeMs, s.misses, s.revived, Date.now()).run();
  } else {
    await env.DB.prepare(
      'UPDATE scores SET name=? WHERE level=? AND player_id=? AND revived=?',
    ).bind(name, s.level, playerId, s.revived).run();
  }
  const stored = better ? next : existing;
  const rank = await rankOf(env.DB, s.level, s.revived, s.type, stored);
  return json({ ok: true, level: s.level, revived: s.revived, rank, name });
}

async function getBoard(req, env, url) {
  const level = Number(url.searchParams.get('level'));
  if (!Number.isInteger(level) || level < 1 || level > MAX_LEVEL) throw new HttpError(400, 'bad-level');
  const revived = url.searchParams.get('revived') === '1' ? 1 : 0;
  const rawLimit = Number(url.searchParams.get('limit'));
  const limit = Number.isFinite(rawLimit) ? Math.min(100, Math.max(1, Math.floor(rawLimit))) : 50;
  const type = goalType(level);
  const order = (type === 'score' || type === 'defend')
    ? 'value DESC, time_ms ASC, updated_at ASC'
    : 'time_ms ASC, misses ASC, updated_at ASC';
  const rows = await env.DB.prepare(
    `SELECT player_id,name,value,time_ms,misses,revived
     FROM scores WHERE level=? AND revived=? ORDER BY ${order} LIMIT ?`,
  ).bind(level, revived, limit).all();
  const player = await optionalPlayer(req, env);
  let me = null;
  const list = (rows.results || []).map((r) => ({
    name: r.name, value: r.value, timeMs: r.time_ms, misses: r.misses,
    revived: r.revived, you: !!(player && r.player_id === player.sub),
  }));
  if (player) {
    const mine = await env.DB.prepare(
      'SELECT value,time_ms,misses,revived,updated_at FROM scores WHERE level=? AND player_id=? AND revived=?',
    ).bind(level, player.sub, revived).first();
    if (mine) {
      me = {
        rank: await rankOf(env.DB, level, revived, type, mine),
        value: mine.value, timeMs: mine.time_ms, misses: mine.misses, revived: mine.revived,
      };
    }
  }
  return json({ level, revived, rows: list, me });
}

async function deleteMe(req, env) {
  const payload = await requirePlayer(req, env);
  await env.DB.prepare('DELETE FROM scores WHERE player_id=?').bind(payload.sub).run();
  await env.DB.prepare('DELETE FROM rate WHERE player_id=?').bind(payload.sub).run();
  return json({ ok: true });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });
    try {
      if (url.pathname === '/v1/health') {
        return json({ ok: true, configured: !!env.GAMEPIX_GAME_ID });
      }
      if (url.pathname === '/v1/scores' && req.method === 'POST') return await postScore(req, env);
      if (url.pathname === '/v1/leaderboard' && req.method === 'GET') return await getBoard(req, env, url);
      if (url.pathname === '/v1/me' && req.method === 'DELETE') return await deleteMe(req, env);
      return json({ error: 'not-found' }, 404);
    } catch (e) {
      const status = e instanceof HttpError ? e.status : 500;
      const code = e instanceof HttpError ? e.code : 'server-error';
      if (!(e instanceof HttpError)) console.error('unhandled', e && e.stack ? e.stack : e);
      return json({ error: code }, status);
    }
  },
};
