"""
ALIASES 共通モジュール。

data.js の議員名と各データソース側の登録名の対応を一元管理する。
ソースごとに正式登録名が異なるため、ソースキー別に格納する。

  ndl:               NDL 国会会議録検索 API（fix_speech_aliases.py が使用）
  shugiin_shitsumon: 衆議院質問主意書（fetch_question_counts.py が使用）
  sangiin_vote:      参議院本会議投票記録（fetch_vote_records.py が使用）
  gian:              衆参議案 keika/meisai ページ（fetch_bill_counts.py が使用）

使い方:
  import sys, os
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  from common_aliases import get_aliases
  ALIASES = get_aliases("ndl")   # → dict[str, list[str]]
"""

# fmt: off
ALIASES: dict[str, dict[str, list[str]]] = {

    # ── 旧字体・表記ゆれ ─────────────────────────────────────────────────

    "P010": {
        # 眞澄美→真澄美（旧字体）。全ソース共通
        "ndl":               ["浅田真澄美"],
        "shugiin_shitsumon": ["浅田真澄美"],
        "sangiin_vote":      ["浅田真澄美"],
        "gian":              ["浅田真澄美"],
    },
    "P109": {
        # 嶋→島（旧字体）。全ソース共通
        "ndl":               ["鹿島祐介"],
        "shugiin_shitsumon": ["鹿島祐介"],
        "sangiin_vote":      ["鹿島祐介"],
        "gian":              ["鹿島祐介"],
    },
    "P121": {
        # 澤→沢（旧字体）。全ソース共通
        "ndl":               ["金沢結衣"],
        "shugiin_shitsumon": ["金沢結衣"],
        "sangiin_vote":      ["金沢結衣"],
        "gian":              ["金沢結衣"],
    },
    "P165": {
        # こうらい→高来/高麗（表記ゆれ）。全ソース共通
        "ndl":               ["高来啓一郎", "高麗啓一郎"],
        "shugiin_shitsumon": ["高来啓一郎", "高麗啓一郎"],
        "sangiin_vote":      ["高来啓一郎", "高麗啓一郎"],
        "gian":              ["高来啓一郎", "高麗啓一郎"],
    },
    "P284": {
        # 澤→沢（旧字体）。全ソース共通
        "ndl":               ["長沢興祐"],
        "shugiin_shitsumon": ["長沢興祐"],
        "sangiin_vote":      ["長沢興祐"],
        "gian":              ["長沢興祐"],
    },
    "P783": {
        # 齋→斎/齊（旧字体、兵庫県知事）
        # ※参議院議員ではないため sangiin_vote エントリなし
        "ndl":               ["斎藤元彦", "齊藤元彦"],
        "shugiin_shitsumon": ["斎藤元彦", "齊藤元彦"],
    },
    "P794": {
        # 濵→浜（旧字体）。全ソース共通
        "ndl":               ["浜田省司"],
        "shugiin_shitsumon": ["浜田省司"],
        "sangiin_vote":      ["浜田省司"],
        "gian":              ["浜田省司"],
    },

    # ── 通称名・ひらがな/カタカナ登録 ────────────────────────────────────

    "P073": {
        # data.js は通称「内山こう」。NDL・参議院投票は戸籍名「内山幸子」を使用
        "ndl":               ["内山幸子"],
        "shugiin_shitsumon": ["内山幸子"],
        "sangiin_vote":      ["内山幸子"],
        "gian":              ["内山幸子"],
    },
    "P509": {
        # 参議院投票記録では姓のみひらがな「いんどう周作」と表記される（犬童周作）
        "sangiin_vote":      ["いんどう周作"],
    },
    "P513": {
        # 参議院投票記録では名のみひらがな「上野ほたる」と表記される（上野蛍）
        "sangiin_vote":      ["上野ほたる"],
    },
    "P523": {
        # 参議院投票記録では名が「くみ子」と混じり表記「江原くみ子」（江原久美子）
        "sangiin_vote":      ["江原くみ子"],
    },
    "P569": {
        # 参議院投票記録では名のみひらがな「郡山りょう」と表記される（郡山玲）
        "sangiin_vote":      ["郡山りょう"],
    },
    "P076": {
        # data.js はひらがな「うるま譲司」
        # NDL 国会会議録: ひらがな登録のため「うるま譲司」で検索する必要がある
        # 衆議院質問主意書: 漢字表記「漆間譲司」で登録されている（意図的に異なる値）
        # 参議院投票記録: sangiin側の登録名が不明なため両方を試行する
        # 議案: 衆議院は漢字登録「漆間譲司」
        "ndl":               ["うるま譲司"],
        "shugiin_shitsumon": ["漆間譲司"],
        "sangiin_vote":      ["うるま譲司", "漆間譲司"],
        "gian":              ["漆間譲司"],
    },
    "P802": {
        # data.js は通称「玉城デニー」。NDL・参議院投票は戸籍名「玉城康裕」を使用
        "ndl":               ["玉城康裕"],
        "shugiin_shitsumon": ["玉城康裕"],
        "sangiin_vote":      ["玉城康裕"],
        "gian":              ["玉城康裕"],
    },
    "P815": {
        # data.js は漢字「大石晃子」。NDL・参議院側はひらがな「大石あきこ」登録
        "ndl":               ["大石あきこ"],
        "shugiin_shitsumon": ["大石あきこ"],
        "sangiin_vote":      ["大石あきこ"],
        "gian":              ["大石あきこ"],
    },
    "P817": {
        # data.js は漢字「佐藤紗央里」。NDL・参議院側はひらがな「さとうさおり」登録
        "ndl":               ["佐藤紗央里"],
        "shugiin_shitsumon": ["佐藤紗央里"],
        "sangiin_vote":      ["佐藤紗央里"],
        "gian":              ["佐藤紗央里"],
    },
}
# fmt: on


def get_aliases(source: str) -> dict[str, list[str]]:
    """
    指定ソース用の ALIASES 辞書を返す。

    Args:
        source: "ndl" | "shugiin_shitsumon" | "sangiin_vote" | "gian"

    Returns:
        {議員ID: [別名リスト]} の辞書（ソースにエントリが存在する議員のみ）
    """
    return {
        pid: entry[source]
        for pid, entry in ALIASES.items()
        if source in entry
    }
