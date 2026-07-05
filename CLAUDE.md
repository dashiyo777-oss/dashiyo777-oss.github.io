# 統覧 TORAN — プロジェクトナレッジ

## 概要

国会議員（衆参計822名）を8軸で独自評価するデータベースサイト。
GitHub Pages でホスティング。データは `data.js` に格納。

- URL: `https://dashiyo777-oss.github.io/politicians.html`
- 評価済: 794名（2026.06時点） / Wikipedia基礎評価: 0名 / 情報不足: 0名

---

## ファイル構成

| ファイル | 役割 |
|---------|------|
| `data.js` | 全政治家データ（POLITICIANS配列）約1.5MB |
| `politicians.html` | ランキング一覧ページ |
| `politician.html` | 議員個別カルテページ |
| `parties.html` | 政党別評価比較ページ |
| `history_ranking.html` | 歴史ランキング |
| `scripts/validate_data.py` | data.js整合性チェックスクリプト |
| `.github/workflows/validate-data.yml` | CI（PR時自動検証） |
| `generate_wikipedia_batches.py` | Wikipedia情報から一括評価生成 |
| `generate_js_data.py` | data.js生成ツール |
| `apply.py` | バッチ評価結果をdata.jsに適用 |

---

## data.js エントリ構造

```javascript
{
    id:"P001", name:"氏名", reading:"よみがな", party:"政党", role:"衆議院議員",
    chamber:"衆議院",  // または "参議院"
    district:"選挙区", status:"現職", gender:"男",  // または "女"
    age:null,
    total:63, rank:"C",
    axes:[3,3,3,3,3,3,3,3],  // 8軸 各0〜5
    stances:{tax_cut:"◎", active_fiscal:"○", ...},
    plus:"強み記述", minus:"弱み記述",
    comment:"総合コメント",
    links:{tw:"", hp:"", wiki:"", yt:""},
    flag_crime:false, flag_caution:false,
    updated:"2026.06", survey:"評価済"
}
```

### survey の種類
- `"評価済"` — 本格評価済み（794名）
- `"Wikipedia基礎評価"` — Wikipedia情報のみで仮評価（0名）
- `"情報不足"` — 評価不可（0名）

---

## スコア計算式（必須）

```python
# 8軸の合計から total を計算
axes_sum = sum(axes)  # 0〜40
total = int(axes_sum * 100 / 40)  # 0〜100

# ランク判定（generate_wikipedia_batches.py の calc_rank）
def calc_rank(total):
    if total >= 90: return "S"
    if total >= 87: return "A+"
    if total >= 83: return "A"
    if total >= 80: return "A-"
    if total >= 77: return "B+"
    if total >= 73: return "B"
    if total >= 70: return "B-"
    if total >= 67: return "C+"
    if total >= 63: return "C"
    if total >= 60: return "C-"
    return "D"
```

### 有効な total 値（axes合計→total の対応例）
- sum=25 → total=62（C-）
- sum=26 → total=65（C）
- sum=27 → total=67（C+）
- sum=28 → total=70（B-）
- sum=29 → total=72（B-）
- sum=30 → total=75（B）
- sum=32 → total=80（A-）
- sum=34 → total=85（A）
- sum=35 → total=87（A+）
- sum=36 → total=90（S）

**重要**: total=76、71等は数学的に不可能な値。CI で検出される。

---

## CI 整合性チェック

PRマージ前に自動実行（`.github/workflows/validate-data.yml`）:

1. **ファイルサイズ** — 500KB 以上
2. **JavaScript 構文** — `node --check data.js`
3. **ヘッダーコメント** — "統覧 TORAN" を含む
4. **政治家数** — 800件以上
5. **total/rank 整合性** — `scripts/validate_data.py` で検証

ローカル確認コマンド:
```bash
node --check data.js && python3 scripts/validate_data.py
```

---

## data.js 手動更新手順

### 1. エントリを探して置換（Python）

```python
import re

data = open('data.js', encoding='utf-8').read()
pid = "P001"

# ブレース深度マッチングでエントリを取得
start = data.find(f'id:"{pid}"')
ob = data.rfind('{', 0, start)
depth = 1; i = ob + 1
while i < len(data) and depth > 0:
    if data[i] == '{': depth += 1
    elif data[i] == '}': depth -= 1
    i += 1
old_entry = data[ob:i]

# 新エントリで置換
new_entry = '{ id:"P001", ... }'
data = data.replace(old_entry, new_entry, 1)
open('data.js', 'w', encoding='utf-8').write(data)
```

