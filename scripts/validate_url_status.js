#!/usr/bin/env node
/**
 * evidence_url_status.js の健全性を検査する。
 *
 * このファイルは週次ワークフローの bot が全面的に書き換え（389行の入れ替え）、
 * politician.html が読み込んで「⚠ リンク切れ」の表示に使う。
 * それにもかかわらず、どこからも検査されていなかった。壊れた形で書かれても
 * 誰も気づかず、詳細ページの表示だけが静かに崩れる状態だった。
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const STATUS_FILE = path.join(ROOT, 'evidence_url_status.js');
const DATA_FILE = path.join(ROOT, 'data.js');

const VALID_STATES = new Set(['ok', 'suspect', 'dead', 'unverified', 'unchecked']);
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function load(file, name) {
  const src = fs.readFileSync(file, 'utf8');
  let value;
  try {
    // const 宣言は sandbox のグローバルに乗らないため、末尾で名前を評価させる
    value = vm.runInNewContext(`${src};${name}`, {});
  } catch (e) {
    console.error(`❌ ${path.basename(file)}: 読み込みに失敗しました — ${e.message}`);
    process.exit(1);
  }
  if (!value || typeof value !== 'object') {
    console.error(`❌ ${path.basename(file)}: ${name} が定義されていません`);
    process.exit(1);
  }
  return value;
}

if (!fs.existsSync(STATUS_FILE)) {
  console.log('evidence_url_status.js が無いため検査をスキップします（初回実行前）');
  process.exit(0);
}

const status = load(STATUS_FILE, 'EVIDENCE_URL_STATUS');
const errors = [];

const ids = Object.keys(status);
if (!ids.length) errors.push('EVIDENCE_URL_STATUS が空です');

for (const id of ids) {
  const s = status[id];
  const at = `${id}`;
  if (!s || typeof s !== 'object') { errors.push(`${at}: オブジェクトではありません`); continue; }
  if (typeof s.url !== 'string' || !/^https?:\/\//.test(s.url)) {
    errors.push(`${at}: url が http(s) で始まっていません（${s.url}）`);
  }
  if (!VALID_STATES.has(s.state)) errors.push(`${at}: state が不正です（${s.state}）`);
  for (const key of ['first_ok', 'last_ok']) {
    if (s[key] !== null && !DATE_RE.test(String(s[key]))) {
      errors.push(`${at}: ${key} が YYYY-MM-DD でも null でもありません（${s[key]}）`);
    }
  }
  if (!DATE_RE.test(String(s.last_checked))) {
    errors.push(`${at}: last_checked が YYYY-MM-DD ではありません（${s.last_checked}）`);
  }
  for (const key of ['fail_streak', 'gone_streak']) {
    if (!Number.isInteger(s[key]) || s[key] < 0) {
      errors.push(`${at}: ${key} が0以上の整数ではありません（${s[key]}）`);
    }
  }
  // dead は「2回連続で404」でしか成立しない。これが崩れると、生きている
  // ページに「リンク切れ」と表示してしまう（2026年9月に実際に起きた）
  if (s.state === 'dead' && s.gone_streak < 2) {
    errors.push(`${at}: dead なのに gone_streak が ${s.gone_streak} です`);
  }
  if (s.state === 'ok' && (s.fail_streak !== 0 || s.gone_streak !== 0)) {
    errors.push(`${at}: ok なのに streak が残っています`);
  }
  // last_ok があるなら first_ok もあるはず
  if (s.last_ok && !s.first_ok) errors.push(`${at}: last_ok があるのに first_ok がありません`);
}

// data.js の evidence との食い違いは、URLを差し替えた直後や evidence を
// 削除した直後には必ず起きる（記録は次の週次実行で作り直される）。
// したがってこれは失敗にはせず、警告として出すだけにする。
// 検査を厳しくしすぎて正当な変更を止めるのは、検査が無いのと別の形で害になる
const warnings = [];
if (fs.existsSync(DATA_FILE)) {
  const evidence = load(DATA_FILE, 'EVIDENCE');
  const byId = new Map(evidence.map((e) => [e.id, e]));
  for (const id of ids) {
    const e = byId.get(id);
    if (!e) {
      warnings.push(`${id}: data.js に存在しない evidence の記録が残っています（次回の生存確認で消えます）`);
    } else if (e.url && e.url !== status[id].url) {
      warnings.push(`${id}: data.js の url と記録の url が食い違っています（差し替え直後なら想定どおり）`);
    }
  }
}

if (errors.length) {
  console.error(`❌ evidence_url_status.js に問題があります（${errors.length}件）`);
  for (const e of errors.slice(0, 40)) console.error(`  - ${e}`);
  if (errors.length > 40) console.error(`  … 他 ${errors.length - 40}件`);
  process.exit(1);
}

if (warnings.length) {
  console.log(`⚠️  警告 ${warnings.length}件（CIは失敗しません）:`);
  for (const w of warnings.slice(0, 20)) console.log(`  - ${w}`);
  if (warnings.length > 20) console.log(`  … 他 ${warnings.length - 20}件`);
}

const counts = ids.reduce((acc, id) => {
  acc[status[id].state] = (acc[status[id].state] || 0) + 1;
  return acc;
}, {});
console.log(`✅ evidence_url_status.js OK（${ids.length}件 / ${JSON.stringify(counts)}）`);
