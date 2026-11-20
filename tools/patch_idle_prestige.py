#!/usr/bin/env python3
"""一次性把「轉生 + 自動攻擊 + 分數升級主武器」加進 index.html。可重複執行（已套用會跳過）。"""
import io, sys, os

P = os.path.expanduser('~/fly-swat-rampage/index.html')
src = io.open(P, encoding='utf-8').read()
orig = src
applied, skipped = [], []


def rep(tag, old, new, count=1):
    global src
    n = src.count(old)
    if n == 0:
        if new in src:
            skipped.append(tag + '（已套用）')
            return
        raise SystemExit(f'✗ 找不到錨點：{tag}\n{old[:120]}')
    if n != count:
        raise SystemExit(f'✗ 錨點出現 {n} 次（預期 {count}）：{tag}')
    src = src.replace(old, new, count)
    applied.append(tag)


# ---------- 1. state 欄位 ----------
rep('state 欄位',
    "  score: 0,\n  levelScore: 0,",
    "  score: 0,\n  bank: 0,                       // 可花用點數（升級貨幣）\n"
    "  upg: { dmg: 0, rate: 0, coin: 0 },\n"
    "  essence: 0,                    // 轉生精華（永久）\n"
    "  rebirths: 0,\n"
    "  deepest: 0,                    // 最高關卡（轉生計算用）\n"
    "  auto: true,                    // 自動攻擊（預設開）\n"
    "  autoT: 0,\n"
    "  levelScore: 0,")

# ---------- 2. hud 快取 ----------
rep('hud 快取',
    "  hud: { timer: '', score: '', prog: '', weapon: '', combo: '' },",
    "  hud: { timer: '', score: '', prog: '', weapon: '', combo: '', bank: '' },")

