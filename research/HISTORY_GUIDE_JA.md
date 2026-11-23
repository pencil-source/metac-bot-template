# PencilForecast v0.3 — 無料の予測履歴・採点

**用途：** GitHub Actionsに保存された未来予測を再収集し、Metaculus公式APIから参照できるYES/NO結果だけで採点する。外部での買い物、LLM呼び出し、Metaculusへの予測投稿は**一切行わない**。

## GitHub上での使用

1. **Actions → PencilForecast v0.3 - history score (read only)** を開く。
2. **Run workflow** をクリック（追加設定不要）。
3. Summary に「記録数・重複排除件数・検証可能な解決数・未解決数・Brierスコア」を表示する。
4. Artifacts の `pencil-forecast-history-audit` をダウンロードする。

保存されるファイル：

- `historical_forecasts.jsonl`：後から良い結果だけを拾うことがないよう、**同じ問題では最初の予測だけ**採用
- `visible_official_resolutions.csv`：Metaculus APIから確認できた公式YES/NO結果だけ
- `history_audit.md`：比較結果・制約
- `audit_status.json`：処理件数・参照失敗の数

## 判断に使ってよいもの・いけないもの

- Metaculus APIの`resolution`が`null`なら、**未確定/閲覧不可**として扱う。`NO`と判断しない。
- `Ambiguous`や`Annulled`は採点対象から除く。
- Metaculusが制限付きAPIアクセスを適用しているため、**予測を大会に投稿していない問題の解決結果は閲覧できない場合がある**。そういう場合は手動で検証した結果を `research/data/resolutions_TEMPLATE.csv` に記入し、v0.3の`score`を使用する。
- 初期の比較基準50%は弱いので、これに勝っただけでは賞金を得る能力の証明にはならない。
- GitHub Actionsの予測Artifactsは原則90日で期限切れ。期限前にバックアップが必要。履歴統合スクリプトを使っても永久保存にはならない。
- このスクリプトは**今から未来の結果が確定した時に**使うもの。実行を繰り返しても確定していない結果は増えない。

公式仕様：<https://www.metaculus.com/api/>。