### 2. 複数エントリを更新する場合
**逆順処理**が必須（文字列オフセットがずれないため）:
```python
matches = list(pattern.finditer(data))
matches.reverse()
for m in matches:
    # 後ろから順に置換
```

---

## 政党別スタンス定義（主要政党）

stances の各キーの意味:

| キー | 内容 |
|------|------|
| tax_cut | 減税・基礎控除拡大 |
| active_fiscal | 積極財政 |
| discipline | 財政規律 |
| defense | 防衛力強化 |
| econ_sec | 経済安全保障 |
| immigration | 外国人受け入れ |
| renewable | 再生可能エネルギー |
| nuclear | 原子力発電 |
| expo | 万博・大型イベント |
| ir | IR・カジノ |
| mynumber | マイナンバー推進 |
| birthrate | 少子化対策 |
| education | 教育投資 |
| regional | 地方創生 |
| china | 対中強硬路線 |
| foreign | 外交積極推進 |
| food | 食料安全保障 |
| semi | 半導体・先端産業 |

記号: `◎`=強く支持、`○`=支持、`△`=中立、`×`=反対

---

## 主要政党メモ

### 減税日本・ゆうこく連合
- **代表**: 河村たかし（P135、衆議院議員・愛知1区）
- **共同代表**: 原口一博
- 主なスタンス: 大幅減税（◎）、積極財政（◎）、マイナンバー反対（×）、外国人受け入れ慎重
- 2025年参院選後に結成された新政治グループ

---

## 国会会議録API（NDL）利用ノウハウ

### 検索動作の特性

- **NDL APIは読み仮名マッチを行う**: `speaker=漆間譲司`（漢字）で検索しても、NDLに「うるま譲司」（ひらがな）で登録されている議員のレコードがヒットする。漢字とひらがなの表記ゆれはAPIが自動吸収するため、件数比較では同一の結果が返る。
- **登録名の確認方法**: `maximumRecords=5` 程度で実データを取得し、以下フィールドで本人確認を行う:
  - `speaker` — NDLに実際に登録されている発言者名（この名前でALIASESを定義する）
  - `speakerYomi` — 読み仮名（別人との区別に有効）
  - `speakerGroup` — 所属会派（政党と一致しているか確認）
  - `nameOfHouse` — 院名（衆議院/参議院）
- **数値の異常検知**: 件数が過大・過小に見えても、`speakerGroup`・`nameOfHouse`・`nameOfMeeting` の整合性を確認してから判断する。属性が本人と一致していれば数値は正当と見なせる。

### ALIASES定義のルール（fix_speech_aliases.py・fetch_question_counts.py）

- NDL APIの `speaker` 登録名（上記確認手順で取得した値）を ALIASES に設定する
- data.js の `name` フィールドとNDL登録名が異なる場合（例: data.jsは漢字、NDLはひらがな）は両スクリプトの ALIASES を同期させること

---

## ⚠️ AI評価時の頻出誤りパターン（必読）

### 経歴・出身の混同（最多発）

| 間違いやすい表現 | 正しい区別 |
|---------------|-----------|
| 「○○省出身」「○○省官僚出身」 | 官僚（キャリア公務員）として省庁に入省した場合のみ使用 |
| 「経産省出身」 | 経産大臣・政務官・副大臣は**政治任命職**。省出身ではない |
| 「元○○官僚」 | 民間企業・国際機関出身者を官僚と混同しない |

**実例（過去の誤記）：**
- 田嶋要（P244）：経済産業大臣**政務官**（政治任命）→ 誤って「経産省出身官僚」と記述
- 遠藤敬（P081）：他人（木村弥生・前江東区長）の有罪判決を誤帰属

### チェックルール
- `plus` / `comment` に「○○省出身」「○○官僚」を書く場合 → Wikipedia・公式サイトで**入省経歴を必ず確認**
- 「大臣」「副大臣」「政務官」は省出身の証拠にならない
- NTT・商社・銀行・国際機関出身者は官僚ではない