# ---------- 3. idle 層（轉生／升級） ----------
IDLE = r"""
/* ==================================================================== *
 * 10b. 轉生與升級（idle 層）
 *   分數 → 點數（自動累積）→ 手動買升級 → 轉生換永久精華
 * ==================================================================== */
const META_KEY = 'fly.swat.meta';

const UPGRADES = {
  dmg:  { base: 80,  mult: 1.30, max: 20, step: 0.15 },   // 傷害 +15%/級
  rate: { base: 100, mult: 1.32, max: 15, step: 0.06 },   // 自動間隔 -6%/級
  coin: { base: 150, mult: 1.35, max: 10, step: 0.05 },   // 得分→點數 +5%/級
};

function loadMeta() {
  try {
    const m = JSON.parse(localStorage.getItem(META_KEY) || '{}');
    state.bank = Math.max(0, Number(m.bank) || 0);
    state.essence = Math.max(0, m.essence | 0);
    state.rebirths = Math.max(0, m.rebirths | 0);
    state.deepest = Math.max(0, m.deepest | 0);
    state.auto = m.auto !== false;
    const u = m.upg || {};
    state.upg = {
      dmg: clamp(u.dmg | 0, 0, UPGRADES.dmg.max),
      rate: clamp(u.rate | 0, 0, UPGRADES.rate.max),
      coin: clamp(u.coin | 0, 0, UPGRADES.coin.max),
    };
  } catch (e) { /* 私密模式 */ }
}

function saveMeta() {
  try {
    localStorage.setItem(META_KEY, JSON.stringify({
      bank: Math.round(state.bank), upg: state.upg, essence: state.essence,
      rebirths: state.rebirths, deepest: state.deepest, auto: state.auto,
    }));
  } catch (e) { /* ignore */ }
}

function dmgMult() { return 1 + UPGRADES.dmg.step * state.upg.dmg + 0.01 * state.essence; }
function coinRate() { return 0.2 + UPGRADES.coin.step * state.upg.coin + 0.01 * state.essence; }
function autoInterval() { return Math.max(0.4, 1.25 * (1 - UPGRADES.rate.step * state.upg.rate)); }
function upgCost(k) { const u = UPGRADES[k]; return Math.round(u.base * Math.pow(u.mult, state.upg[k])); }

function buyUpgrade(k) {
  const u = UPGRADES[k];
  if (!u) return false;
  if (state.upg[k] >= u.max) { showToast(t('upgMax')); return false; }
  const cost = upgCost(k);
  if (state.bank < cost) { showToast(t('upgPoor', { n: cost - Math.floor(state.bank) })); return false; }
  state.bank -= cost;
  state.upg[k]++;
  saveMeta();
  if (typeof Sfx !== 'undefined' && Sfx.upgrade) Sfx.upgrade();
  showToast(t('upgBought', { name: t('upg_' + k), lv: state.upg[k] }));
  renderShop();
  updateHud(true);
  return true;
}

function toggleAuto() {
  state.auto = !state.auto;
  state.autoT = 0;
  saveMeta();
  updateAutoBtn();
  return state.auto;
}

function updateAutoBtn() {
  const b = document.getElementById('autoBtn');
  if (!b) return;
  b.classList.toggle('on', state.auto);
  const l = document.getElementById('autoLbl');
  if (l) l.textContent = state.auto ? t('autoOn') : t('autoOff');
}

/* 轉生：本輪最高關卡 ≥20 或累積分數 ≥30000 才可轉 */
function rebirthGain() {
  if (state.deepest < 20 && state.score < 30000) return 0;
  return 1 + Math.floor(state.deepest / 10) + Math.floor(Math.sqrt(state.score / 2000));
}

function doRebirth() {
  const gain = rebirthGain();
  if (!gain) { showToast(t('rebirthLocked')); return 0; }
  state.essence += gain;
  state.rebirths++;
  state.bank = 0;
  state.upg = { dmg: 0, rate: 0, coin: 0 };
  state.score = 0;
  state.deepest = 0;
  state.level = 1;
  state.unlocked = clamp(1 + Math.floor(state.essence / 10), 1, 5);
  state.weaponIndex = state.unlocked - 1;
  try { localStorage.removeItem(PROGRESS_KEY); } catch (e) { /* ignore */ }
  saveScore();
  saveMeta();
  showToast(t('rebirthDone', { g: gain }));
  if (typeof Sfx !== 'undefined' && Sfx.win) Sfx.win();
  renderWeaponBar();
  updateWeaponChip();
  showStart();
  return gain;
}

function armRebirth(btn) {
  if (!btn) return;
  if (btn.dataset.armed === '1') { btn.dataset.armed = ''; doRebirth(); return; }
  btn.dataset.armed = '1';
  btn.innerHTML = `🌀 ${t('rebirthConfirm')}`;
  clearTimeout(armRebirth._t);
  armRebirth._t = setTimeout(() => {
    if (btn.isConnected) { btn.dataset.armed = ''; btn.innerHTML = `🌀 ${t('rebirthBtn')}`; }
  }, 4000);
}

function shopHtml() {
  const rows = ['dmg', 'rate', 'coin'].map((k) => {
    const u = UPGRADES[k], lv = state.upg[k], maxed = lv >= u.max;
    const cost = upgCost(k), afford = !maxed && state.bank >= cost;
    return `<button class="shopBtn${maxed ? ' max' : ''}${afford || maxed ? '' : ' poor'}" data-upg="${k}" ${maxed ? 'disabled' : ''}>`
      + `<b>${t('upg_' + k)}</b><small>Lv ${lv}/${u.max}</small>`
      + `<span>${maxed ? t('upgMaxShort') : '💎 ' + cost}</span></button>`;
  }).join('');
  const gain = rebirthGain();
  const info = gain
    ? t('rebirthInfo', { e: state.essence, n: state.rebirths, g: gain })
    : t('rebirthLocked');
  return `<div class="shop">
    <div class="shopTitle"><span>💎 ${t('shopTitle')}</span><b>${Math.floor(state.bank)}</b></div>
    <div class="shopGrid">${rows}</div>
    <div class="rebirth"><span>${info}</span>
      <button id="btnRebirth" class="mini ${gain ? '' : 'poor'}" ${gain ? '' : 'disabled'}>🌀 ${t('rebirthBtn')}</button>
    </div>
  </div>`;
}

function renderShop() {
  const host = document.getElementById('shopHost');
  if (!host) return;
  host.innerHTML = shopHtml();
  host.querySelectorAll('[data-upg]').forEach((b) => { b.onclick = () => buyUpgrade(b.dataset.upg); });
  const rb = document.getElementById('btnRebirth');
  if (rb) rb.onclick = () => armRebirth(rb);
}

/* 自動攻擊：每 autoInterval() 秒自動鎖定最近目標打一下 */
function nearestEnemy() {
  let best = null, bd = Infinity;
  const ox = W / 2, oy = H * 0.62;
  for (const f of state.flies) {
    if (!f || f.dead || f.state === 'dying' || f.friendly) continue;
    const d = dist2(ox, oy, f.x, f.y);
    if (d < bd) { bd = d; best = f; }
  }
  return best;
}

function autoAttack(dt) {
  if (!state.auto || state.paused || state.phase !== 'playing') return;
  if (state.weaponLockT > 0) return;
  state.autoT -= dt;
  if (state.autoT > 0) return;
  const target = nearestEnemy();
  if (!target) { state.autoT = 0.1; return; }
  state.autoT = autoInterval();
  attack(target.x, target.y);
}

"""

