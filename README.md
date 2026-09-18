# SNS Auto Scheduler Toolkit

Bluesky向けの「投稿予約」「エンゲージメント自動化（いいね・フォロー）」「アフィリエイト投稿」をまとめて行う、実運用ベースのSNS自動化ツール群です。実際に個人のSNS運用（毎日の情報発信・フォロワー獲得）で継続稼働させていたスクリプトをもとに、汎用的に使える形へ整理・再構成したものです。

## できること

- **CSVベースの予約投稿**: `posts.csv` に日時と本文を書いておくだけで、指定時刻に自動投稿
- **積極的エンゲージメント**: フォローバック、キーワード検索からの「いいね」、関連ユーザーの自動フォロー
- **アフィリエイト投稿の自動配信**: 指定時刻にランダムでアフィリエイト文言を選び、OGP情報（リンクカードの画像・タイトル）を自動取得して投稿
- **予約枯渇時の自動延長フック**: 全ての予約投稿が消化されると、同じフォルダの `update_posts.py` を自動実行する仕組み（次バッチの `posts.csv` を生成するスクリプトを自作して配置すれば、投稿ネタが尽きることなく運用を継続できる）
- **常駐運用**: Windows タスクスケジューラーでPC起動時にバックグラウンド実行する手順を同梱

## 構成

| ファイル | 役割 |
|---|---|
| `unified_scheduler.py` | メインスクリプト。予約投稿・エンゲージメント・アフィリエイト投稿を1プロセスで統合運用 |
| `bluesky_scheduler.py` | `posts.csv` からの予約投稿のみを行うシンプル版 |
| `bluesky_proactive_bot.py` | フォロバ・キーワードいいね・関連ユーザーフォローのみを行う単体スクリプト |
| `csv_image_url_filler.py` | `posts.csv` の特定リンクを含む行に画像URLを一括付与するユーティリティ |
| `run_scheduler.bat` / `run_hidden.vbs` | `unified_scheduler.py` をバックグラウンドで常駐実行するためのランチャー |
| `docs/TASK_SCHEDULER_GUIDE.md` | Windowsタスクスケジューラーへの登録手順 |
| `posts.sample.csv` | 予約投稿CSVのフォーマット例 |
| `affiliate_posts.sample.json` | アフィリエイト投稿リストのフォーマット例 |

## 技術スタック

- Python 3.10+
- [atproto](https://github.com/MarshalX/atproto)（Bluesky/AT Protocol 公式相当のPython SDK）
- `python-dotenv`（環境変数管理）
- `requests`（OGP情報の取得）

## セットアップ

### 1. Blueskyのアプリパスワードを発行

1. Blueskyにログイン
2. **設定 → プライバシーとセキュリティ → アプリパスワード** を開く
3. 「アプリパスワードを追加」をクリックして新しいパスワードを生成
4. 表示された `xxxx-xxxx-xxxx-xxxx` 形式のパスワードをコピー（メインパスワードは絶対に使わないこと）

### 2. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を開いて、`BLUESKY_HANDLE` と `BLUESKY_PASSWORD` を入力してください。

### 3. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 4. 投稿データの用意

```bash
cp posts.sample.csv posts.csv
cp affiliate_posts.sample.json affiliate_posts.json
```

`posts.csv` を編集し、実際に投稿したい日時・本文に書き換えてください。

| カラム | 内容 |
|---|---|
| `scheduled_datetime` | 投稿日時（例: `2026-02-23T09:00:00`、JST） |
| `content` | 投稿内容（300文字以内） |
| `posted` | 投稿済みなら `true` が自動で入る（手動編集不要） |
| `image_path` | 添付したいローカル画像のパス（任意） |

### 5. 実行

```bash
python unified_scheduler.py
```

- 起動するとスケジュールに沿って自動で投稿します
- 5分おきに投稿予定をチェックし、5時間おきにエンゲージメント（いいね・フォロー）を実行します
- 全ての予約投稿が完了すると、次のバッチ生成スクリプトの呼び出しを試みます

### 6. バックグラウンド常時実行（任意）

PCを起動している間ずっと自動運用したい場合は、`docs/TASK_SCHEDULER_GUIDE.md` の手順でWindowsタスクスケジューラーに登録してください。24時間稼働させたい場合はVPS等でも実行可能です。

## 注意事項

- `.env` ファイルは絶対にGitやSNSで公開しないでください（`.gitignore` で除外済み）
- Blueskyの利用規約に従い、過度な自動いいね・自動フォローは控えてください（本ツールはスリープを挟んで送信頻度を抑える設計にしています）
- アフィリエイト投稿を行う場合は、各ASP・プラットフォームの規約（ステルスマーケティング規制等）を確認の上、自己責任でご利用ください

## ライセンス

MIT License
