# PencilForecast v0.3 — 最初に読む説明

**研究用・追加購入なし・実資金なし**で作った二択未来予測AIです。Metaculusの問題を取得し、OpenRouterの無料モデルで予測し、記録を保管し、後日結果を比較します。大会の賞金を得るような高精度は**未証明**です。

### いま完成しているもの

- 実際のMetaculus APIから予測問題を取得：成功（2026-11-24）
- 固定した無料モデルで二択確率を出す：成功（実例：質問46544、YES 88%）
- 予測記録のGitHub Actions Artifactへの保存：成功（90日保持）
- 複数の実行記録からの履歴収集：成功（記録1件、取得エラー0）
- 結果が確定した場合のBrier / 対数損失評価：実装・自動テスト済み（まだ実際の解決済み質問はなし）
- GitHubのメインブランチ：安全設定で公式大会自動投稿を無効化

### 操作する場所

| やりたいこと | GitHub Actions |
| --- | --- |
| 問題を探すだけ（LLM呼び出し0） | [PencilForecast v0.3 - research](https://github.com/pencil-source/metac-bot-template/actions/workflows/forecastlab_v03_research.yml) でmodeを `discover` |
| 未来の問題を1つ予測（無料AIを最大1回） | 同じページでmodeを `forecast` に変更。料金・無料枠に注意 |
| 保存済み予測を集めて採点 | [PencilForecast v0.3 - history score](https://github.com/pencil-source/metac-bot-template/actions/workflows/forecastlab_history.yml) |
| 元コード・解説を見る | [日本語の開発説明](research/FORECASTLAB_JA.md) / [履歴採点の説明](research/HISTORY_GUIDE_JA.md) |

**自動実行は設定していません。** `PENCIL_LIVE_ENABLED`を追加・有効化すると公式テンプレートが本番投稿を始めるため、**触らない**でください。特に、公式の `Forecast on new AI tournament questions` / `Forecast on Metaculus Cup` / `Test Bot` は研究用の無料ワークフローとは別物です。

### 注意

1. **お金を入れない**。OpenRouterの利用上限は$0のまま。無料モデル・無料APIが使えなくなった場合は停止する。
2. APIキーはGitHub Secretsだけで管理する。スクショやチャット、公開ソースにコピーしない。以前の画像に映ったMetaculusキーは再発行を推奨。
3. GitHub ActionsのArtifactsは90日で削除されるので、重要な結果は期限内に手元にも保存する。
4. 自動採点で結果が確認できない場合、MetaculusのAPI閲覧制限か未解決の可能性がある。勝手に正解を補わない。
5. 現在の予測AIはまだニュース自動調査がなく、**大会で利益を得る能力も、50%ベースラインより優れるかも未検証**。段階的に改善する。

検証済みの実行：

- [無料AIでの本物の問題予測（成功）](https://github.com/pencil-source/metac-bot-template/actions/runs/45247808012)
- [保存済み予測の履歴取得（成功）](https://github.com/pencil-source/metac-bot-template/actions/runs/45250097724)

現段階では**ユーザーが新しい契約をする必要はありません**。
