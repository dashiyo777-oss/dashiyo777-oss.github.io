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
const POLITICIANS = vm.runInNewContext(dataJs + ';POLITICIANS', {});

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
// A2. 出典名の創作・内容空疎・テンプレート量産の検出（全カテゴリ）
//
//   2026-09の全件検証で、以下4種類の量産パターンが見つかった。
//   いずれも「もっともらしいが実在しない」記載であり、機械的に止める。
//     (1) 実在しない公的文書名（「〜公報資料」「〜処分決定公報」等）
//     (2) 内容が空疎な evidence（「Wikipediaに記述が確認された」等、事実を述べていない）
//     (3) 同一 detail の複数議員への使い回し（テンプレート量産）
//     (4) 存在しない議員IDを参照する孤児 evidence
// ---------------------------------------------------------------------------
const FAKE_DOC = [
  /公報資料$/, /公報記録$/, /職務記録公報/, /政策実績公報/, /審議記録公報/,
  /処分決定公報/, /処分決定通達/, /処分決定通知/, /活動記録・公式公報/,
  // 2026-09-22 の実績61件の検証で、下記の名称を持つ文書も一切実在しないことが判明した。
  // 「◯◯省政策実績アーカイブ」「◯◯庁政策成果報告」「◯◯省実績記録」等、
  // 官公庁の刊行物を装いながら検索しても存在しない名称の一群。
  /政策実績アーカイブ/, /実績アーカイブ/, /政策成果報告/, /政策実績資料/,
  /実績記録$/, /職務報告資料/, /政策実績白書/, /実績白書/, /職務活動記録/,
  // 2026-09-22 の再検証で、上記を末尾一致（$）で書いていたため
  // 「復興庁 政策実績白書資料」のように語尾に1語足しただけの出典が素通りしていた。
  // 部分一致に改めている。
  //
  // 首長20件が使っていた「◯◯県庁実績」「◯◯県庁政策実績」も同じ構造。
  // 県庁が「実績」という名の刊行物を出しているわけではなく、出典として機能しない。
  /[都道府県]庁実績/, /[都道府県]庁政策実績/, /[都道府県]庁成果/,
];

// 資料体（コーパス）の名前だけで、会期・委員会・日付のいずれも特定していない出典。
// 「参議院会議録」とだけ書かれていても、どの会議録の何ページを指すのか分からず、
// 読者が検証できないため出典として機能しない。2026-09-22 の検証では、この出典名を
// 持つ40件のうち複数で、当人の経歴と矛盾する記載（知事経験のない議員への
// 「知事経験に基づく」、閣僚経験のない議員への「大臣としての経験」等）が見つかった。
const CORPUS_ONLY = [/^参議院会議録$/, /^衆議院会議録$/, /^国会会議録$/];
const EMPTY_DETAIL = [
  /Wikipediaに.{0,20}記述が確認された/,
  /Wikipediaの記載により.{0,20}確認された/,
];
const pidSet = new Set(POLITICIANS.map((p) => p.id));

for (const e of EVIDENCE) {
  const where = `${e.id}（${e.pid}）`;
  if (!pidSet.has(e.pid)) {
    errors.push(`${where}: 存在しない議員ID "${e.pid}" を参照しています（孤児 evidence）。削除してください。`);
  }
  if (FAKE_DOC.some((re) => re.test(e.src || ''))) {
    errors.push(
      `${where}: 出典名「${e.src}」は実在しない公的文書の疑いがあります。\n` +
      `      「〜公報」「〜公報資料」といった官公庁文書を装った名称は、2026年9月の検証で\n` +
      `      85件すべてが創作と判明しました。実在する資料名とURLを指定してください。`
    );
  }
  if (!has(e.url) && CORPUS_ONLY.some((re) => re.test((e.src || '').trim()))) {
    errors.push(
      `${where}: 出典「${e.src}」は資料体の名称のみで、会期・委員会・日付のいずれも\n` +
      `      特定していないため検証できません。会議録を出典にする場合は、国会会議録検索\n` +
      `      システム（https://kokkai.ndl.go.jp/）の該当ページのURLを指定してください。`
    );
  }
  if (EMPTY_DETAIL.some((re) => re.test(e.detail || ''))) {
    errors.push(
      `${where}: detail が事実を述べていません（「Wikipediaに記述が確認された」型）。\n` +
      `      何が・いつ・どうだったのかを書いてください。出典に何かが書いてあるという記述は\n` +
      `      evidence になりません。`
    );
  }
}

// 同一 detail が複数の議員に使い回されていないか
{
  const seen = new Map();
  for (const e of EVIDENCE) {
    const key = (e.detail || '').trim();
    if (key.length < 40) continue;
    if (!seen.has(key)) seen.set(key, []);
    seen.get(key).push(e);
  }
  for (const [key, list] of seen) {
    const pids = new Set(list.map((e) => e.pid));
    if (pids.size < 2) {
      // 同一議員に同一 detail が複数ある＝取り込み時の二重登録。
      if (list.length > 1) {
        errors.push(
          `${list[0].pid}: 同一の detail を持つ evidence が ${list.length}件 重複しています` +
          `（${list.map((e) => e.id).join(', ')}）。1件に統合してください。`
        );
      }
      continue;
    }
    // 同一の公的事実を同一文言で記述するのは正当（例: 同じ処分の説明）。
    // URLを伴うものは許容し、裏取りの無い使い回しのみを弾く。
    if (list.every((e) => has(e.url))) continue;
    errors.push(
      `${[...pids].join(', ')}: 同一の detail が ${pids.size}人に使い回されています（${list.map((e) => e.id).join(', ')}）。\n` +
      `      「${key.slice(0, 50)}…」\n` +
      `      テンプレート量産の疑いがあります。各議員に固有の事実を、出典URLとともに記述してください。`
    );
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
