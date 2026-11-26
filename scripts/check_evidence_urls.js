#!/usr/bin/env node
//
// evidence の出典URLが今も開けるかを確認し、結果を evidence_url_status.js に記録する。
//
// 背景:
//   TORAN の evidence は「出典URLを読者が開いて確認できる」ことを前提にしている。
//   しかし官公庁のページは改組・年度切り替え・サイトリニューアルで頻繁に消える。
//   URLが死んだとき、ただリンク切れになるだけだと「最初から存在しなかった出典」と
//   「当時は実在したが後に消えた出典」の区別が付かない。2026年9月の全件検証で
//   削除した102件は前者だったが、今後は後者が必ず出てくる。
//
//   そこで「いつ到達できたか」を記録に残す。リンクが死んだあとも
//   「2026-09-22 時点では閲覧可能だった」と読者に示せるようにするための仕組み。
//
// 使い方:
//   node scripts/check_evidence_urls.js              # 全URLを確認して記録を更新
//   node scripts/check_evidence_urls.js --limit 20   # 先頭20件だけ（動作確認用）
//   node scripts/check_evidence_urls.js --dry-run    # ファイルを書き換えない
//   node scripts/check_evidence_urls.js --self-test  # ローカルサーバで判定ロジックを検証
//
// 終了コード:
//   0 = 新たに「リンク切れ」と判定されたURLなし
//   1 = 新たに「リンク切れ」と判定されたURLあり（CIはIssueを立てる）

'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const STATUS_FILE = path.join(ROOT, 'evidence_url_status.js');

// 1回の実行で失敗しただけでは「リンク切れ」と断定しない。
// 一時的な障害・メンテナンスと恒久的な消滅を区別するため、
// 連続 DEAD_AFTER 回「404/410」を返して初めて dead にする。
//
// ⚠️ dead にするのは 404/410 が続いたときだけ。403（Bot遮断）や 429（レート制限）、
// 5xx、通信エラーは何回続いても dead にしない。経産省・農水省の会見概要ページは
// 素の fetch に 403 を返すが、ブラウザでは普通に開ける。これを「リンク切れ」と
// 表示したら読者に嘘をつくことになる。到達を確認できないだけなので unverified とし、
// サイト上はリンクをそのまま出す。
const DEAD_AFTER = 2;
const TIMEOUT_MS = 20000;
const CONCURRENCY = 6;
const RETRY_DELAY_MS = 3000;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const today = () => new Date().toISOString().slice(0, 10);

// ---------------------------------------------------------------------------
// 判定ロジック
// ---------------------------------------------------------------------------

/**
 * HTTPレスポンス（または通信エラー）を3状態に分類する。
 *   ok      … 到達できた
 *   gone    … サーバが「無い」と答えた（404/410）。恒久的な消滅の可能性が高い
 *   error   … 到達できなかったが、無いとは限らない（タイムアウト・5xx・429 等）
 */
function classify(result) {
  if (result.networkError) return 'error';
  const s = result.status;
  if (s >= 200 && s < 400) return 'ok';
  if (s === 404 || s === 410) return 'gone';
  // 403 は Bot 遮断のことが多く、ページ自体は生きている場合がある。
  // 429 はレート制限。いずれも「消えた」とは扱わない。
  return 'error';
}

/**
 * 前回までの記録と今回の結果をマージする。
 * first_ok は一度記録したら上書きしない（「いつから確認できていたか」の証跡）。
 */
function mergeStatus(prev, outcome, date) {
  const base = prev || {};
  const next = {
    url: outcome.url,
    first_ok: base.first_ok || null,
    last_ok: base.last_ok || null,
    last_checked: date,
    last_status: outcome.status === null ? (outcome.reason || 'network_error') : outcome.status,
    fail_streak: base.fail_streak || 0,
    gone_streak: base.gone_streak || 0,
    state: base.state || 'unchecked',
  };

  if (outcome.verdict === 'ok') {
    next.first_ok = base.first_ok || date;
    next.last_ok = date;
    next.fail_streak = 0;
    next.gone_streak = 0;
    next.state = 'ok';
    return next;
  }

  next.fail_streak = (base.fail_streak || 0) + 1;

  if (outcome.verdict === 'gone') {
    // サーバが「無い」と答えた。これだけが消滅の証拠になる
    next.gone_streak = (base.gone_streak || 0) + 1;
    next.state = next.gone_streak >= DEAD_AFTER ? 'dead' : 'suspect';
    return next;
  }

  // 到達できなかったが、無いとは限らない（403 / 429 / 5xx / 通信エラー）。
  // 何回続いても dead にはしない
  next.gone_streak = 0;
  next.state = 'unverified';
  return next;
}