### データ不整合の修正ルール（2026.07.05追記）

**一括推定修正の禁止**:
- AI推定によるパターン一致での一括修正は行わない
- AI生成データをAI推定で上書きすると誤りが検出不能になる（2026.07: role/chamber 15件誤記はこの構造で発生）
- 修正は必ず**1件ずつ**、衆参公式名簿等の一次情報で検証してから行う

**一次情報の優先順位**:
1. 参議院公式（sangiin.go.jp）/ 衆議院公式（shugiin.go.jp）の議員名簿
2. 各議員の政党公式ページ
3. Wikipedia（二次情報、補完用）

**自動検知**: `scripts/validate_chamber.py` を月次 GitHub Actions（`.github/workflows/validate-chamber.yml`）で実行し、衆参名簿との乖離を検出する。

---

## よくある作業

### 新規評価追加（Excelデータ受け取り時）

1. Excelをアップロード → Python でパース
2. 8軸スコアを設定（各0〜5）
3. `total = int(sum(axes) * 100 / 40)` を計算
4. `rank = calc_rank(total)` を設定
5. plus / minus / comment を記述
6. stances を政党傾向に合わせて設定
7. `scripts/validate_data.py` で整合性確認
8. コミット・プッシュ → PR → CI pass → マージ

### 不整合を一括修正する場合

```bash
python3 /tmp/fix_data.py  # 過去に使用したスクリプト（/tmp に保存）
python3 scripts/validate_data.py  # 確認
```

### データ更新日の表示

`politicians.html` の JS が POLITICIANS 配列の `updated` フィールド最大値を自動取得して表示。
エントリの `updated:"2026.06"` を更新するだけで反映される。

---

## ⚠️ changelog.js 必須更新ルール

**data.js を変更したら、必ず同じ PR で `changelog.js` も更新すること。**
CI がこれを自動検出して失敗させる（data.js 変更時に changelog.js 未更新は ❌ でブロック）。

### changelog.js の書き方

```javascript
// changelog.js の先頭に追記（新しいものを上に）
const SITE_CHANGELOG = [
  {
    date: "2026.06.14",          // 更新日（YYYY.MM.DD）
    label: "変更の種類を一言で",   // 例: "評価追加", "バグ修正", "機能追加"
    entries: [
      "変更内容を箇条書きで（何件追加・何を修正など）",
      "複数行OK",
    ]
  },
  // ... 既存のエントリ
];
```

### 更新例

| 作業内容 | changelog に書くこと |
|---------|-------------------|
| 評価済み人数が増えた | "評価済みXX名に到達" |
| 特定議員のデータ修正 | "XX（氏名）の◯◯を修正" |
| 情報不足→Wikipedia基礎評価 | "情報不足X件にWikipedia基礎評価を適用" |
| スタンス・コメント更新 | "XX名のスタンス・コメントを更新" |

---

## Git 運用

- 開発ブランチ: `claude/amazing-volta-Ii6eP`
- マージ方法: squash merge
- stop-hook エラー時:
  ```bash
  git config user.email "noreply@anthropic.com"
  git config user.name "Claude"
  git fetch origin main
  git rebase --exec "git commit --amend --no-edit --reset-author" origin/main
  ```

---

## 残タスク（2026.06.15時点）

### 機能系
- [ ] 更新告知自動化（GitHub Actions + X API 連携）

### 完了済み
- ✅ `Wikipedia基礎評価` 全91件の本格評価 → 0件（2026.06.14）
- ✅ `[ ]` 付き43件（参議院）の正式名称・政党確定（2026.06.14）
- ✅ `情報不足` 全件解消 → 0件（2026.06.14）
- ✅ Google Search Console 登録（2026.06.14）
- ✅ サイトマップ（sitemap.xml）作成（2026.06.14）
- ✅ 政党別レーダーチャート（院別・男女別比較）（2026.06.14）
- ✅ 議員カルテ：立法活動・採決記録リンク（2026.06.14）

---

## アクセス改善（実施済み）

- ✅ OGPタグ（politicians.html・politician.html）
- ✅ Xシェアボタン（議員カルテページ）
- ✅ title タグ動的最適化（議員名・ランク・点数を含む）
- ✅ 政党別比較ページ（parties.html）
- ✅ データ更新日表示
