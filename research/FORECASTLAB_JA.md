# PencilForecast v0.3 — 追加費用0円での研究版

2026-11-24 時点の構成。**本番大会への投稿・定期予測・有料APIの使用は一切行わない**。競艇・株のAIとは独立した、将来の出来事に対する確率予測研究。

## 実装済み

- Metaculus API の **GET** だけを使い、現在受付中の独立した二択問題を取得する。クローズ済み、二択以外、判定基準のない問題、期限が遠すぎる問題は除く。API仕様・権限により一部の問題が取得できない場合は安全に停止する。
- 無料版 NVIDIA Nemotron を **モデル名末尾が `:free` の固定ID** で最大3回だけ呼び出す。既定は1件、再試行・有料フォールバック・定期実行なし。
- `/api/v1/key` で分かる範囲の無料枠残量を確認。残量が不足していたら予測しない。分からない場合も1～3件という上限は守る。
- 結果を `question_snapshot.json` / `forecasts.jsonl` / `run_status.json` として GitHub Actions の Artifact に保存（90日で期限切れ）。予測確率、日時、質問ID、モデル、APIが返した費用情報、予測理由を保存する。
- `score` コマンドで**明示的に確認した YES/NO 結果だけ**をBrierスコア・対数損失で評価。結果がないときは未評価、Annulled/Ambiguousは採点せず、未来予測後に発生した結果のみ認める。
- Python 3.11標準ライブラリのみ。外部ライブラリのインストール不要。

## GitHub上で使う

GitHubの **Actions → PencilForecast v0.3 - research (manual, free only) → Run workflow**。

- 最初は **mode = discover**：Metaculusで条件に合う質問を探すだけ。LLM呼出は **0回**。
- 次に **mode = forecast**：合う質問を最大1件（既定）だけ予測する。想定モデルの利用料金は$0だが、実際のAPI費用は報告フィールドで確認する。
- `post_id=0` は自動検索。特定の問題を使いたければMetaculusの質問ページの数値IDを入力。
- `max_questions` は1～3（初回は1を推奨）。
- 実行履歴の **Artifacts → pencil-forecast-research** から記録一式をダウンロード。90日以内に保管すること。

**絶対に** GitHubの `PENCIL_LIVE_ENABLED` を有効にしないこと。公式テンプレートの自動大会予測は独立した別の仕組みで、まだ有料モデルに切り替わる可能性がある。手動の `Test Bot` も本研究用ではない。

## ローカルで使う（Windows）

Python 3.11以上。リポジトリ直下で：

```powershell
# LLMを使わない問題探し：Metaculusキーは環境変数で指定可能
python research/forecastlab_v03.py discover --out research_output

# 予測：OPENROUTER_API_KEY が環境変数として設定されている場合のみ
python research/forecastlab_v03.py forecast --max-questions 1 --out research_output

# 結果が確定し、検証用CSVを自分で記入した後に採点
python research/forecastlab_v03.py score --records research_output/forecasts.jsonl --resolutions research/data/resolutions_TEMPLATE.csv --out research_output
```

**APIキーはチャット・スクリーンショット・GitHub公開ファイルに貼り付けない。** GitHub Actions上では Secret から読み込む。かつて画像に写ったMetaculusキーは後で再発行を推奨。

## 正確な採点方法

`research/data/resolutions_TEMPLATE.csv` の列は以下のとおり。

```text
question_id,outcome,resolved_at_utc,verification_url
```

* 未確定の質問は行を作らない。
* `outcome` は公式に確定した `yes` / `no` のみ（途中経過や曖昧判定は不可）。
* `resolved_at_utc` はタイムゾーン付き（例：`2027-01-04T09:00:00+00:00`）。
* `verification_url` は公式の結果確認先。手入力情報の真偽は自動で保証されない。
* 1件1回の「未来予測記録」が原則。モデルの調整後に同じ問題を再採点して良い結果だけを選ぶのは不可。
* 現段階の比較相手は仮の50%予測。これは**非常に弱い基準**であり、Metaculus参加者や強い既存予測モデルに勝てる証拠にはならない。

## 大会賞金との関係

この研究版は**大会に何も投稿しない**。MetaculusはAPIアカウントの権限ごとに質問本文や解決結果の閲覧制限が異なる。研究記録に対する`score`と大会側の公式スコアも別物。成果を測った後、ルールと無料利用枠を確認して初めて本番投稿を検討する。

## 未解決・注意

- 無料モデルには日次回数上限と停止リスクがある。実行を繰り返しても精度の改善にはならない。
- 現時点では**ライブの最新ニュースや各質問固有の統計検索をしていない**。モデルの一般知識からの推測であり、長期的な優位性は未検証。
- 公開GitHubなので質問と予測記録は第三者が閲覧できる場合がある。個人情報を含む質問は使わない。
- Github Actionsの利用もGitHubの利用枠・規約に従う。無制限の無料実行は保証しない。
- 自動スコア連携は、Botが一度も投稿していない質問では公式の解決値をAPIから取得できない場合がある。**未確認の結果を捏造して自動採点しない**。
- 先に作成済みの2026-11-30東京気温予測（YES 28%）は `research/data/legacy_nov30_2026_forecast.json` として別途保存。Metaculusの質問IDを持たないため大会スコアには入らない。

## 研究を継続する基準

単なる成功率ではなく、事前確定した予測を独立した未来イベントで複数集め、Brier・log loss・信頼区間・費用・失敗率を評価する。100件でも内容が似ていれば独立ではない。勝率や大会賞金・生活費を賄える可能性は現時点では証明できていない。

API仕様：<https://www.metaculus.com/api/>  
OpenRouter無料モデル：<https://openrouter.ai/collections/free-models>  
OpenRouter制限：<https://openrouter.ai/docs/api-reference/limits>  
研究用リポジトリ：<https://github.com/pencil-source/metac-bot-template>