/** URLが変わったら履歴はリセットする（別の出典を指しているため） */
function resetIfUrlChanged(prev, url) {
  if (prev && prev.url !== url) return null;
  return prev;
}

// ---------------------------------------------------------------------------
// 取得
// ---------------------------------------------------------------------------

async function fetchOnce(url, method) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method,
      redirect: 'follow',
      signal: ctl.signal,
      headers: {
        // 素の fetch だと弾く官公庁サイトがあるため、一般的なUAを名乗る
        'User-Agent':
          'Mozilla/5.0 (compatible; TORAN-link-checker/1.0; +https://dashiyo777-oss.github.io/)',
        'Accept': 'text/html,application/xhtml+xml,application/pdf,*/*',
      },
    });
    return { status: res.status, networkError: false };
  } catch (e) {
    return { status: null, networkError: true, reason: e.name === 'AbortError' ? 'timeout' : 'network' };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 1つのURLを確認する。
 * HEAD を拒否するサーバが多いため、HEAD が ok 以外なら GET で確かめ直す。
 * 一度失敗したら少し待って1回だけ再試行する（瞬間的な失敗を拾わないため）。
 */
async function checkUrl(url, fetchImpl = fetchOnce) {
  let r = await fetchImpl(url, 'HEAD');
  if (classify(r) !== 'ok') {
    r = await fetchImpl(url, 'GET');
  }
  if (classify(r) !== 'ok') {
    await sleep(RETRY_DELAY_MS);
    r = await fetchImpl(url, 'GET');
  }
  return { url, status: r.status, reason: r.reason, verdict: classify(r) };
}

/**
 * URLの本文をテキストに落として返す。
 *
 * 出典が「実在する」ことと「その記述を裏付けている」ことは別である。
 * 到達確認だけでは前者しか分からないため、本文を読んで後者を確かめる手段を
 * 用意する。執筆環境から直接開けない相手先でも、Actions の runner からは
 * 読めることがある。
 */
async function dumpUrl(url, maxChars = 4000) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method: 'GET',
      redirect: 'follow',
      signal: ctl.signal,
      headers: {
        'User-Agent':
          'Mozilla/5.0 (compatible; TORAN-link-checker/1.0; +https://dashiyo777-oss.github.io/)',
        'Accept': 'text/html,application/xhtml+xml,*/*',
      },
    });
    const type = res.headers.get('content-type') || '';
    if (!res.ok) return { url, status: res.status, text: null };
    if (!/text|xml|json/.test(type)) {
      return { url, status: res.status, text: null, note: `本文がテキストではありません（${type}）` };
    }
    const html = await res.text();
    return { url, status: res.status, text: htmlToText(html).slice(0, maxChars) };
  } catch (e) {
    return { url, status: null, text: null, note: e.name === 'AbortError' ? 'timeout' : 'network' };
  } finally {
    clearTimeout(timer);
  }
}

/** HTMLからタグとスクリプトを落として読める形にする（厳密な変換は目的としない） */
function htmlToText(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|li|tr|h[1-6]|dt|dd|table)>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/[ \t\u3000]+/g, ' ')
    .replace(/\n\s*\n\s*\n+/g, '\n\n')
    .split('\n')
    .map((l) => l.trim())
    .join('\n')
    .trim();
}

// ---------------------------------------------------------------------------
// 入出力
// ---------------------------------------------------------------------------

function loadEvidence() {
  const src = fs.readFileSync(path.join(ROOT, 'data.js'), 'utf8');
  return vm.runInNewContext(src + ';EVIDENCE', {});
}

