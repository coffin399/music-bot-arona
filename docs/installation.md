# Music Bot Arona - Discord音楽ボット

誰でも簡単にDiscord上で音楽を再生できる高機能な音楽ボットです。

## 🎵 主な機能

- **高品質音楽再生**: YouTube、ニコニコ動画、SoundCloudなどから音楽を再生
- **キュー管理**: 効率的な再生キューの管理機能
- **音量制御**: 0-200%の範囲で音量調整
- **ループ再生**: 現在の曲またはキュー全体のループ再生
- **検索機能**: 曲名やアーティスト名での検索
- **カスタマイズ**: 設定ファイルでの動作カスタマイズ

## 🚀 クイックスタート

### 1. 必要な環境
- Python 3.8以上
- FFmpeg
- Discord Bot Token

### 2. インストール
```bash
# リポジトリをクローン
git clone https://github.com/coffin399/music-bot-arona.git
cd music-bot-arona

# 依存関係をインストール
pip install -r requirements.txt

# 設定ファイルを作成
cp config.default.yaml config.yaml
```

### 3. 設定
`config.yaml`の`token`をあなたのDiscord Botトークンに変更してください。

### 4. 起動
```bash
python bot.py
```

## 📖 ドキュメント

詳細なドキュメントは[こちら](https://coffin399.github.io/music-bot-arona/)をご覧ください。

## 🎮 コマンド一覧

### 再生コントロール
- `/play <曲名またはURL>` - 曲を再生またはキューに追加
- `/pause` - 一時停止
- `/resume` - 再生再開
- `/stop` - 再生停止＆キュークリア
- `/skip` - 現在の曲をスキップ
- `/seek <時間>` - 指定時刻に移動
- `/volume <0-200>` - 音量変更

### キュー管理
- `/queue` - キューを表示
- `/nowplaying` - 現在再生中の曲を表示
- `/shuffle` - キューをシャッフル
- `/clear` - キューをクリア
- `/remove <番号>` - 指定番号の曲を削除
- `/loop <off/one/all>` - ループモード設定

### ボイスチャンネル
- `/join` - ボイスチャンネルに接続
- `/leave` - ボイスチャンネルから切断
- `/music_help` - ヘルプを表示

## 🔧 設定

`config.yaml`で以下の設定が可能です：

```yaml
music:
  ffmpeg_path: "ffmpeg"           # FFmpegのパス
  auto_leave_timeout: 300         # 自動退出までの秒数
  max_queue_size: 1000            # 最大キューサイズ
  default_volume: 20              # デフォルト音量 (0-200)
  max_guilds: 100000000           # 最大サーバー数
  inactive_timeout_minutes: 30    # 非アクティブタイムアウト（分）
```

## 🎯 対応サービス

- YouTube
- ニコニコ動画（オプション：ログイン情報を設定可能）
- SoundCloud
- その他yt-dlpが対応する動画サイト

## 🐛 トラブルシューティング

### Botがオンラインにならない
- トークンが正しく設定されているか確認
- インターネット接続を確認

### コマンドが表示されない
- Botに必要な権限があるか確認
- Botを再起動してコマンドの同期を待つ（最大1時間）

### 音楽が再生されない
- FFmpegが正しくインストールされているか確認
- Botがボイスチャンネルに接続する権限があるか確認

## 📄 ライセンス

このプロジェクトはMITライセンスの下で提供されています。

## 🤝 貢献

プルリクエストやイシューの報告を歓迎します！

## 📞 サポート

問題が発生した場合は、[GitHub Issues](https://github.com/coffin399/music-bot-arona/issues)で報告してください。
