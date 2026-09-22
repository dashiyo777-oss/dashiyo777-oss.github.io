#!/usr/bin/env node
// 「問題・疑惑」evidence に一次情報URLを必須化する。
//
// 背景:
//   2026-09-22、note読者からの指摘を端緒に不祥事フラグの全件照合を行ったところ、
//   自民党の公式リスト（2024年2月13日公表の不記載議員85人 / 2024年4月4日の党紀委員会
//   処分39人）のいずれにも該当しない議員41人に「不記載」「役職停止処分」が記載されて
//   いた。削除した虚偽 evidence の共通点は、src に「自由民主党党紀委員会処分決定公報」
//   等の公的文書名を掲げながら url が空であったこと——つまり一次情報による裏取りが
//   一度も行われていなかったことである。
//   実在の政治家に対する事実無根の不祥事記載は最も重い種類の誤りであるため、
//   同じ構造の誤りを機械的に止める。
//
// 方式: ratchet（ラチェット）
//   既存の未裏取りエントリは scripts/evidence_source_baseline.json に「既知の負債」
//   として登録し、当面は許容する。ただし
//     - baseline に無い新規の url 空エントリは一切許さない
//     - baseline は「縮む」方向にしか更新できない（url を付けたら baseline から外す）
//   ため、負債は増えず、解消したぶんだけ確実に減る。
//
// 使い方:
//   node scripts/validate_evidence_sources.js              検証
//   node scripts/validate_evidence_sources.js --prune      解消済みidをbaselineから削除
//
// 注意: --prune は「解消済みidの削除」しか行わない。新規の未裏取りエントリを
//       baseline に追加する機能は意図的に設けていない（負債の追加を防ぐため）。

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const BASELINE_PATH = path.join(ROOT, 'scripts', 'evidence_source_baseline.json');
const TARGET_CAT = '問題・疑惑';

const dataJs = fs.readFileSync(path.join(ROOT, 'data.js'), 'utf8');
const EVIDENCE = vm.runInNewContext(dataJs + ';EVIDENCE', {});

let baseline = { ids: [] };
if (fs.existsSync(BASELINE_PATH)) {
  baseline = JSON.parse(fs.readFileSync(BASELINE_PATH, 'utf8'));
}
const baselineIds = new Set(baseline.ids || []);

const errors = [];
const warnings = [];

const has = (v) => typeof v === 'string' && v.trim() !== '';
const evById = new Map();
for (const e of EVIDENCE) evById.set(e.id, e);

// ---------------------------------------------------------------------------
// A. 「問題・疑惑」evidence 本体の検証
// ---------------------------------------------------------------------------
const resolved = [];      // baseline 登録済みだが url が付いた（＝解消済み）
const stale = [];         // baseline 登録済みだが該当しなくなった

for (const e of EVIDENCE) {
  if (e.cat !== TARGET_CAT) continue;
  const where = `${e.id}（${e.pid}）`;

  if (!has(e.src)) {
    errors.push(`${where}: cat:"${TARGET_CAT}" の evidence に src がありません。出典を明記してください。`);
  }

  if (!has(e.url)) {
    if (baselineIds.has(e.id)) continue;   // 既知の負債として許容
    errors.push(
      `${where}: cat:"${TARGET_CAT}" の evidence に url がありません。\n` +
      `      summary: ${e.summary || '(なし)'}\n` +
      `      src: ${e.src || '(なし)'}\n` +
      `      不祥事の記載には一次情報のURLが必須です。src に公的文書名を書くだけでは\n` +
      `      裏取りになりません（2026-09の事実無根記載41件はすべてこの形でした）。`
    );
    continue;
  }

  // url がある場合の形式チェック
  let u = null;
  try {
    u = new URL(e.url);
  } catch (_) {
    errors.push(`${where}: url が URL として解釈できません: ${e.url}`);
    continue;
  }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') {
    errors.push(`${where}: url は http(s) である必要があります: ${e.url}`);
  }
  if (/(^|\.)google\.[a-z.]+$/.test(u.hostname) && u.pathname.startsWith('/search')) {
    errors.push(`${where}: 検索結果ページは出典になりません。該当記事・公的資料のURLを指定してください: ${e.url}`);
  }
  if (baselineIds.has(e.id)) resolved.push(e.id);

  // 警告: 二次情報のみを出典とする不祥事記載
  if (u.hostname === 'ja.wikipedia.org' || u.hostname === 'en.wikipedia.org') {
    warnings.push(`${where}: 出典が Wikipedia（二次情報）です。報道・公的資料への差し替えが望まれます。`);
  }
}

// ---------------------------------------------------------------------------
// B. baseline の陳腐化チェック（ratchet を後戻りさせない）
// ---------------------------------------------------------------------------
for (const id of baselineIds) {
  const e = evById.get(id);
  if (!e) {
    stale.push(`${id}: evidence が存在しません（削除済み）`);
  } else if (e.cat !== TARGET_CAT) {
    stale.push(`${id}: cat が "${e.cat}" に変わりました`);
  }
}

// ---------------------------------------------------------------------------
// --prune: 解消済み・陳腐化した id を baseline から取り除く
// ---------------------------------------------------------------------------
if (process.argv.includes('--prune')) {
  const staleIds = new Set(stale.map((s) => s.split(':')[0]));
  const keep = (baseline.ids || []).filter((id) => !resolved.includes(id) && !staleIds.has(id));
  const removed = (baseline.ids || []).length - keep.length;
  baseline.ids = keep;
  baseline.updated = new Date().toISOString().slice(0, 10);
  fs.writeFileSync(BASELINE_PATH, JSON.stringify(baseline, null, 2) + '\n', 'utf8');
  console.log(`✅ baseline から ${removed}件 を削除しました（残り ${keep.length}件）`);
  process.exit(0);
}

if (resolved.length) {
  errors.push(
    `baseline に登録されたまま url が付与された evidence が ${resolved.length}件 あります: ${resolved.join(', ')}\n` +
    `      裏取りが済んだものは baseline から外してください:\n` +
    `        node scripts/validate_evidence_sources.js --prune`
  );
}
if (stale.length) {
  errors.push(
    `baseline に不要なエントリが ${stale.length}件 あります:\n` +
    stale.map((s) => '        - ' + s).join('\n') + '\n' +
    `      次のコマンドで整理してください:\n` +
    `        node scripts/validate_evidence_sources.js --prune`
  );
}

// ---------------------------------------------------------------------------
// 出力
// ---------------------------------------------------------------------------
const total = EVIDENCE.filter((e) => e.cat === TARGET_CAT).length;
const debt = EVIDENCE.filter((e) => e.cat === TARGET_CAT && !has(e.url) && baselineIds.has(e.id)).length;

if (errors.length) {
  console.error(`❌ 問題・疑惑 evidence の出典検証に失敗しました（${errors.length}件）\n`);
  errors.forEach((m) => console.error('  - ' + m));
  console.error(
    `\n  cat:"${TARGET_CAT}" の evidence は実在の人物に対する不利益な事実の主張です。\n` +
    `  一次情報のURLを伴わない記載は追加できません。\n` +
    `  詳細は CLAUDE.md「問題・疑惑 evidence の出典必須ルール」を参照してください。`
  );
  process.exit(1);
}

console.log(`✅ 問題・疑惑 evidence の出典 OK（${total}件中 ${total - debt}件が裏取り済み / 既知の未裏取り ${debt}件）`);
if (warnings.length) {
  console.log(`\n⚠️  警告 ${warnings.length}件（CIは失敗しません）:`);
  warnings.forEach((m) => console.log('  - ' + m));
}
