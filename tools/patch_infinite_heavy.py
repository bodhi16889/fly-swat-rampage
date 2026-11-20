#!/usr/bin/env python3
"""第二階段改造：無限關卡 + 3 把可無限升級的重型武器。可重複執行。"""
import io, os, re, sys

P = os.path.expanduser('~/fly-swat-rampage/index.html')
src = io.open(P, encoding='utf-8').read()
applied, skipped = [], []


def rep(tag, old, new, count=1):
    global src
    n = src.count(old)
    if n == 0:
        if new.split('\n')[0] in src:
            skipped.append(tag + '（已套用）'); return
        raise SystemExit(f'✗ 找不到錨點：{tag}\n{old[:160]}')
    if n != count:
        raise SystemExit(f'✗ 錨點 {tag} 出現 {n} 次（預期 {count}）')
    src = src.replace(old, new, count)
    applied.append(tag)


# ---------- 1. 20 把武器 → 3 把重型武器 ----------
i0 = src.index('const WEAPONS = [')
i1 = src.index('const FLY_TYPES', i0)
NEW_WEAPONS = """/* 三把重型武器：種類少、等級無上限（傷害隨等級線性成長）。
   升級消耗「點數」，由分數自動累積，玩家手動按。 */
const WEAPONS = [
  { id: 'hammer', name: '重型碎蠅錘', short: '重錘', icon: '🔨', radius: 120, cooldown: 0.62,
    mode: 'tap', damage: 4, aoe: true, branch: 'heavy' },
  { id: 'flame', name: '重型火焰噴射器', short: '火焰', icon: '🔥', radius: 210, cooldown: 0.30,
    mode: 'holdFan', fanDeg: 74, tick: 0.22, tickDamage: 2, branch: 'heavy' },
  { id: 'plasma', name: '重型電漿炮', short: '電漿', icon: '🔆', radius: 0, cooldown: 0.95,
    mode: 'laser', band: 70, damage: 99, bossDamage: 10, pierce: true, branch: 'heavy' },
];
const WLV_MAX = 9999;             // 實質無上限

"""
if src[i0:i1] != NEW_WEAPONS:
    src = src[:i0] + NEW_WEAPONS + src[i1:]
    applied.append('WEAPONS → 3 把重型')

# ---------- 2. LEVELS 延遲產生（無限關卡） ----------
rep('levelCfg',
    """const LEVELS = {};
for (let n = 1; n <= 100; n++) LEVELS[n] = makeLevel(n);""",
    """const LEVELS = {};
for (let n = 1; n <= 100; n++) LEVELS[n] = makeLevel(n);
/* 無限關卡：超過 100 關即時產生並快取（章節主題循環、每 100 關一階更硬） */
function levelCfg(n) {
  if (LEVELS[n]) return LEVELS[n];
  return (LEVELS[n] = makeLevel(n));
}""")

# ---------- 3. makeLevel 支援無限 ----------
rep('makeLevel 章節循環',
    "  const chapter = CHAPTERS[Math.floor((n - 1) / 20)];\n  const stage = ((n - 1) % 20) + 1;",
    "  const chapter = CHAPTERS[Math.floor((n - 1) / 20) % CHAPTERS.length];\n"
    "  const stage = ((n - 1) % 20) + 1;\n"
    "  const loop = Math.floor((n - 1) / (CHAPTERS.length * 20)) + 1;\n"
    "  const tier = loop - 1;")

rep('makeLevel 數值',
    """    time: 40,
    speedMul: Math.min(1.5, 1 + (n - 1) * 0.0035),
    spawnEvery: Math.max(0.30, 0.95 - n * 0.006),
    targetCount: Math.min(28, 8 + Math.floor(n * 0.17)),""",
    """    time: 40,
    loop,
    tier,
    hpMul: 1 + tier * 0.8,
    speedMul: Math.min(2.8, 1 + (n - 1) * 0.0035),
    spawnEvery: Math.max(0.14, 0.95 - n * 0.006),
    targetCount: Math.min(60, 8 + Math.floor(n * 0.17)),""")

# ---------- 4. LEVELS[...] → levelCfg(...) ----------
body = src
pat = re.compile(r'LEVELS\[([^\]\n]+)\]')
def sub(m):
    expr = m.group(1)
    return f'levelCfg({expr})'
