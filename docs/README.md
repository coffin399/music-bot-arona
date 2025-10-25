# Music Bot Arona Documentation

このディレクトリには、Music Bot Aronaのドキュメントサイトが含まれています。

## ファイル構成

- `index.html` - メインのドキュメントページ
- `styles.css` - スタイルシート
- `script.js` - JavaScript機能
- `README.md` - このファイル

## GitHub Pagesでのデプロイ

このドキュメントサイトはGitHub Pagesでホストするように設計されています。

### デプロイ手順

1. GitHubリポジトリの設定に移動
2. 「Pages」セクションを選択
3. 「Source」で「Deploy from a branch」を選択
4. 「Branch」で「main」を選択
5. 「Folder」で「/docs」を選択
6. 「Save」をクリック

### カスタムドメイン（オプション）

カスタムドメインを使用する場合：

1. `docs/CNAME`ファイルを作成
2. ドメイン名を記述（例：`music-bot-arona.example.com`）
3. DNS設定でドメインをGitHub Pagesに設定

## ローカルでの確認

ローカルでドキュメントサイトを確認するには：

```bash
# docsディレクトリに移動
cd docs

# 簡単なHTTPサーバーを起動（Python 3の場合）
python -m http.server 8000

# ブラウザで http://localhost:8000 にアクセス
```

## カスタマイズ

### スタイルの変更

`styles.css`を編集してデザインをカスタマイズできます。

### コンテンツの更新

`index.html`を編集してコンテンツを更新できます。

### 機能の追加

`script.js`にJavaScript機能を追加できます。

## ライセンス

このドキュメントサイトはMITライセンスの下で提供されています。
