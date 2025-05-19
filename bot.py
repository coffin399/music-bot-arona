import discord
from discord.ext import commands
from discord import app_commands  # スラッシュコマンド用
import yaml
import asyncio
import yt_dlp
from collections import deque
import os  # ファイルパスの確認用


# --- 設定ファイルの読み込み ---
def load_config():
    try:
        with open("config.yaml", 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("エラー: config.yamlが見つかりません。")
        exit()
    except yaml.YAMLError as e:
        print(f"エラー: config.yamlの読み込みに失敗しました。: {e}")
        exit()


config = load_config()
TOKEN = config.get('token')
PREFIX = config.get('prefix', '!!')
MESSAGES = config.get('messages', {})
YOUTUBE_COOKIES_FILE = config.get('youtube_cookies_file', '')

if not TOKEN or TOKEN == "YOUR_DISCORD_BOT_TOKEN":
    print("エラー: config.yaml に有効なDiscord BOTトークンが設定されていません。")
    exit()

# --- FFmpegオプション ---
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# --- yt-dlpオプション ---
YDL_OPTS_BASE = {
    'format': 'bestaudio/best',
    'quiet': True,
    'extract_flat': True,
    'default_search': 'ytsearch',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'opus',
        'preferredquality': '192',
    }],
    'source_address': '0.0.0.0'
}

# YouTube Cookieファイルの設定
if YOUTUBE_COOKIES_FILE:
    if os.path.exists(YOUTUBE_COOKIES_FILE):
        YDL_OPTS_BASE['cookiefile'] = YOUTUBE_COOKIES_FILE
        print(MESSAGES.get('youtube_cookie_load_info',
                           "YouTube Cookieファイルをロードしました。ログイン状態で動作します。"))
    else:
        print(MESSAGES.get('youtube_cookie_file_not_found',
                           "警告: config.yamlで指定されたYouTube Cookieファイルが見つかりません: {} ログインせずに続行します。").format(
            YOUTUBE_COOKIES_FILE))

# --- BOTの初期設定 ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)  # 標準ヘルプコマンドを無効化
tree = app_commands.CommandTree(bot)  # スラッシュコマンドツリー

# --- グローバル変数 ---
queues = {}
current_song_info = {}


# --- ヘルパー関数 (変更なし) ---
async def play_next(ctx_or_interaction):  # ctxまたはinteractionを受け取れるように
    guild_id = ctx_or_interaction.guild.id
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx_or_interaction.guild)

    # メッセージ送信先を判別
    async def send_message(content):
        if isinstance(ctx_or_interaction, commands.Context):
            await ctx_or_interaction.send(content)
        elif isinstance(ctx_or_interaction, discord.Interaction):
            # play_nextからは通常、followup.sendを使うか、元のチャンネルIDを保持しておく必要がある
            # ここでは元のチャンネルに送る (playコマンドのctxからchannelを取得して渡す方が確実)
            # playコマンド内でchannelを保持して渡すようにする方が良い
            channel = bot.get_channel(ctx_or_interaction.channel_id)
            if channel:
                await channel.send(content)
            else:  # フォールバック
                print(f"Warning: Could not find channel {ctx_or_interaction.channel_id} to send play_next message.")

    if guild_id in queues and queues[guild_id]:
        if not voice_client or not voice_client.is_connected():
            queues[guild_id].clear()
            current_song_info.pop(guild_id, None)
            return

        if voice_client.is_playing() or voice_client.is_paused():
            return

        song_data = queues[guild_id].popleft()
        stream_url = song_data['url']
        title = song_data['title']
        webpage_url = song_data['webpage_url']

        try:
            source = await discord.FFmpegOpusAudio.from_probe(stream_url, **FFMPEG_OPTIONS)
            # play_next_after_error_check に渡す context/interaction を統一
            callback_context = ctx_or_interaction
            voice_client.play(source,
                              after=lambda e: bot.loop.create_task(play_next_after_error_check(callback_context, e)))
            current_song_info[guild_id] = {'title': title, 'webpage_url': webpage_url}
            await send_message(MESSAGES.get('now_playing', "再生中: {}").format(title))
        except Exception as e:
            await send_message(MESSAGES.get('error_playing', "再生中にエラーが発生しました: {}").format(e))
            print(f"Error playing next song: {e}")
            bot.loop.create_task(play_next_after_error_check(ctx_or_interaction, e))
    else:
        current_song_info.pop(guild_id, None)