# 只取代讀取（排除 levelCfg 內部與指派）
count = 0
out_lines = []
for line in body.split('\n'):
    if 'LEVELS[n] = makeLevel' in line or 'LEVELS[n] = cfg' in line or 'if (LEVELS[n])' in line:
        out_lines.append(line); continue
    new_line, k = pat.subn(sub, line)
    count += k
    out_lines.append(new_line)
if count:
    src = '\n'.join(out_lines)
    applied.append(f'LEVELS[] → levelCfg()（{count} 處）')

# ---------- 5. state ----------
rep('state 武器等級',
    "  unlocked: 1,\n  weaponIndex: 0,",
    "  unlocked: WEAPONS.length,\n  weaponIndex: 0,\n  wlv: [0, 0, 0],          // 三把重型武器各自的等級（無上限）")

rep('state upg',
    "  upg: { dmg: 0, rate: 0, coin: 0 },",
    "  upg: { rate: 0, coin: 0 },")

# ---------- 6. UPGRADES：只留射速與點數轉換 ----------
rep('UPGRADES',
    """const UPGRADES = {
  dmg:  { base: 80,  mult: 1.30, max: 20, step: 0.15 },   // 傷害 +15%/級
  rate: { base: 100, mult: 1.32, max: 15, step: 0.06 },   // 自動間隔 -6%/級
  coin: { base: 150, mult: 1.35, max: 10, step: 0.05 },   // 得分→點數 +5%/級
};""",
    """const UPGRADES = {
  rate: { base: 120, mult: 1.30, max: 20, step: 0.05 },   // 自動間隔 -5%/級
  coin: { base: 150, mult: 1.32, max: 15, step: 0.05 },   // 得分→點數 +5%/級
};""")

# ---------- 7. loadMeta / saveMeta 加 wlv ----------
rep('loadMeta',
    """    const u = m.upg || {};
    state.upg = {
      dmg: clamp(u.dmg | 0, 0, UPGRADES.dmg.max),
      rate: clamp(u.rate | 0, 0, UPGRADES.rate.max),
      coin: clamp(u.coin | 0, 0, UPGRADES.coin.max),
    };""",
    """    const u = m.upg || {};
    state.upg = {
      rate: clamp(u.rate | 0, 0, UPGRADES.rate.max),
      coin: clamp(u.coin | 0, 0, UPGRADES.coin.max),
    };
    const w = Array.isArray(m.wlv) ? m.wlv : [];
    state.wlv = WEAPONS.map((_, i) => Math.max(0, Math.min(WLV_MAX, w[i] | 0)));""")

rep('saveMeta',
    "      bank: Math.round(state.bank), upg: state.upg, essence: state.essence,",
    "      bank: Math.round(state.bank), upg: state.upg, wlv: state.wlv, essence: state.essence,")

# ---------- 8. 傷害倍率：只剩精華 ----------
rep('dmgMult',
    "function dmgMult() { return 1 + UPGRADES.dmg.step * state.upg.dmg + 0.01 * state.essence; }",
    "function dmgMult() { return 1 + 0.01 * state.essence; }   // 武器傷害另外由等級成長")

# ---------- 9. 武器解鎖：三把一開始全開 ----------
rep('checkUnlock',
    """function checkUnlock() {
  let next = state.unlocked;
  while (next < WEAPONS.length && state.score >= WEAPONS[next].unlock) next++;
  if (next > state.unlocked) {
    const latest = WEAPONS[next - 1];
    state.unlocked = next;
    state.weaponIndex = next - 1;
    showToast(t('weaponUp', { name: wName(latest) }));
    Sfx.upgrade();
    state.effects.push({ type: 'flash', ttl: 0.35, t: 0, color: latest.id === 'laser' ? '#a8e6ff' : '#ffe0a8' });
    renderWeaponBar();
    updateWeaponChip();
  }
}""",
    """function checkUnlock() {
  /* 三把重型武器開局全部可用；成長改成「武器等級」而不是「解鎖新武器」 */
  if (state.unlocked !== WEAPONS.length) { state.unlocked = WEAPONS.length; renderWeaponBar(); }
}""")

rep('unlockedFromScore',
    """function unlockedFromScore(score) {
  let n = 1;
  while (n < WEAPONS.length && score >= WEAPONS[n].unlock) n++;
  return n;
}""",
    """function unlockedFromScore() { return WEAPONS.length; }   // 全部一開始就開""")

