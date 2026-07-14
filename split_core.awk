# data.js -> data_core.js  (一覧ページ用の軽量版を切り出す)
#
# 用途: politicians.html（一覧ページ）は軽量フィールドしか使わないため、
#       現行 data.js から重量フィールドを除いた data_core.js を生成する。
#       ※ data.js は再生成せず、読み取り専用で変換するだけ。
#
# 変換内容:
#   - POLITICIANS: plus/minus/comment/links を除去（複数行形式・1行形式の両対応）
#   - EVIDENCE 配列: 本体を除去し const EVIDENCE_COUNT = N; に置換
#   - DATA_UPDATED_AT / CHANGELOG / 軽量フィールドはそのまま保持
#
# 実行: awk -f split_core.awk data.js > data_core.js

# EVIDENCE 配列の開始
/^const EVIDENCE = \[$/ { inEv = 1; next }
inEv {
  if ($0 ~ /^\];$/) { inEv = 0; print "const EVIDENCE_COUNT = " evc ";"; next }
  if ($0 ~ /^  \{/) evc++
  next
}

# 複数行形式の議員データ: 重量フィールド行を丸ごと削除
/^    plus:/    { next }
/^    comment:/ { next }
/^    links:/   { next }

# 1行形式の議員データ: 行内の重量フィールドを除去
/^  \{id:"P/ {
  gsub(/plus:"([^"\\]|\\.)*",minus:"([^"\\]|\\.)*",/, "")
  gsub(/comment:"([^"\\]|\\.)*",/, "")
  gsub(/links:\{[^}]*\},/, "")
}

{ print }
