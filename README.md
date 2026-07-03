# feed-relay

Claude Code Routines実行環境のegress制限を回避するための中継リポジトリ。

## 仕組み

```
[GitHub Actions]                [このリポジトリ]              [Claude Code Routines]
egress制限なし                   feeds.json を保持              api.github.com / raw.githubusercontent.com
  │                                    │                          への到達は確認済み(403にならない)
  ├─ Google News RSS を取得            │                                │
  ├─ はてブ・Techmeme等を取得          │                                │
  ├─ 公開日時をここで確定  ───────────▶│                                │
  └─ feeds.json をコミット・push       │                                │
                                        └──────── raw.githubusercontent.com 経由で取得 ────▶│
```

「個別記事ページを開いて公開日を確認する」という、Routines側では403で
実行不可能だった工程を、GitHub Actions側(ネットワーク制限なし)に丸ごと
移してしまう構成です。Routinesは出来上がったJSONを1回取得するだけで済みます。

## セットアップ手順

1. GitHubに新しいリポジトリを作成する(公開リポジトリで問題なければ設定不要。
   非公開にする場合はPersonal Access Tokenが必要になるので、まずは公開推奨)
2. このディレクトリの中身をそのままリポジトリ直下にpushする
   ```
   .github/workflows/fetch-feeds.yml
   scripts/fetch_feeds.py
   requirements.txt
   ```
3. `scripts/fetch_feeds.py` の `FEEDS` リストを、Tak さんが既に
   `AI自動化ナビ` で使っている実際のフィード一覧(Google Newsの検索クエリ、
   はてブ、Techmeme、海外ソース等)に置き換える
4. GitHubのActionsタブから `Fetch RSS Feeds` ワークフローを一度手動実行
   (workflow_dispatch)して、`feeds.json` が正しく生成・コミットされるか確認する
5. 生成された `feeds.json` に対して、以下のURLで取得できることを確認する
   ```
   https://raw.githubusercontent.com/<ユーザー名>/<リポジトリ名>/main/feeds.json
   ```

## Routines側プロンプトの変更

既存のRoutineプロンプトのうち、「各RSSフィードを直接取得する」「個別記事
ページを開いて公開日を確認する」という工程を、以下のように差し替えてください。

```
## 記事候補の取得(変更後)

以下のURLをcurlで取得し、JSONとしてパースせよ。
これは事前にGitHub Actions側でRSS取得・公開日確認まで完了済みのデータであり、
このURLへのアクセスはegressポリシーでブロックされない(api.github.com /
raw.githubusercontent.com は到達可能であることを確認済み)。

curl -s https://raw.githubusercontent.com/<ユーザー名>/<リポジトリ名>/main/feeds.json

取得したJSONの items 配列には、各記事の title / url / published_at /
published_at_confirmed / age_hours / sources が含まれる。
published_at_confirmed が true の記事のみ、公開日確認済みとして扱ってよい。
false または published_at が null の記事は「要確認リード」に分類すること。

このJSON取得が失敗した場合のみ、従来通りWebSearchでのフォールバックを行うこと。
```

これで、Routines側は個別サイトへのfetchを一切行わずに、公開日確認済みの
候補リストを受け取れるようになります。

## 運用上の注意

- GitHub Actionsのcron実行時刻は、Routineの実行時刻より前になるよう
  余裕を持って設定してください(上記の例はJST 06:00に設定、Routineの
  実行がその後であることを確認してください)
- `feeds.json` の更新が失敗している場合(Actionsタブでエラーを確認できる)、
  古いデータのままRoutinesが読むことになるので、Actionsの実行結果は
  たまに見ておくと安心です
- 将来的に非公開リポジトリにする場合は、Personal Access Tokenを発行し、
  `curl -H "Authorization: token $GITHUB_TOKEN" ...` の形でContents API
  (`api.github.com/repos/.../contents/feeds.json`)経由に切り替える必要が
  あります(raw.githubusercontent.comは非公開リポジトリのファイルには
  認証なしでは到達できないため)
