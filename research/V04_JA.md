# PencilForecast v0.4 — 見出しあり／なしの比較（研究用）
v0.3と既存予測は変更しない。大会への投稿・定期実行・課金への切替は行わない。
## 手動操作
Actions → PencilForecast v0.4 - paired news research (manual)。
最初は discover（AI呼出なし）。対象は45日以内に解決予定で締切15分超の公開二択問題。取得した候補中で短期順。post_id=0は自動選択。
GDELT DOC APIで直近7日間の見出しを最大6件保存する。見出しのみで記事本文は読まない。検索語は簡易的な抽出で関連性や網羅性は保証されない。
pairedでは見出しが得られた場合に限り同じ固定無料モデルを最大2回呼ぶ。見出しなしとありの入力を比較する。無料枠不足・異常時は停止。有料モデルへの切替はしない。費用報告ゼロも確認する。GitHub Actionsと外部サービスの無料利用条件を守ること。
## 評価
両方の予測・時刻・見出し・ハッシュをpaired_record.jsonとして保存（Actions artifactは90日）。失敗・未完了は採点しない。結果は公式の確定値のみを使用する。結果ファイルの例: {"101":{"outcome":1,"resolved_at":"2026-12-01T00:00:00Z"}}。
python research/forecastlab_v04.py --mode score --records record1.json record2.json --outcomes outcomes.json
Brierスコアで見出しなし、あり、50%固定、ありの確率を50%方向に20%縮小した固定補正を比較する。重複・締切後の予測を拒否。補正値は未検証の仮説で、結果を見てから変更しない。精度改善の主張には十分な数の新規解決済み問題が必要。モデルの自動昇格なし。
実際の外部接続は手動のdiscover/pairedで別途検証する。v0.3の採点とは独立。
