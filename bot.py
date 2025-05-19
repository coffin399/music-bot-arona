import discord
from discord.ext import commands
import wavelink
import yaml
import logging
import re # URL判定用

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 設定ファイルの読み込み ---
try:
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    logger.critical("config.yaml が見つかりません。作成してください。")
    exit()
except yaml.YAMLError as e:
    logger.critical(f"config.yaml の読み込みに失敗しました: {e}")
    exit()

TOKEN = config.get("discord_token")
LAVALINK_HOST = config.get("lavalink_host")
LAVALINK_PORT = config.get("lavalink_port")
LAVALINK_PASSWORD = config.get("lavalink_password")
LAVALINK_IDENTIFIER = config.get("lavalink_identifier", "WavelinkNode")
PREFIX = config.get("prefix", "!!")
MESSAGES = config.get("messages", {})

if not TOKEN:
    logger.critical("Discordトークンがconfig.yamlに設定されていません。")
    exit()

# --- Intents設定 ---
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# --- カスタムPlayerクラス ---
class LavalinkPlayer(wavelink.Player):
    """wavelink.Playerを拡張したカスタムPlayerクラス"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = wavelink.Queue()
        self.text_channel: discord.TextChannel | None = None # コマンドが実行されたチャンネルを保持

    async def play_next_track(self):
        """キューから次の曲を再生する"""
        if self.playing or self.paused:
            return

        if not self.queue.is_empty:
            next_track: wavelink.Playable = self.queue.get()
            await self.play(next_track)
            if self.text_channel:
                try:
                    await self.text_channel.send(MESSAGES.get('now_playing', "🎶 再生中: **{title}**").format(title=next_track.title))
                except discord.HTTPException:
                    logger.warning(f"Failed to send 'now_playing' message to {self.text_channel.name}")
        else:
            if self.text_channel:
                # logger.info(f"Queue is empty for guild {self.guild.id}. Consider auto-disconnect.")
                # 自動切断などの処理をここに入れることも可能
                pass

# --- Botイベント ---
@bot.event
async def on_ready():
    logger.info(f'{bot.user} としてログインしました。')
    logger.info(f"Prefix: {PREFIX}")
    logger.info(f"Wavelink Version: {wavelink.__version__}")
    activity = discord.Activity(type=discord.ActivityType.listening, name=f"{PREFIX}help")
    await bot.change_presence(activity=activity)
    await setup_wavelink()

async def setup_wavelink():
    """Wavelinkノードをセットアップして接続する"""
    logger.info("Lavalinkノードへの接続を試みています...")
    node = wavelink.Node(
        uri=f"http://{LAVALINK_HOST}:{LAVALINK_PORT}",
        password=LAVALINK_PASSWORD,
        identifier=LAVALINK_IDENTIFIER,
        # session_id=bot.session_id # discord.py v2.x & wavelink v2.x
    )
    try:
        # discord.py v2.x and wavelink v2.x/v3.x:
        await wavelink.Pool.connect(nodes=[node], client=bot, cache_capacity=100)
        # For wavelink v1.x or older structure:
        # await wavelink.NodePool.connect(client=bot, nodes=[node])
    except Exception as e:
        logger.error(f"Lavalinkノードへの接続に失敗しました: {e}")
        logger.error("Lavalinkサーバーが起動しているか、config.yamlの設定が正しいか確認してください。")

@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    node = payload.node

@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player: LavalinkPlayer | None = payload.player
    reason = payload.reason
    # logger.info(f"Track ended in guild {player.guild.id if player else 'N/A'}. Reason: {reason}")
    if player:
        if reason.may_start_next() or reason == wavelink.TrackEndReason.FINISHED:
            await player.play_next_track()

@bot.event
async def on_wavelink_track_exception(payload: wavelink.TrackExceptionEventPayload):
    player: LavalinkPlayer | None = payload.player
    track = payload.track
    error = payload.error
    logger.error(f"Track '{track.title if track else 'Unknown'}' でエラー: {error}")
    if player and player.text_channel:
        await player.text_channel.send(MESSAGES.get('error_occurred', "エラーが発生しました: {error}").format(error=f"曲の再生中に問題が発生しました ({error.message if hasattr(error, 'message') else str(error)[:100]})"))
    if player:
        await player.play_next_track() # エラー後も次の曲へ

@bot.event
async def on_wavelink_track_stuck(payload: wavelink.TrackStuckEventPayload):
    player: LavalinkPlayer | None = payload.player
    track = payload.track
    threshold = payload.threshold_ms
    logger.warning(f"Track '{track.title if track else 'Unknown'}' got stuck for {threshold}ms.")
    if player and player.text_channel:
        await player.text_channel.send(f"⚠️ 曲 '{track.title}' の再生がスタックしました。スキップを試みます。")
    if player:
        await player.play_next_track()

# --- 音楽コマンド Cog ---
class MusicCog(commands.Cog, name="Music"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """全てのコマンドの前に実行されるチェック"""
        if not ctx.guild:
            await ctx.send("このコマンドはサーバー内でのみ使用できます。")
            return False
        return True

    async def get_player(self, ctx: commands.Context, connect_if_none: bool = False) -> LavalinkPlayer | None:
        """現在のギルドのプレイヤーを取得する。必要なら接続する。"""
        if not ctx.guild:
            return None

        player: LavalinkPlayer | None = ctx.voice_client # type: ignore
        if player is None and connect_if_none:
            if ctx.author.voice:
                try:
                    player = await ctx.author.voice.channel.connect(cls=LavalinkPlayer) # type: ignore
                    player.text_channel = ctx.channel
                    await ctx.send(MESSAGES.get('connected_to_vc', "🔊 **{channel}** に接続しました。").format(channel=player.channel.name))
                except discord.ClientException:
                    await ctx.send("ボイスチャンネルへの接続に失敗しました。権限を確認してください。")
                    return None
                except Exception as e:
                    logger.error(f"Error connecting to voice channel: {e}")
                    await ctx.send("ボイスチャンネルへの接続中に予期せぬエラーが発生しました。")
                    return None
            else:
                await ctx.send(MESSAGES.get('join_vc_first', "先にボイスチャンネルに参加してください。"))
                return None
        elif player and player.text_channel is None : # 再接続などで text_channel が未設定の場合
             player.text_channel = ctx.channel

        return player

    @commands.command(name='connect', aliases=['join', 'j'], help="ボイスチャンネルに接続します。")
    async def connect_command(self, ctx: commands.Context, *, channel: discord.VoiceChannel | None = None):
        player = await self.get_player(ctx)

        if player and player.connected:
            await ctx.send(MESSAGES.get('already_connected', "既にボイスチャンネルに接続しています。"))
            return

        if channel:
            target_channel = channel
        elif ctx.author.voice:
            target_channel = ctx.author.voice.channel
        else:
            await ctx.send(MESSAGES.get('join_vc_first', "先にボイスチャンネルに参加してください。"))
            return

        if target_channel:
            try:
                new_player: LavalinkPlayer = await target_channel.connect(cls=LavalinkPlayer) # type: ignore
                new_player.text_channel = ctx.channel
                await ctx.send(MESSAGES.get('connected_to_vc', "🔊 **{channel}** に接続しました。").format(channel=target_channel.name))
            except Exception as e:
                logger.error(f"Error connecting to {target_channel.name}: {e}")
                await ctx.send(f"{target_channel.name} への接続に失敗しました。")


    @commands.command(name='disconnect', aliases=['leave', 'dc'], help="ボイスチャンネルから切断します。")
    async def disconnect_command(self, ctx: commands.Context):
        player = await self.get_player(ctx)

        if not player or not player.connected:
            await ctx.send(MESSAGES.get('not_connected', "ボイスチャンネルに接続していません。"))
            return

        # キューをクリアし、再生を停止
        player.queue.clear()
        if player.playing or player.paused:
            await player.stop()

        await player.disconnect()
        await ctx.send(MESSAGES.get('disconnected_from_vc', "👋 ボイスチャンネルから切断しました。"))

    @commands.command(name='play', aliases=['p'], help="曲を再生します。URLまたは検索クエリを指定。")
    async def play_command(self, ctx: commands.Context, *, query: str):
        player = await self.get_player(ctx, connect_if_none=True)
        if not player:
            return

        player.text_channel = ctx.channel # コマンド実行チャンネルを更新

        if not query:
            await ctx.send("再生する曲のタイトルまたはURLを指定してください。")
            return

        # URLかどうかの簡易判定 (yt-dlpに任せるため、厳密でなくても良い)
        is_url = re.match(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', query)

        search_query = query
        if not is_url:
            # YouTube Music や YouTube で検索する場合、プレフィックスを付与
            # Lavalink v4以降では ytsearch:, ytmsearch: などが推奨
            # yt-dlpを直接使う場合、プレフィックスは不要なことが多い
             if "nicovideo.jp" not in query.lower() and "nico.ms" not in query.lower():
                 search_query = f"ytsearch:{query}" # LavalinkがYouTubeで検索することを期待
             # ニコニコ動画のURLでない検索語句は、そのまま渡すか、ytsearch: をつけるかはLavalinkの設定による

        try:
            tracks: list[wavelink.Playable] | None = await wavelink.Playable.search(search_query)

            if not tracks:
                await ctx.send(MESSAGES.get('no_results', "😢 「{query}」の検索結果が見つかりませんでした。").format(query=query))
                return

            track_to_play: wavelink.Playable
            if isinstance(tracks, list): # Search result
                track_to_play = tracks[0]
            else: # Playlist or single track direct URL
                track_to_play = tracks # Should be a Playable or a Playlist

            if isinstance(track_to_play, wavelink.Playlist):
                # プレイリストの場合
                player.queue.extend(track_to_play.tracks)
                await ctx.send(f"🎶 プレイリスト **{track_to_play.name}** ({len(track_to_play.tracks)}曲) をキューに追加しました。")
                if not player.playing:
                    await player.play_next_track()

            elif isinstance(track_to_play, wavelink.Playable):
                # 単一の曲の場合
                if player.playing or not player.queue.is_empty:
                    player.queue.put(track_to_play)
                    await ctx.send(MESSAGES.get('added_to_queue', "📝 キューに追加しました: **{title}**").format(title=track_to_play.title))
                else:
                    await player.play(track_to_play)
                    await ctx.send(MESSAGES.get('now_playing', "🎶 再生中: **{title}**").format(title=track_to_play.title))
            else:
                await ctx.send("サポートされていないトラック形式です。")


        except wavelink.LavalinkException as e:
            logger.error(f"Play command Lavalink error: {e}")
            await ctx.send(MESSAGES.get('error_occurred', "エラーが発生しました: {error}").format(error=str(e)))
        except Exception as e:
            logger.error(f"An unexpected error occurred in play command: {e}", exc_info=True)
            await ctx.send(MESSAGES.get('error_occurred', "予期せぬエラーが発生しました。").format(error=str(e)))

    @commands.command(name='stop', help="再生を停止し、キューをクリアします。")
    async def stop_command(self, ctx: commands.Context):
        player = await self.get_player(ctx)
        if not player or (not player.playing and player.queue.is_empty): # 再生中でもなくキューも空
            await ctx.send(MESSAGES.get('nothing_playing', "現在再生中の曲はありません。"))
            return

        player.queue.clear()
        if player.playing or player.paused:
             await player.stop() # これで on_wavelink_track_end が発火するはず

        await ctx.send(MESSAGES.get('player_stopped', "⏹️ 再生を停止し、キューをクリアしました。"))

    @commands.command(name='skip', aliases=['s', 'next'], help="現在の曲をスキップします。")
    async def skip_command(self, ctx: commands.Context):
        player = await self.get_player(ctx)
        if not player or not player.current: # playing だとポーズ中やバッファリング中に反応しないことがある
            await ctx.send(MESSAGES.get('nothing_playing', "現在再生中の曲はありません。"))
            return

        if player.queue.is_empty and not player.current : # currentもなければ本当に何もない
             await ctx.send(MESSAGES.get('nothing_playing', "現在再生中の曲はありません。"))
             return

        await ctx.send(MESSAGES.get('skipped', "⏭️ スキップしました。"))
        await player.stop() # on_wavelink_track_end で次の曲が再生される

    @commands.command(name='queue', aliases=['q', 'list'], help="現在の再生キューを表示します。")
    async def queue_command(self, ctx: commands.Context):
        player = await self.get_player(ctx)
        if not player:
            await ctx.send(MESSAGES.get('bot_not_in_vc', "BOTがボイスチャンネルにいません。"))
            return

        if player.queue.is_empty and not player.current:
            await ctx.send(MESSAGES.get('queue_empty', "キューは空です。"))
            return

        embed = discord.Embed(title=MESSAGES.get('queue_title', "再生キュー"), color=discord.Color.blue())
        if player.current:
            duration_min_sec = f"{player.current.duration // 60000}:{ (player.current.duration // 1000) % 60:02d}"
            embed.add_field(name="再生中", value=f"[{player.current.title}]({player.current.uri}) ({duration_min_sec})", inline=False)

        if not player.queue.is_empty:
            queue_list_str = []
            for i, track in enumerate(list(player.queue)[:10]): # 最大10件表示
                duration_min_sec = f"{track.duration // 60000}:{ (track.duration // 1000) % 60:02d}"
                queue_list_str.append(f"{i+1}. [{track.title}]({track.uri}) ({duration_min_sec})")

            if queue_list_str:
                embed.add_field(name="待機中", value="\n".join(queue_list_str), inline=False)
            if len(player.queue) > 10:
                embed.set_footer(text=f"他 {len(player.queue) - 10} 曲...")
        elif not player.current: # currentもqueueもない場合
            embed.description = MESSAGES.get('queue_empty', "キューは空です。")


        if not embed.fields and not embed.description: # 何もセットされなかった場合
             await ctx.send(MESSAGES.get('queue_empty', "キューは空です。"))
        else:
            await ctx.send(embed=embed)

    @commands.command(name='nowplaying', aliases=['np', 'current'], help="現在再生中の曲を表示します。")
    async def nowplaying_command(self, ctx: commands.Context):
        player = await self.get_player(ctx)
        if not player or not player.current:
            await ctx.send(MESSAGES.get('nothing_playing', "現在再生中の曲はありません。"))
            return

        track = player.current
        embed = discord.Embed(
            title=MESSAGES.get('now_playing', "🎶 再生中: **{title}**").format(title=track.title),
            url=track.uri,
            color=discord.Color.green()
        )
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)
        elif track.source == "youtube": # ytimg.com からサムネイル取得 (artworkがない場合)
            embed.set_thumbnail(url=f"https://i.ytimg.com/vi/{track.identifier}/hqdefault.jpg")


        embed.add_field(name="アーティスト", value=track.author or "不明", inline=True)
        duration_min_sec = f"{track.duration // 60000}:{ (track.duration // 1000) % 60:02d}"
        embed.add_field(name="長さ", value=duration_min_sec, inline=True)

        position = player.position // 1000  # 秒単位
        duration = track.duration // 1000 # 秒単位
        if duration > 0:
            progress_percent = int((position / duration) * 100)
            bar_length = 20
            filled_length = int(bar_length * position // duration)
            bar = '─' * filled_length + '🔵' + '─' * (bar_length - filled_length)
            pos_min_sec = f"{position // 60}:{position % 60:02d}"
            embed.add_field(name="再生位置", value=f"`{bar}` [{pos_min_sec} / {duration_min_sec}] ({progress_percent}%)", inline=False)

        if track.requester: # discord.py v2.0
            requester: discord.User | discord.Member | None = ctx.guild.get_member(track.requester) # type: ignore
            if requester:
                embed.set_footer(text=f"リクエスト者: {requester.display_name}", icon_url=requester.display_avatar.url)

        await ctx.send(embed=embed)

    @commands.command(name='volume', aliases=['vol'], help="音量を設定 (0-1000)。引数なしで現在の音量を表示。")
    async def volume_command(self, ctx: commands.Context, volume: int | None = None):
        player = await self.get_player(ctx)
        if not player:
            await ctx.send(MESSAGES.get('bot_not_in_vc', "BOTがボイスチャンネルにいません。"))
            return

        if volume is None:
            await ctx.send(f"現在の音量: **{int(player.volume)}%**") # wavelink.Player.volume は float なのでintに変換
            return

        if not (0 <= volume <= 1000):
            await ctx.send(MESSAGES.get('invalid_volume', "無効なボリューム値です (0-1000)。"))
            return

        await player.set_volume(volume) # wavelink v2/v3
        # await player.filter(wavelink.Filter(volume=volume/100)) # wavelink v3+ Filterを使った方法
        await ctx.send(MESSAGES.get('volume_set', "🔊 ボリュームを **{volume}%** に設定しました。").format(volume=volume))

    @commands.command(name='clear', aliases=['clr'], help="再生キューをクリアします。")
    async def clear_command(self, ctx: commands.Context):
        player = await self.get_player(ctx)
        if not player:
            await ctx.send(MESSAGES.get('bot_not_in_vc', "BOTがボイスチャンネルにいません。"))
            return

        if player.queue.is_empty:
            await ctx.send("キューは既に空です。")
            return

        player.queue.clear()
        await ctx.send(MESSAGES.get('cleared_queue', "🗑️ キューをクリアしました。"))

    # --- コマンドエラーハンドリング ---
    @play_command.error
    @connect_command.error
    @disconnect_command.error
    @stop_command.error
    @skip_command.error
    @queue_command.error
    @nowplaying_command.error
    @volume_command.error
    @clear_command.error
    async def music_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"引数が不足しています: `{error.param.name}`\nコマンドのヘルプ: `{PREFIX}help {ctx.command.qualified_name}`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"引数の型が正しくありません。\nコマンドのヘルプ: `{PREFIX}help {ctx.command.qualified_name}`")
        elif isinstance(error, commands.CommandNotFound):
            # これはBotレベルで処理されるので、通常ここには来ない
            pass
        elif isinstance(error, commands.CheckFailure):
            # cog_check や other checks failed
            # メッセージはチェック側で送信済みの場合が多い
            logger.warning(f"CheckFailure for command {ctx.command.name} by {ctx.author}: {error}")
        elif isinstance(error, wavelink.LavalinkException):
            logger.error(f"LavalinkException in {ctx.command.name}: {error}")
            await ctx.send(MESSAGES.get('error_occurred', "エラーが発生しました: {error}").format(error=f"Lavalinkエラー: {error}"))
        else:
            logger.error(f"Unhandled error in command {ctx.command.name}: {error}", exc_info=True)
            await ctx.send(MESSAGES.get('error_occurred', "コマンド実行中に予期せぬエラーが発生しました。").format(error=str(error)[:1000]))


# --- Cogの登録とBotの実行 ---
async def main():
    async with bot:
        try:
            await bot.add_cog(MusicCog(bot))
            logger.info("MusicCogをロードしました。")
        except Exception as e:
            logger.critical(f"MusicCogのロードに失敗しました: {e}", exc_info=True)
            return

        try:
            await bot.start(TOKEN)
        except discord.LoginFailure:
            logger.critical("Discordへのログインに失敗しました。トークンが正しいか確認してください。")
        except discord.PrivilegedIntentsRequired:
            logger.critical("必要なIntents (Message Contentなど) が有効になっていません。Discord Developer Portalで設定してください。")
        except Exception as e:
            logger.critical(f"Botの起動中に予期せぬエラーが発生しました: {e}", exc_info=True)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Botを終了します...")
    finally:
        # asyncio.run(bot.close()) # bot.startが完了していれば不要
        pass