rep('idle 層', "function addScore(n) {", IDLE + "function addScore(n) {")

# ---------- 4. addScore 累積點數 ----------
rep('addScore 點數',
    """function addScore(n) {
  state.score = Math.max(0, state.score + n);
  if (n > 0) state.levelScore += n;
  checkUnlock();
  saveScore();
}""",
    """function addScore(n) {
  state.score = Math.max(0, state.score + n);
  if (n > 0) {
    state.levelScore += n;
    state.bank += n * coinRate();          // 分數自動轉成可花用點數
  }
  checkUnlock();
  saveScore();
  saveMeta();
}""")

# ---------- 5. 傷害倍率 ----------
rep('傷害倍率',
    "  if (f.friendly) { addBeeHit(f); return; }\n\n  if (f.isBoss) {",
    "  if (f.friendly) { addBeeHit(f); return; }\n\n"
    "  dmg = Math.max(1, Math.round(dmg * dmgMult()));   // 升級與精華加成\n\n"
    "  if (f.isBoss) {")

# ---------- 6. update 內呼叫自動攻擊 ----------
rep('update 呼叫',
    "  if (state.cool > 0) state.cool -= dt;\n",
    "  if (state.cool > 0) state.cool -= dt;\n  autoAttack(dt);\n")

# ---------- 7. HUD：點數 ----------
rep('HUD 點數更新',
    """    dom.score.innerHTML = `${scoreTxt}<small>${t('scoreUnit')}</small>`;
    state.hud.score = scoreTxt;
  }""",
    """    dom.score.innerHTML = `${scoreTxt}<small>${t('scoreUnit')}</small>`;
    state.hud.score = scoreTxt;
  }
  const bankTxt = String(Math.floor(state.bank));
  if (force || bankTxt !== state.hud.bank) {
    const bankEl = document.getElementById('bank');
    if (bankEl) bankEl.textContent = bankTxt;
    state.hud.bank = bankTxt;
  }""")

# ---------- 8. HUD HTML ----------
rep('HUD HTML',
    """    <div id="weaponChip"><span class="ico" id="weaponIcon">📰</span><span id="weaponName">捲起來的報紙</span></div>
  </div>""",
    """    <div id="weaponChip"><span class="ico" id="weaponIcon">📰</span><span id="weaponName">捲起來的報紙</span></div>
  </div>
  <div class="hud-row third">
    <div id="bankChip">💎 <span id="bank">0</span><small id="bankUnit"></small></div>
    <button id="autoBtn" class="mini on" title="自動攻擊開關">⚡ <span id="autoLbl">AUTO</span></button>
  </div>""")

# ---------- 9. CSS ----------
rep('CSS',
    "  .hint { margin-top: 12px;",
    """  .hud-row.third { margin-top: 4px; font-size: 11px; color: #ffe9b0; }
  #bankChip { display: flex; align-items: center; gap: 4px; font-weight: 700; }
  #bankChip small { opacity: .6; font-size: 9px; }
  #autoBtn { border: 1px solid rgba(255,255,255,.22); background: rgba(0,0,0,.28); color: #cbb894; }
  #autoBtn.on { background: #ffd166; color: #2a2118; border-color: #ffd166; }
  .shop { margin: 8px 0 4px; padding: 8px 9px; border-radius: 12px; background: rgba(0,0,0,.24); border: 1px solid rgba(255,255,255,.10); text-align: left; }
  .shopTitle { display: flex; justify-content: space-between; font-size: 10.5px; letter-spacing: .08em; color: #ffd166; margin-bottom: 6px; }
  .shopGrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
  .shopBtn { display: flex; flex-direction: column; gap: 1px; padding: 6px 4px; border-radius: 10px; background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.14); color: #f3e7cd; font-size: 10px; line-height: 1.4; }
  .shopBtn b { font-size: 10.5px; }
  .shopBtn small { font-size: 9px; opacity: .68; }
  .shopBtn span { font-size: 10px; color: #ffd166; }
  .shopBtn.poor { opacity: .5; }
  .shopBtn.max { border-color: rgba(255,209,102,.5); color: #ffd166; }
  .rebirth { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 8px; font-size: 10px; color: #b9a888; }
  .rebirth .mini.poor { opacity: .45; }
  .hint { margin-top: 12px;""")

