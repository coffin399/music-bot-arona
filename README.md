# music-bot-arona
Development discontinued, merged into the following repository
https://github.com/coffin399/llmcord-JP-plana

# Discord Music Bot

Discord上で音楽を再生できる単独動作型のBotプログラムです。

## 必要要件

- Python 3.8以上
- FFmpeg（音声処理用）
- Discord Bot Token

## インストール手順

### 1. 必要なパッケージをインストール

```bash
pip install discord.py yt-dlp
```

### 2. FFmpegをインストール

**Windows:**
1. [FFmpeg公式サイト](https://ffmpeg.org/download.html)からダウンロード
2. PATHに追加するか、config.jsonで`ffmpeg_path`を指定

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Mac (Homebrewを使用)
brew install ffmpeg
```

### 3. ファイル構成

```
music-bot/
├── music_bot.py           # メインプログラム
├── ytdlp_wrapper.py       # yt-dlpラッパー（または services/ytdlp_wrapper.py）
├── config.json            # 設定ファイル（初回起動時に自動生成）
├── config-example.json    # 設定例（初回起動時に自動生成）
├── cache/                 # キャッシュディレクトリ（自動生成）
└── nico_cookies.txt       # ニコニコ動画用Cookie（オプション、自動生成）
```

### 4. Discord Bot の作成

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. 「New Application」をクリックしてアプリケーションを作成
3. 左メニューの「Bot」をクリック
4. 「Add Bot」をクリックしてBotを作成
5. 「Token」の下の「Copy」ボタンでトークンをコピー
6. 「Privileged Gateway Intents」で以下を有効化：
   - MESSAGE CONTENT INTENT
   - SERVER MEMBERS INTENT

### 5. Botをサーバーに招待

1. 左メニューの「OAuth2」→「URL Generator」をクリック
2. 「Scopes」で以下を選択：
   - `bot`
   - `applications.commands`
3. 「Bot Permissions」で以下を選択：
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Add Reactions
   - Connect
   - Speak
   - Use Voice Activity
   - Priority Speaker
4. 生成されたURLをコピーしてブラウザで開き、サーバーに招待

## 使い方

### 初回起動

```bash
python music_bot.py
```

初回起動時：
1. `config-example.json`が自動生成されます
2. `config-example.json`が`config.json`にコピーされます
3. プログラムが終了するので、`config.json`を編集してください

### 設定ファイルの編集

`config.json`を開いて、最低限以下を設定：

```json
{
  "bot": {
    "token": "YOUR_BOT_TOKEN_HERE"  // ← ここにBotトークンを貼り付け
  }
}
```

### Botの起動

```bash
python music_bot.py
```

## コマンド一覧

### 🎵 再生コントロール

| コマンド | 説明 |
|---------|------|
| `/play <曲名またはURL>` | 曲を再生またはキューに追加 |
| `/pause` | 一時停止 |
| `/resume` | 再生再開 |
| `/stop` | 再生停止＆キュークリア |
| `/skip` | 現在の曲をスキップ |
| `/volume <0-200>` | 音量変更 |

### 📋 キュー管理

| コマンド | 説明 |
|---------|------|
| `/queue` | キューを表示 |
| `/nowplaying` | 現在再生中の曲を表示 |
| `/shuffle` | キューをシャッフル |
| `/clear` | キューをクリア |
| `/remove <番号>` | 指定番号の曲を削除 |
| `/loop <off/one/all>` | ループモード設定 |

### 🔊 ボイスチャンネル

| コマンド | 説明 |
|---------|------|
| `/join` | ボイスチャンネルに接続 |
| `/leave` | ボイスチャンネルから切断 |
| `/music_help` | ヘルプを表示 |

## 対応サービス

- YouTube
- ニコニコ動画（オプション：ログイン情報を設定可能）
- SoundCloud
- その他yt-dlpが対応する動画サイト

## トラブルシューティング

### Botがオンラインにならない
- トークンが正しく設定されているか確認
- インターネット接続を確認

### コマンドが表示されない
- Botに必要な権限があるか確認
- Botを再起動してコマンドの同期を待つ（最大1時間）

### 音楽が再生されない
- FFmpegが正しくインストールされているか確認
- Botがボイスチャンネルに接続する権限があるか確認

### エラー: ytdlp_wrapperが見つからない
- `ytdlp_wrapper.py`が同じディレクトリまたは`services/`ディレクトリにあるか確認

## カスタマイズ

`config.json`で以下の設定が可能：

```json
{
  "music": {
    "ffmpeg_path": "ffmpeg",           // FFmpegのパス
    "auto_leave_timeout": 10,          // 自動退出までの秒数
    "max_queue_size": 9000,            // 最大キューサイズ
    "default_volume": 50,              // デフォルト音量 (0-200)
    "messages": {                      // メッセージのカスタマイズ
      // 各種メッセージをカスタマイズ可能
    }
  }
}
```

## ライセンス

このプログラムはMITライセンスで提供されています。

## 注意事項

- 著作権を遵守してご利用ください
- Botの使用は各サーバーのルールに従ってください
- 大量のリクエストは避け、適切に使用してください