async def play_next_after_error_check(ctx_or_interaction, error):
    if error:
        print(f'Player error: {error}')
    await play_next(ctx_or_interaction)


# --- イベント ---
@bot.event
async def on_ready():
    print(f'{bot.user.name} が起動しました！')
    await bot.change_presence(activity=discord.Game(name=f"音楽再生中 | /help"))
    try:
        # スラッシュコマンドをグローバルに同期 (全てのサーバーで利用可能)
        # テスト中は特定のサーバーIDを指定すると反映が早い: guild=discord.Object(id=YOUR_SERVER_ID)
        synced = await tree.sync()
        print(f"{len(synced)}個のスラッシュコマンドを同期しました。")
        for cmd in synced:
            print(f"- {cmd.name}")
    except Exception as e:
        print(f"スラッシュコマンドの同期に失敗しました: {e}")


# --- スラッシュコマンド ---
@tree.command(name="help", description="音楽BOTのコマンド一覧を表示します。")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(title="音楽BOT コマンド一覧", color=discord.Color.blurple())
    embed.add_field(name=f"`{PREFIX}play <曲名またはURL>` (`{PREFIX}p`)", value="曲を再生またはキューに追加します。",
                    inline=False)
    embed.add_field(name=f"`{PREFIX}skip` (`{PREFIX}s`)", value="現在の曲をスキップします。", inline=False)
    embed.add_field(name=f"`{PREFIX}stop` (`{PREFIX}leave`, `{PREFIX}disconnect`)",
                    value="再生を停止し、BOTをVCから切断します。", inline=False)
    embed.add_field(name=f"`{PREFIX}queue` (`{PREFIX}q`)", value="現在の再生キューを表示します。", inline=False)
    embed.add_field(name=f"`{PREFIX}nowplaying` (`{PREFIX}np`)", value="現在再生中の曲を表示します。", inline=False)
    embed.add_field(name=f"`{PREFIX}pause`", value="再生を一時停止します。(サーバー管理者推奨)", inline=False)
    embed.add_field(name=f"`{PREFIX}resume`", value="一時停止した再生を再開します。(サーバー管理者推奨)", inline=False)
    embed.set_footer(text=f"Prefix: {PREFIX} | このヘルプはスラッシュコマンド /help です。")
    await interaction.response.send_message(embed=embed, ephemeral=True)  # ephemeral=Trueで本人にのみ表示