# ---------- 10. i18n ----------
EN = """    scoreUnit: 'pts',
    bankUnit: 'pts',
    autoOn: 'AUTO', autoOff: 'MANUAL',
    shopTitle: 'UPGRADE', upg_dmg: 'POWER', upg_rate: 'AUTO RATE', upg_coin: 'POINTS GAIN',
    upgMax: 'Already maxed out', upgMaxShort: 'MAX',
    upgPoor: 'Not enough points — need {n} more', upgBought: '{name} Lv {lv}',
    rebirthBtn: 'REBIRTH', rebirthConfirm: 'TAP AGAIN',
    rebirthInfo: 'Essence {e} · Rebirths {n} · Next +{g}',
    rebirthLocked: 'Reach level 20 or 30,000 pts to rebirth',
    rebirthDone: 'Rebirth! +{g} essence (damage & points +{g}%)',"""
rep('i18n en', "    scoreUnit: 'pts',", EN)

ZH = """    scoreUnit: '分',
    bankUnit: '點',
    autoOn: '自動', autoOff: '手動',
    shopTitle: '武器升級', upg_dmg: '威力', upg_rate: '自動射速', upg_coin: '點數轉換',
    upgMax: '已滿級', upgMaxShort: '滿級',
    upgPoor: '點數不足，還差 {n}', upgBought: '{name} 升到 Lv {lv}',
    rebirthBtn: '轉生', rebirthConfirm: '再按一次',
    rebirthInfo: '精華 {e} · 已轉生 {n} 次 · 這次可得 +{g}',
    rebirthLocked: '打到第 20 關或 30,000 分才能轉生',
    rebirthDone: '轉生完成，精華 +{g}（傷害與點數 +{g}%）',"""
rep('i18n zh', "    scoreUnit: '分',", ZH)

# ---------- 11. 選單放入商店 ----------
rep('選單商店',
    """    <div class="btns"><button id="btnStart" class="primary">${t('startFrom1')}</button></div>""",
    """    <div id="shopHost">${shopHtml()}</div>
    <div class="btns"><button id="btnStart" class="primary">${t('startFrom1')}</button></div>""")

# ---------- 12. showStart 綁定 ----------
rep('showStart 綁定',
    "  dom.modal.classList.remove('hidden');\n  document.getElementById('profileName').textContent = PROFILE.name;",
    "  dom.modal.classList.remove('hidden');\n  renderShop();\n  updateAutoBtn();\n  document.getElementById('profileName').textContent = PROFILE.name;")

# ---------- 13. 開機載入 meta ----------
rep('開機 loadMeta',
    "state.score = loadScore();\nstate.unlocked = unlockedFromScore(state.score);",
    "state.score = loadScore();\nloadMeta();\n"
    "state.unlocked = Math.max(unlockedFromScore(state.score), clamp(1 + Math.floor(state.essence / 10), 1, 5));")

# ---------- 14. autoBtn 綁定 ----------
rep('autoBtn 綁定',
    "document.getElementById('muteBtn').addEventListener('click', (e) => {",
    "const _autoBtnEl = document.getElementById('autoBtn');\n"
    "if (_autoBtnEl) _autoBtnEl.addEventListener('click', () => { Sfx.init(); toggleAuto(); });\n"
    "document.getElementById('muteBtn').addEventListener('click', (e) => {")

# ---------- 15. 最高關卡追蹤 ----------
rep('deepest 追蹤',
    """function saveProgress(level) {
  try {
    const p = loadProgress();
    p[level] = true;""",
    """function saveProgress(level) {
  if (level > state.deepest) { state.deepest = level; saveMeta(); }
  try {
    const p = loadProgress();
    p[level] = true;""")

# ---------- 16. __game 測試介面 ----------
rep('__game 介面',
    "  state, LEVELS, WEAPONS, FLY_TYPES,",
    "  state, LEVELS, WEAPONS, FLY_TYPES, UPGRADES,\n"
    "  buyUpgrade, doRebirth, rebirthGain, toggleAuto, autoAttack, nearestEnemy,\n"
    "  dmgMult, coinRate, autoInterval, upgCost, loadMeta, saveMeta,")

io.open(P, 'w', encoding='utf-8').write(src)
print('套用:', len(applied), '跳過:', len(skipped))
for a in applied: print('  ✓', a)
for s in skipped: print('  -', s)
print('bytes:', len(orig), '->', len(src))