# ---------- 10. currentWeapon：依等級放大 ----------
rep('currentWeapon',
    "function currentWeapon() { return WEAPONS[state.weaponIndex]; }",
    """function weaponLv(i) { return state.wlv[i] || 0; }
function weaponDmgMul(i) { return 1 + 0.3 * weaponLv(i); }
function wCost(i) { return Math.round(80 * Math.pow(1.30, weaponLv(i)) * (1 + i * 0.9)); }

function currentWeapon() {
  const base = WEAPONS[state.weaponIndex] || WEAPONS[0];
  const lv = weaponLv(state.weaponIndex);
  if (!lv) return base;
  const k = weaponDmgMul(state.weaponIndex);
  const out = Object.assign({}, base);
  out.lv = lv;
  out.damage = Math.round((base.damage || 1) * k);
  if (base.tickDamage) out.tickDamage = +(base.tickDamage * k).toFixed(2);
  if (base.radius) out.radius = Math.round(base.radius * (1 + 0.02 * lv));
  if (base.bossDamage) out.bossDamage = Math.round(base.bossDamage * k);
  if (base.band) out.band = Math.round(base.band * (1 + 0.02 * lv));
  return out;
}""")

# ---------- 11. 買武器升級 ----------
rep('buyWeaponUpgrade',
    "function toggleAuto() {",
    """function buyWeaponUpgrade(i) {
  if (i < 0 || i >= WEAPONS.length) return false;
  if (weaponLv(i) >= WLV_MAX) { showToast(t('upgMax')); return false; }
  const cost = wCost(i);
  if (state.bank < cost) { showToast(t('upgPoor', { n: cost - Math.floor(state.bank) })); return false; }
  state.bank -= cost;
  state.wlv[i] = weaponLv(i) + 1;
  saveMeta();
  if (typeof Sfx !== 'undefined' && Sfx.upgrade) Sfx.upgrade();
  showToast(t('wUpBought', { name: wName(WEAPONS[i]), lv: state.wlv[i] }));
  if (i === state.weaponIndex) updateWeaponChip();
  renderShop();
  updateHud(true);
  return true;
}

function toggleAuto() {""")

# ---------- 12. 商店：三把武器 + 射速 + 點數 ----------
rep('shopHtml',
    """function shopHtml() {
  const rows = ['dmg', 'rate', 'coin'].map((k) => {
    const u = UPGRADES[k], lv = state.upg[k], maxed = lv >= u.max;
    const cost = upgCost(k), afford = !maxed && state.bank >= cost;
    return `<button class="shopBtn${maxed ? ' max' : ''}${afford || maxed ? '' : ' poor'}" data-upg="${k}" ${maxed ? 'disabled' : ''}>`
      + `<b>${t('upg_' + k)}</b><small>Lv ${lv}/${u.max}</small>`
      + `<span>${maxed ? t('upgMaxShort') : '💎 ' + cost}</span></button>`;
  }).join('');""",
    """function shopHtml() {
  const rows = WEAPONS.map((w, i) => {
    const lv = weaponLv(i), cost = wCost(i), afford = state.bank >= cost;
    return `<button class="shopBtn w${afford ? '' : ' poor'}" data-wup="${i}">`
      + `<b>${w.icon} ${LANG === 'zh' ? w.name : w.short}</b>`
      + `<small>Lv ${lv} · ${t('dmgMul', { x: weaponDmgMul(i).toFixed(1) })}</small>`
      + `<span>💎 ${cost}</span></button>`;
  }).join('');
  const grows = ['rate', 'coin'].map((k) => {
    const u = UPGRADES[k], lv = state.upg[k], maxed = lv >= u.max;
    const cost = upgCost(k), afford = !maxed && state.bank >= cost;
    return `<button class="shopBtn g${maxed ? ' max' : ''}${afford || maxed ? '' : ' poor'}" data-upg="${k}" ${maxed ? 'disabled' : ''}>`
      + `<b>${t('upg_' + k)}</b><small>Lv ${lv}/${u.max}</small>`
      + `<span>${maxed ? t('upgMaxShort') : '💎 ' + cost}</span></button>`;
  }).join('');""")

rep('shopHtml 版面',
    """    <div class="shopGrid">${rows}</div>""",
    """    <div class="shopGrid w">${rows}</div>
    <div class="shopGrid g">${grows}</div>""")

rep('renderShop 綁定',
    "  host.querySelectorAll('[data-upg]').forEach((b) => { b.onclick = () => buyUpgrade(b.dataset.upg); });",
    "  host.querySelectorAll('[data-upg]').forEach((b) => { b.onclick = () => buyUpgrade(b.dataset.upg); });\n"
    "  host.querySelectorAll('[data-wup]').forEach((b) => { b.onclick = () => buyWeaponUpgrade(+b.dataset.wup); });")