function loadStatus() {
  if (!fs.existsSync(STATUS_FILE)) return {};
  const src = fs.readFileSync(STATUS_FILE, 'utf8');
  try {
    return vm.runInNewContext(src + ';EVIDENCE_URL_STATUS', {}) || {};
  } catch {
    return {};
  }
}

function writeStatus(status, summary) {
  const entries = Object.keys(status)
    .sort()
    .map((id) => `  ${JSON.stringify(id)}: ${JSON.stringify(status[id])},`)
    .join('\n');

  const body = `// 統覧 TORAN — evidence 出典URLの生存記録
// 自動生成ファイル。直接編集しないでください。
// scripts/check_evidence_urls.js が更新します。
//
// last_ok は「そのURLに最後に到達できた日」。リンクが後に消えても、
// 読者に「いつの時点では閲覧できたか」を示すために残しています。
//
// 最終確認: ${summary.date} / 対象 ${summary.total}件
// 到達 ${summary.ok}件 / リンク切れ ${summary.dead}件 / 消滅の疑い ${summary.suspect}件
// 確認できず ${summary.unverified}件（403・429・通信エラー等。ページは生きている可能性が高い）

const EVIDENCE_URL_STATUS = {
${entries}
};
`;
  fs.writeFileSync(STATUS_FILE, body);
}

// ---------------------------------------------------------------------------
// セルフテスト（ネットワークに出られない環境でも判定ロジックを検証する）
// ---------------------------------------------------------------------------