# --- プレフィックスコマンド (変更なし、または微調整) ---
@bot.command(name='play', aliases=['p'])
async def play(ctx: commands.Context, *, query: str):
    if not ctx.author.voice:
        await ctx.send(MESSAGES.get('join_voice_channel_first', "まずボイスチャンネルに参加してください。"))
        return

    voice_channel = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if voice_client is None:
        try:
            voice_client = await voice_channel.connect(timeout=10.0, reconnect=True)
        except asyncio.TimeoutError:
            await ctx.send(MESSAGES.get('connect_timeout', "ボイスチャンネルへの接続がタイムアウトしました。"))
            return
        except Exception as e:
            await ctx.send(MESSAGES.get('error_generic', "エラーが発生しました: {}").format(e))
            return
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)

    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = deque()

    await ctx.send(MESSAGES.get('searching_song', "{} を検索中...").format(query))
    loop = asyncio.get_event_loop()

    ydl_opts_to_use = YDL_OPTS_BASE.copy()

    try:
        with yt_dlp.YoutubeDL(ydl_opts_to_use) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))

        if not info:
            await ctx.send(MESSAGES.get('song_not_found', "曲が見つかりませんでした。"))
            return

        songs_to_add = []
        if 'entries' in info:
            if not info['entries']:
                await ctx.send(MESSAGES.get('song_not_found', "曲が見つかりませんでした。"))
                return

            is_true_playlist = info.get('extractor_key') and 'playlist' in info.get('extractor_key').lower()
            is_url_input = query.startswith("http://") or query.startswith("https://")

            if is_url_input and is_true_playlist:
                for entry in info['entries']:
                    if entry and entry.get('url') and entry.get('title'):
                        songs_to_add.append({'url': entry['url'], 'title': entry['title'],
                                             'webpage_url': entry.get('webpage_url', entry.get('original_url', ''))})
            elif info['entries']:
                entry = info['entries'][0]
                if entry and entry.get('url') and entry.get('title'):
                    songs_to_add.append({'url': entry['url'], 'title': entry['title'],
                                         'webpage_url': entry.get('webpage_url', entry.get('original_url', ''))})
                else:
                    await ctx.send(MESSAGES.get('song_not_found', "曲が見つかりませんでした。"))
                    return
            else:
                await ctx.send(MESSAGES.get('song_not_found', "曲が見つかりませんでした。"))
                return

        elif 'url' in info:
            songs_to_add.append(
                {'url': info['url'], 'title': info['title'], 'webpage_url': info.get('webpage_url', query)})

        else:
            await ctx.send(MESSAGES.get('song_not_found', "曲が見つかりませんでした。"))
            return

        if not songs_to_add:
            await ctx.send(MESSAGES.get('song_not_found', "曲が見つかりませんでした。"))
            return

        for song_data in songs_to_add:
            queues[guild_id].append(song_data)

        if len(songs_to_add) == 1:
            await ctx.send(
                MESSAGES.get('added_to_queue', "{} をキューに追加しました。").format(songs_to_add[0]['title']))
        elif len(songs_to_add) > 1:
            await ctx.send(
                MESSAGES.get('added_playlist_to_queue', "プレイリストから {} 曲をキューに追加しました。").format(
                    len(songs_to_add)))

    except yt_dlp.utils.DownloadError as e:
        # 特定のエラーメッセージを判別（例：年齢制限など）
        if "Sign in to confirm your age" in str(e) or "confirm your age" in str(e).lower():
            await ctx.send(
                f"この動画は年齢制限があります。config.yamlで `youtube_cookies_file` を設定すると再生できる場合があります。\nエラー詳細: {e}")
        else:
            await ctx.send(
                MESSAGES.get('youtube_search_error', "YouTubeでの検索または情報取得に失敗しました。") + f": {e}")
        print(f"yt-dlp DownloadError: {e}")
        return
    except Exception as e:
        await ctx.send(MESSAGES.get('error_generic', "エラーが発生しました: {}").format(e))
        print(f"Generic error in play command: {e}")
        return

    if not voice_client.is_playing() and not voice_client.is_paused():
        # play_next に ctx を渡す
        await play_next(ctx)


@bot.command(name='skip', aliases=['s'])
async def skip(ctx: commands.Context):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.is_connected():
        await ctx.send(MESSAGES.get('bot_not_in_voice_channel', "BOTがボイスチャンネルに接続していません。"))
        return

    if not voice_client.is_playing() and not voice_client.is_paused():
        await ctx.send(MESSAGES.get('nothing_playing', "現在何も再生していません。"))
        return

    voice_client.stop()
    await ctx.send(MESSAGES.get('skipped', "スキップしました。"))
    # play_next は after コールバックで ctx を伴って呼ばれる


@bot.command(name='stop', aliases=['leave', 'disconnect'])
async def stop(ctx: commands.Context):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    guild_id = ctx.guild.id

    if voice_client and voice_client.is_connected():
        if guild_id in queues:
            queues[guild_id].clear()
        current_song_info.pop(guild_id, None)

        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()

        await voice_client.disconnect()
        await ctx.send(MESSAGES.get('stopped', "再生を停止し、ボイスチャンネルから切断しました。"))
    else:
        await ctx.send(MESSAGES.get('bot_not_in_voice_channel', "BOTがボイスチャンネルに接続していません。"))