# ---------- 13. 轉生重置武器等級 ----------
rep('rebirth 重置',
    """  state.bank = 0;
  state.upg = { dmg: 0, rate: 0, coin: 0 };
  state.score = 0;
  state.deepest = 0;
  state.level = 1;
  state.unlocked = clamp(1 + Math.floor(state.essence / 10), 1, 5);
  state.weaponIndex = state.unlocked - 1;""",
    """  state.bank = 0;
  state.upg = { rate: 0, coin: 0 };
  state.wlv = WEAPONS.map(() => Math.round(state.essence / 25));   // 精華換起始武器等級
  state.score = 0;
  state.deepest = 0;
  state.level = 1;
  state.unlocked = WEAPONS.length;
  state.weaponIndex = 0;""")

# ---------- 14. HUD 武器名顯示等級 ----------
rep('武器名顯示等級',
    "  dom.weaponName.textContent = wName(w);",
    "  const lv = weaponLv(state.weaponIndex);\n"
    "  dom.weaponName.textContent = wName(w) + (lv ? ' Lv' + lv : '');")

# ---------- 15. 生成關卡時套用 hpMul ----------
rep('spawnFly 血量倍率',
    "  const f = new Fly(type);\n  if (cfg.speedMul) { f.speed *= cfg.speedMul; f.baseSpeed = f.speed; }",
    "  const f = new Fly(type);\n"
    "  if (cfg.speedMul) { f.speed *= cfg.speedMul; f.baseSpeed = f.speed; }\n"
    "  const hpMul = cfg.hpMul || 1;\n"
    "  if (hpMul > 1 && !f.friendly) { f.hp = f.maxHp = Math.max(1, Math.round(f.hp * hpMul)); }")

rep('Boss 血量倍率',
    "    const hp = state.levelConfig.bossHp || FLY_TYPES.boss.hp;",
    "    const hp = Math.round((state.levelConfig.bossHp || FLY_TYPES.boss.hp) * (state.levelConfig.hpMul || 1));")

# ---------- 16. 選單改成無限關卡階梯 ----------
rep('選單計算',
    """  const chap = clamp(state.menuChapter, 1, CHAPTERS.length);
  state.menuChapter = chap;
  const chapter = CHAPTERS[chap - 1];
  let chapCleared = 0;
  for (let i = 0; i < 20; i++) if (prog[(chap - 1) * 20 + i + 1]) chapCleared++;

  const chapBtns = CHAPTERS.map((c) => {
    const first = (c.id - 1) * 20 + 1;
    const unlocked = levelUnlocked(first);
    let done = 0;
    for (let i = 0; i < 20; i++) if (prog[first + i]) done++;
    return `<button class="chtab${c.id === chap ? ' active' : ''}" data-chap="${c.id}" ${unlocked ? '' : 'disabled'}>
      ${LANG === 'zh' ? c.name : c.name_en}<small>${done}/20</small></button>`;
  }).join('');

  const cells = Array.from({ length: 20 }, (_, i) => {
    const n = (chap - 1) * 20 + i + 1;
    const unlocked = levelUnlocked(n);
    const cleared = !!prog[n];
    return `<button class="lvcell${unlocked ? '' : ' locked'}" data-level="${n}" ${unlocked ? '' : 'disabled'}>
      <b>${cleared ? t('levelCleared') : (unlocked ? '▶' : t('locked'))}</b><span>${n}</span></button>`;
  }).join('');""",
    """  const nextN = maxCleared + 1;
  const nextCfg = levelCfg(nextN);
  const loop = nextCfg.loop || 1;
  const themeName = LANG === 'zh' ? nextCfg.name : nextCfg.name_en;""")

rep('選單 HTML',
    """    <div class="chapters">${chapBtns}</div>
    <div class="chapterInfo"><span>${LANG === 'zh' ? chapter.name : chapter.name_en} · ${chapCleared}/20</span>""",
    """    <div class="ladder">
      <div class="ladTop"><span>🏁 ${t('highestLevel', { n: maxCleared })}</span><span>♾️ ${t('loopLabel', { n: loop })}</span></div>
      <button class="lv next" id="btnNextLv"><b>▶ ${t('levelN', { n: nextN, name: lvName(nextN) })}</b><span>${t('nextSub')}</span></button>
    </div>
    <div class="chapterInfo"><span>${themeName}</span>""")

