# 設定ファイルの説明

Music Bot Aronaの設定ファイル（`config.yaml`）について詳しく説明します。

## 📁 設定ファイルの場所

設定ファイルは `config.yaml` としてプロジェクトのルートディレクトリに配置します。

初回起動時は `config.default.yaml` をコピーして使用してください：

```bash
cp config.default.yaml config.yaml
```

## 🔧 基本設定

### Bot Token

```yaml
token: "YOUR_BOT_TOKEN_HERE"
```

**必須設定** - Discord Developer Portalで取得したBotトークンを設定してください。

### コマンドプレフィックス

```yaml
prefix: "!"
```

Botのコマンドプレフィックスを設定します。スラッシュコマンドを使用する場合は変更不要です。

## 🎵 音楽設定

### FFmpeg設定

```yaml
music:
  ffmpeg_path: "ffmpeg"           # FFmpegの実行ファイルパス
  ffmpeg_before_options: "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
  ffmpeg_options: "-vn"
```

- `ffmpeg_path`: FFmpegの実行ファイルのパス
- `ffmpeg_before_options`: FFmpegの前処理オプション
- `ffmpeg_options`: FFmpegのオプション

### 再生設定

```yaml
music:
  default_volume: 20              # デフォルト音量 (0-200)
  max_queue_size: 1000            # 最大キューサイズ
  auto_leave_timeout: 300         # 自動退出までの秒数
```

- `default_volume`: ボット起動時のデフォルト音量（0-200の範囲）
- `max_queue_size`: キューに追加できる最大曲数
- `auto_leave_timeout`: ボイスチャンネルが空になった時の自動退出までの秒数

### サーバー管理

```yaml
music:
  max_guilds: 100000000           # 最大サーバー数
  inactive_timeout_minutes: 30    # 非アクティブタイムアウト（分）
```

- `max_guilds`: ボットが同時に接続できる最大サーバー数
- `inactive_timeout_minutes`: 非アクティブなサーバーの状態をクリーンアップするまでの時間

## 📝 メッセージ設定

### カスタムメッセージ

```yaml
music:
  messages:
    # 各種メッセージをカスタマイズ可能
    now_playing: "🎵 現在再生中: {title} ({duration}) - リクエスト: {requester_display_name}"
    queue_empty: "キューが空です。"
    # その他のメッセージ...
```

メッセージの内容をカスタマイズできます。`{title}`, `{duration}`, `{requester_display_name}`などの変数を使用可能です。

## 🌐 ニコニコ動画設定

### ログイン情報（オプション）

```yaml
music:
  nico:
    email: "your_email@example.com"
    password: "your_password"
```

ニコニコ動画のプレミアム会員限定動画を再生する場合に設定します。

**注意**: パスワードは平文で保存されるため、セキュリティに注意してください。

## 🔍 検索設定

### デフォルト検索エンジン

```yaml
music:
  default_search: "ytsearch"      # デフォルト検索エンジン
  max_playlist_items: 50          # プレイリストの最大アイテム数
```

- `default_search`: デフォルトの検索エンジン（通常は`ytsearch`）
- `max_playlist_items`: プレイリストから読み込む最大アイテム数

## 📊 ログ設定

### ログレベル

```yaml
logging:
  level: "INFO"                   # ログレベル (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

ログの出力レベルとフォーマットを設定できます。

## 🎨 表示設定

### プログレスバー

```yaml
music:
  progress_bar_length: 20         # プログレスバーの長さ
```

`/nowplaying`コマンドで表示されるプログレスバーの長さを設定できます。

## 🔒 セキュリティ設定

### 権限チェック

```yaml
music:
  require_voice_channel: true     # ボイスチャンネル参加を必須にする
  admin_only_commands: []          # 管理者のみが使用できるコマンド
```

- `require_voice_channel`: 音楽コマンドを使用する際にボイスチャンネルへの参加を必須にする
- `admin_only_commands`: 管理者のみが使用できるコマンドのリスト

## 📋 設定例

### 基本的な設定例

```yaml
# Discord Bot Token
token: "YOUR_BOT_TOKEN_HERE"

# Bot設定
prefix: "!"

# 音楽設定
music:
  ffmpeg_path: "ffmpeg"
  default_volume: 20
  max_queue_size: 1000
  auto_leave_timeout: 300
  max_guilds: 100000000
  inactive_timeout_minutes: 30
  ffmpeg_before_options: "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
  ffmpeg_options: "-vn"
  progress_bar_length: 20
  require_voice_channel: true
  admin_only_commands: []
  
  # ニコニコ動画設定（オプション）
  nico:
    email: ""
    password: ""
    
  # 検索設定
  default_search: "ytsearch"
  max_playlist_items: 50
  
  # メッセージ設定
  messages:
    now_playing: "🎵 現在再生中: {title} ({duration}) - リクエスト: {requester_display_name}"
    queue_empty: "キューが空です。"
    # その他のメッセージ...

# ログ設定
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

## ⚠️ 注意事項

1. **トークンの管理**: Botトークンは絶対に他人と共有しないでください
2. **パスワードの管理**: ニコニコ動画のパスワードは平文で保存されるため注意してください
3. **権限の設定**: 適切な権限を設定してセキュリティを確保してください
4. **リソースの管理**: `max_guilds`や`max_queue_size`は適切に設定してください

## 🔄 設定の再読み込み

設定ファイルを変更した場合は、ボットを再起動する必要があります：

```bash
# ボットを停止（Ctrl+C）
# 再度起動
python bot.py
```