@bot.command(name='queue', aliases=['q'])
async def queue_command(ctx: commands.Context):
    guild_id = ctx.guild.id
    embed = discord.Embed(title="再生キュー", color=discord.Color.blue())

    np_text = MESSAGES.get('nothing_playing', "現在何も再生していません。")
    if guild_id in current_song_info and current_song_info[guild_id]:
        np_title = current_song_info[guild_id]['title']
        np_url = current_song_info[guild_id].get('webpage_url', '#')
        np_text = f"[{np_title}]({np_url})"
    embed.add_field(name="再生中", value=np_text, inline=False)

    if guild_id not in queues or not queues[guild_id]:
        if not (guild_id in current_song_info and current_song_info[guild_id]):
            embed.add_field(name="次の曲", value=MESSAGES.get('queue_empty', "キューは空です。"), inline=False)
    else:
        song_list_text = []
        for i, song_data in enumerate(list(queues[guild_id])[:10]):
            song_list_text.append(f"{i + 1}. [{song_data['title']}]({song_data.get('webpage_url', '#')})")

        if song_list_text:
            embed.add_field(name="次の曲", value="\n".join(song_list_text), inline=False)
        else:
            embed.add_field(name="次の曲", value=MESSAGES.get('queue_empty', "キューは空です。"), inline=False)

        if len(queues[guild_id]) > 10:
            embed.set_footer(text=f"他 {len(queues[guild_id]) - 10} 曲がキューにあります。")

    await ctx.send(embed=embed)


@bot.command(name='nowplaying', aliases=['np'])
async def nowplaying(ctx: commands.Context):
    guild_id = ctx.guild.id
    if guild_id in current_song_info and current_song_info[guild_id]:
        title = current_song_info[guild_id]['title']
        url = current_song_info[guild_id].get('webpage_url', '#')
        embed = discord.Embed(title="再生中", description=f"[{title}]({url})", color=discord.Color.green())
        await ctx.send(embed=embed)
    else:
        await ctx.send(MESSAGES.get('nothing_playing', "現在何も再生していません。"))


@bot.command(name='pause')
@commands.has_permissions(manage_guild=True)
async def pause(ctx: commands.Context):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await ctx.send(MESSAGES.get('paused', "一時停止しました。"))
    elif voice_client and voice_client.is_paused():
        await ctx.send("既に一時停止されています。")
    else:
        await ctx.send(MESSAGES.get('nothing_playing', "現在何も再生していません。"))


@bot.command(name='resume')
@commands.has_permissions(manage_guild=True)
async def resume(ctx: commands.Context):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await ctx.send(MESSAGES.get('resumed', "再生を再開しました。"))
    elif voice_client and voice_client.is_playing():
        await ctx.send("既に再生中です。")
    else:
        await ctx.send(MESSAGES.get('nothing_playing', "現在何も再生していません。"))


# --- エラーハンドリング (変更なし) ---
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"コマンドの引数が不足しています: `{error.param.name}`\n`/help` または `{PREFIX}help {ctx.command.name}` でヘルプを確認してください。")
    elif isinstance(error, commands.CommandInvokeError):
        original = error.original
        print(f"CommandInvokeError: {original}")
        if isinstance(original, yt_dlp.utils.DownloadError):
            await ctx.send(MESSAGES.get('youtube_search_error', "YouTubeでの検索または情報取得に失敗しました。"))
        elif isinstance(original, discord.errors.ClientException) and str(original) == "Already playing audio.":
            await ctx.send("既に何か再生中です。")
        else:
            await ctx.send(MESSAGES.get('error_generic', "エラーが発生しました: {}").format(original))
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("このコマンドを実行する権限がありません。")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(
            f"引数の型が正しくありません。`/help` または `{PREFIX}help {ctx.command.name}` でヘルプを確認してください。")
    else:
        print(f'Unhandled error: {error} (Type: {type(error)})')
        await ctx.send(MESSAGES.get('error_generic', "予期せぬエラーが発生しました: {}").format(error))


# --- BOTの実行 ---
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("エラー: 無効なトークンです。config.yaml のDiscord BOTトークンを確認してください。")
    except Exception as e:
        print(f"BOTの起動中に予期せぬエラーが発生しました: {e}")