rep('選單移除 20 格',
    "    <div class=\"lvgrid\">${cells}</div>\n", "")

rep('選單 handler',
    """  document.getElementById('btnStart').onclick = () => { Sfx.init(); state.menuChapter = 1; startLevel(1, true); };""",
    """  document.getElementById('btnStart').onclick = () => { Sfx.init(); state.menuChapter = 1; startLevel(1, true); };
  const nextLvBtn = document.getElementById('btnNextLv');
  if (nextLvBtn) nextLvBtn.onclick = () => { Sfx.init(); startLevel(nextN, false); };""")

rep('選單移除舊 handler',
    """  document.getElementById('btnBoard').onclick = () => showBoard(chap);
  const globalBtn = document.getElementById('btnGlobal');
  if (globalBtn) globalBtn.onclick = () => showGlobalBoard(chap);
  dom.card.querySelectorAll('.chtab').forEach((btn) => {
    if (btn.disabled) return;
    btn.onclick = () => { state.menuChapter = +btn.dataset.chap; showStart(); };
  });
  dom.card.querySelectorAll('.lvcell[data-level]').forEach((btn) => {
    if (btn.disabled) return;
    btn.onclick = () => { Sfx.init(); startLevel(+btn.dataset.level, false); };
  });""",
    """  document.getElementById('btnBoard').onclick = () => showBoard(nextCfg.chapter);
  const globalBtn = document.getElementById('btnGlobal');
  if (globalBtn) globalBtn.onclick = () => showGlobalBoard(nextCfg.chapter);""")

# ---------- 17. 結算：永遠有下一關 ----------
rep('showResult 無限',
    "  const last = !state.endless && state.level >= 100;",
    "  const last = false;   // 無限關卡：永遠有下一關（第 100 關不再是最後）")

# ---------- 18. 開機：全部武器解鎖 ----------
rep('開機解鎖',
    "state.unlocked = Math.max(unlockedFromScore(state.score), clamp(1 + Math.floor(state.essence / 10), 1, 5));",
    "state.unlocked = WEAPONS.length;   // 三把重型武器開局全開")

# ---------- 19. __game 介面 ----------
rep('__game 武器介面',
    "  buyUpgrade, doRebirth, rebirthGain, toggleAuto, autoAttack, nearestEnemy,",
    "  buyUpgrade, buyWeaponUpgrade, wCost, weaponLv, weaponDmgMul, currentWeapon,\n"
    "  selectWeapon, levelCfg, makeLevel, levelUnlocked,\n"
    "  buyUpgrade, doRebirth, rebirthGain, toggleAuto, autoAttack, nearestEnemy,")

# ---------- 20. CSS ----------
rep('CSS 階梯與商店',
    "  .shopGrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }",
    """  .shopGrid { display: grid; gap: 6px; }
  .shopGrid.w { grid-template-columns: repeat(3, 1fr); }
  .shopGrid.g { grid-template-columns: repeat(2, 1fr); margin-top: 6px; }
  .ladder { margin: 8px 0 4px; }
  .ladTop { display: flex; justify-content: space-between; font-size: 10px; color: #b9a888; margin-bottom: 6px; }
  .lv.next { display: flex; align-items: center; justify-content: space-between; width: 100%; }
  .lv.next b { font-size: 12px; }
  .lv.next span { font-size: 10px; opacity: .7; }""")

# ---------- 21. i18n ----------
rep('i18n en 新鍵',
    "    rebirthDone: 'Rebirth! +{g} essence (damage & points +{g}%)',",
    """    rebirthDone: 'Rebirth! +{g} essence (damage & points +{g}%)',
    dmgMul: 'dmg x{x}',
    wUpBought: '{name} Lv {lv}',
    highestLevel: 'Cleared: {n}',
    loopLabel: 'Loop {n}',
    nextSub: 'Endless levels',""")

rep('i18n zh 新鍵',
    "    rebirthDone: '轉生完成，精華 +{g}（傷害與點數 +{g}%）',",
    """    rebirthDone: '轉生完成，精華 +{g}（傷害與點數 +{g}%）',
    dmgMul: '傷害 ×{x}',
    wUpBought: '{name} 升到 Lv {lv}',
    highestLevel: '已通關 {n} 關',
    loopLabel: '第 {n} 輪',
    nextSub: '無限關卡，越後面越硬',""")

io.open(P, 'w', encoding='utf-8').write(src)
print('套用', len(applied), '項；跳過', len(skipped))
for a in applied: print('  ✓', a)
for s in skipped: print('  -', s)