async function selfTest() {
  const http = require('http');
  const os = require('os');
  let failures = 0;
  const check = (name, actual, expected) => {
    const a = JSON.stringify(actual);
    const e = JSON.stringify(expected);
    if (a === e) {
      console.log(`  ✅ ${name}`);
    } else {
      console.error(`  ❌ ${name}\n      期待: ${e}\n      実際: ${a}`);
      failures++;
    }
  };

  // --- 判定ロジック
  console.log('判定:');
  check('200 は ok', classify({ status: 200 }), 'ok');
  check('301 は ok（リダイレクト追跡後）', classify({ status: 301 }), 'ok');
  check('404 は gone', classify({ status: 404 }), 'gone');
  check('410 は gone', classify({ status: 410 }), 'gone');
  check('403 は error（Bot遮断の可能性があり消滅とは断定しない）', classify({ status: 403 }), 'error');
  check('429 は error', classify({ status: 429 }), 'error');
  check('500 は error', classify({ status: 500 }), 'error');
  check('通信失敗は error', classify({ networkError: true }), 'error');

  // --- 履歴マージ
  console.log('履歴:');
  const d1 = '2026-01-01';
  const d2 = '2026-02-01';
  const d3 = '2026-03-01';
  const okOutcome = (url) => ({ url, status: 200, verdict: 'ok' });
  const goneOutcome = (url) => ({ url, status: 404, verdict: 'gone' });

  const s1 = mergeStatus(null, okOutcome('https://a.example/x'), d1);
  check('初回到達で first_ok が入る', [s1.first_ok, s1.last_ok, s1.state], [d1, d1, 'ok']);

  const s2 = mergeStatus(s1, goneOutcome('https://a.example/x'), d2);
  check('1回失敗では dead にしない', [s2.state, s2.fail_streak, s2.last_ok], ['suspect', 1, d1]);

  const s3 = mergeStatus(s2, goneOutcome('https://a.example/x'), d3);
  check('404が2回続いて dead', [s3.state, s3.gone_streak], ['dead', 2]);
  check('dead になっても first_ok / last_ok は残る', [s3.first_ok, s3.last_ok], [d1, d1]);

  // 403 / 429 / 通信エラーは何回続いても dead にしない。
  // 経産省・農水省の会見ページは素の fetch に 403 を返すが実際には生きている
  const errOutcome = (url, status) => ({ url, status, verdict: 'error' });
  const e1 = mergeStatus(s1, errOutcome('https://a.example/x', 403), d2);
  check('403 は1回目から unverified', [e1.state, e1.gone_streak], ['unverified', 0]);
  const e2 = mergeStatus(e1, errOutcome('https://a.example/x', 403), d3);
  check('403 が続いても dead にしない', [e2.state, e2.gone_streak], ['unverified', 0]);
  const e3 = mergeStatus(e2, errOutcome('https://a.example/x', 429), '2026-04-01');
  check('429 も同様', e3.state, 'unverified');
  check('unverified でも last_ok は保たれる', e3.last_ok, d1);
  const e4 = mergeStatus(e2, goneOutcome('https://a.example/x'), '2026-04-01');
  check('403続きのあと404が1回では suspect 止まり', [e4.state, e4.gone_streak], ['suspect', 1]);
  const e5 = mergeStatus(e4, goneOutcome('https://a.example/x'), '2026-05-01');
  check('404が2回続けば dead', [e5.state, e5.gone_streak], ['dead', 2]);

  const s4 = mergeStatus(s3, okOutcome('https://a.example/x'), '2026-04-01');
  check('復活したら ok に戻り streak がリセットされる', [s4.state, s4.fail_streak, s4.last_ok], ['ok', 0, '2026-04-01']);
  check('復活しても first_ok は最初の日のまま', s4.first_ok, d1);

  check('URLが差し替わったら履歴をリセット', resetIfUrlChanged(s4, 'https://b.example/y'), null);
  check('URLが同じなら履歴を引き継ぐ', resetIfUrlChanged(s4, 'https://a.example/x') === s4, true);

  // --- 本文の読み出し
  console.log('本文:');
  check(
    'タグを落として読める形にする',
    htmlToText('<h1>略歴</h1><p>平成9年4月\u3000科学技術庁</p><script>var x=1;</script>'),
    '略歴\n平成9年4月 科学技術庁'
  );
  check('実体参照を戻す', htmlToText('<p>A&amp;B&nbsp;C</p>'), 'A&B C');

  // --- Actions への受け渡し（終了コードに頼らない通知経路）
  console.log('outputs:');
  const sumFixture = { dead: 2, unverified: 3 };
  const deadFixture = [
    { id: 'E0001', pid: 'P001', src: '某省', url: 'https://a.example/x', last_ok: '2026-01-01', last_status: 404 },
    { id: 'E0002', pid: 'P002', src: '某県', url: 'https://b.example/y', last_ok: null, last_status: 404 },
  ];
  const out = buildOutputs(sumFixture, deadFixture, []);
  check('dead 件数を文字列で渡す', out.dead, '2');
  check('newly_dead が0でも dead は立つ', [out.dead, out.newly_dead], ['2', '0']);
  check('report に両方のIDが入る', /E0001[\s\S]*E0002/.test(out.report), true);
  check('last_ok がないものは「確認記録なし」と書く', /到達の確認記録なし/.test(out.report), true);

  const outFile = path.join(os.tmpdir(), `toran-out-${process.pid}.txt`);
  try { fs.unlinkSync(outFile); } catch {}
  check('GITHUB_OUTPUT がなければ書かない', appendOutputs(out, undefined), false);
  check('GITHUB_OUTPUT があれば書く', appendOutputs(out, outFile), true);
  const written = fs.readFileSync(outFile, 'utf8');
  check('複数行の値はヒアドキュメント形式', /report<<__TORAN_REPORT__\n/.test(written), true);
  check('書き出した内容に件数が含まれる', /dead<<__TORAN_DEAD__\n2\n/.test(written), true);
  fs.unlinkSync(outFile);

  // --- 実際のHTTPに対する挙動（ローカルサーバ）
  console.log('HTTP:');
  const server = http.createServer((req, res) => {
    if (req.url === '/ok') { res.writeHead(200); res.end('ok'); return; }
    if (req.url === '/notfound') { res.writeHead(404); res.end('nf'); return; }
    if (req.url === '/redirect') { res.writeHead(302, { Location: '/ok' }); res.end(); return; }
    if (req.url === '/head-blocked') {
      // HEAD は拒否するが GET なら返すサーバ（官公庁サイトによくある）
      if (req.method === 'HEAD') { res.writeHead(405); res.end(); return; }
      res.writeHead(200); res.end('ok');
      return;
    }
    res.writeHead(500); res.end('err');
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}`;

  const r1 = await checkUrl(`${base}/ok`);
  check('到達できるURLは ok', r1.verdict, 'ok');

  const r2 = await checkUrl(`${base}/redirect`);
  check('リダイレクトを追って ok', r2.verdict, 'ok');

  const r3 = await checkUrl(`${base}/head-blocked`);
  check('HEADを拒否してもGETで ok と判定', r3.verdict, 'ok');

  const r4 = await checkUrl(`${base}/notfound`);
  check('404 は gone', [r4.verdict, r4.status], ['gone', 404]);

  await new Promise((r) => server.close(r));

  console.log('');
  if (failures) {
    console.error(`❌ セルフテスト失敗（${failures}件）`);
    process.exit(1);
  }
  console.log('✅ セルフテスト成功');
}

// ---------------------------------------------------------------------------
// GitHub Actions への受け渡し
//
// 以前はスクリプトの終了コード（新たなリンク切れがあれば 1）だけを合図にして
// いたが、ワークフロー側が `node ... | tee` で受けていたため、パイプの終了
// コードは tee のもの（常に 0）になり、Issue を作る手順が一度も動かなかった。
// 検知できていても通知が出なければ、検知していないのと同じである。
// そこで終了コードに頼らず、件数を outputs として明示的に渡す。
// ---------------------------------------------------------------------------

function buildOutputs(summary, deadEntries, newlyDead) {
  const lines = [];
  for (const d of deadEntries) {
    const seen = d.last_ok ? `${d.last_ok} まで到達を確認` : '到達の確認記録なし';
    lines.push(`- ${d.id}（${d.pid}）${d.src}`);
    lines.push(`    ${d.url}`);
    lines.push(`    ${seen} / HTTP ${d.last_status ?? '-'}`);
  }
  return {
    dead: String(summary.dead),
    newly_dead: String(newlyDead.length),
    unverified: String(summary.unverified),
    report: lines.join('\n'),
  };
}

function appendOutputs(outputs, file) {
  if (!file) return false;
  let body = '';
  for (const [key, value] of Object.entries(outputs)) {
    // 複数行の値はヒアドキュメント形式で渡す必要がある
    const delim = `__TORAN_${key.toUpperCase()}__`;
    body += `${key}<<${delim}\n${value}\n${delim}\n`;
  }
  fs.appendFileSync(file, body, 'utf8');
  return true;
}

// ---------------------------------------------------------------------------
// 本体
// ---------------------------------------------------------------------------

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--self-test')) return selfTest();

  // 差し替え候補のURLが本当に開けるかを、データに入れる前に確かめるための単発確認
  const urlArg = args.indexOf('--check-url');
  if (urlArg >= 0) {
    const urls = args.slice(urlArg + 1).filter((a) => /^https?:\/\//.test(a));
    if (!urls.length) {
      console.error('--check-url のあとに http(s) で始まるURLを1つ以上指定してください');
      process.exit(2);
    }
    let ng = 0;
    for (const u of urls) {
      const r = await checkUrl(u);
      const mark = r.verdict === 'ok' ? '✅' : r.verdict === 'gone' ? '❌' : '⚠️';
      console.log(`${mark} ${r.verdict.padEnd(6)} HTTP ${String(r.status ?? r.reason).padEnd(8)} ${u}`);
      if (r.verdict !== 'ok') ng++;
    }
    process.exit(ng ? 1 : 0);
  }

  // 出典が記述を裏付けているかを確かめるため、本文を読み出す
  const dumpArg = args.indexOf('--dump-url');
  if (dumpArg >= 0) {
    const urls = args.slice(dumpArg + 1).filter((a) => /^https?:\/\//.test(a));
    if (!urls.length) {
      console.error('--dump-url のあとに http(s) で始まるURLを1つ以上指定してください');
      process.exit(2);
    }
    let ng = 0;
    for (const u of urls) {
      const r = await dumpUrl(u);
      console.log('='.repeat(70));
      console.log(`URL   : ${r.url}`);
      console.log(`HTTP  : ${r.status ?? r.note ?? '-'}`);
      console.log('='.repeat(70));
      if (r.text) {
        console.log(r.text);
      } else {
        console.log(`(本文を取得できませんでした: ${r.note ?? r.status})`);
        ng++;
      }
      console.log('');
    }
    process.exit(ng ? 1 : 0);
  }

  const dryRun = args.includes('--dry-run');
  const limitArg = args.indexOf('--limit');
  const limit = limitArg >= 0 ? parseInt(args[limitArg + 1], 10) : Infinity;

  const EVIDENCE = loadEvidence();
  const prevStatus = loadStatus();
  const date = today();

  const targets = EVIDENCE
    .filter((e) => typeof e.url === 'string' && /^https?:\/\//.test(e.url))
    .slice(0, limit);

  console.log(`evidence ${EVIDENCE.length}件中、URLを持つ ${targets.length}件を確認します`);
  if (dryRun) console.log('(--dry-run: ファイルは書き換えません)');

  const status = {};
  const newlyDead = [];
  let done = 0;

  // 相手先に負担をかけないよう同時実行数を絞る
  const queue = [...targets];
  const workers = Array.from({ length: Math.min(CONCURRENCY, queue.length) }, async () => {
    while (queue.length) {
      const e = queue.shift();
      const outcome = await checkUrl(e.url);
      const prev = resetIfUrlChanged(prevStatus[e.id], e.url);
      const merged = mergeStatus(prev, outcome, date);
      status[e.id] = merged;

      if (merged.state === 'dead' && (!prev || prev.state !== 'dead')) {
        newlyDead.push({ id: e.id, pid: e.pid, url: e.url, src: e.src, last_ok: merged.last_ok });
      }
      done++;
      if (done % 25 === 0) console.log(`  ${done}/${targets.length} …`);
    }
  });
  await Promise.all(workers);

  const summary = {
    date,
    total: Object.keys(status).length,
    ok: Object.values(status).filter((s) => s.state === 'ok').length,
    suspect: Object.values(status).filter((s) => s.state === 'suspect').length,
    dead: Object.values(status).filter((s) => s.state === 'dead').length,
    unverified: Object.values(status).filter((s) => s.state === 'unverified').length,
  };

  console.log('');
  console.log(
    `到達 ${summary.ok}件 / リンク切れ ${summary.dead}件 / 消滅の疑い ${summary.suspect}件 / ` +
    `確認できず ${summary.unverified}件（403・429・通信エラー等。ページは生きている可能性が高い）`
  );

  // dead のものは「今回あらたに」かどうかに関わらず全件を通知対象にする。
  // 一度しか報せない仕組みだと、その一度を取りこぼした時点で永久に黙る
  const deadEntries = targets
    .filter((e) => status[e.id] && status[e.id].state === 'dead')
    .map((e) => ({
      id: e.id,
      pid: e.pid,
      src: e.src,
      url: e.url,
      last_ok: status[e.id].last_ok,
      last_status: status[e.id].last_status,
    }));

  if (deadEntries.length) {
    console.log('');
    console.log(`⚠️ リンク切れと判定されているURL（${deadEntries.length}件）:`);
    for (const d of deadEntries) {
      const seen = d.last_ok ? `${d.last_ok} まで到達を確認` : '到達の確認記録なし';
      console.log(`  - ${d.id}（${d.pid}）${d.src}`);
      console.log(`      ${d.url}`);
      console.log(`      ${seen} / HTTP ${d.last_status ?? '-'}`);
    }
  }

  if (appendOutputs(buildOutputs(summary, deadEntries, newlyDead), process.env.GITHUB_OUTPUT)) {
    console.log('');
    console.log('GitHub Actions の outputs に件数を渡しました');
  }

  if (newlyDead.length) {
    console.log('');
    console.log(`⚠️ 今回あらたにリンク切れと判定されたURL（${newlyDead.length}件）:`);
    for (const d of newlyDead) {
      const seen = d.last_ok ? `${d.last_ok} まで到達を確認` : '一度も到達を確認できていない';
      console.log(`  - ${d.id}（${d.pid}）${d.src}`);
      console.log(`      ${d.url}`);
      console.log(`      ${seen}`);
    }
  }

  if (!dryRun) {
    writeStatus(status, summary);
    console.log('');
    console.log(`evidence_url_status.js を更新しました（${summary.total}件）`);
  }

  process.exit(newlyDead.length ? 1 : 0);
}

if (require.main === module) {
  main().catch((e) => {
    console.error(e);
    process.exit(2);
  });
}

module.exports = { classify, mergeStatus, resetIfUrlChanged, checkUrl };
