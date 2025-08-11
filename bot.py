"""
Standalone Discord Music Bot
単独で動作する音楽Bot
"""
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import logging
import json
import random
from typing import Dict, Optional, List, Union, Any
from enum import Enum, auto
import math
from pathlib import Path
import sys
import os
import shutil

# サービスモジュールのインポート設定
try:
    from services.ytdlp_wrapper import Track, extract as extract_audio_data, ensure_stream
except ImportError:
    try:
        from ytdlp_wrapper import Track, extract as extract_audio_data, ensure_stream
    except ImportError as e:
        print(f"[CRITICAL] ytdlp_wrapperのインポートに失敗しました。エラー: {e}")
        print("ytdlp_wrapper.py を同じディレクトリまたは services/ ディレクトリに配置してください。")
        sys.exit(1)

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# --- Helper & Enumクラス ---
def format_duration(duration_seconds: int) -> str:
    if duration_seconds is None or duration_seconds < 0:
        return "N/A"
    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    seconds = duration_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}" if hours > 0 else f"{minutes:02}:{seconds:02}"


class LoopMode(Enum):
    OFF = auto()
    ONE = auto()
    ALL = auto()


class GuildState:
    def __init__(self, bot: commands.Bot, guild_id: int, config: dict):
        self.bot = bot
        self.guild_id = guild_id
        self.voice_client: Optional[discord.VoiceClient] = None
        self.current_track: Optional[Track] = None
        self.queue: asyncio.Queue[Track] = asyncio.Queue()
        self.volume: float = config.get('music', {}).get('default_volume', 50) / 100.0
        self.loop_mode: LoopMode = LoopMode.OFF
        self.is_playing: bool = False
        self.is_paused: bool = False
        self.auto_leave_task: Optional[asyncio.Task] = None
        self.last_text_channel_id: Optional[int] = None

    def update_last_text_channel(self, channel_id: int):
        self.last_text_channel_id = channel_id

    async def clear_queue(self):
        self.queue = asyncio.Queue()


# --- 設定管理 ---
def create_config_example():
    """config-example.jsonを作成"""
    config_example = {
        "bot": {
            "token": "YOUR_BOT_TOKEN_HERE",
            "prefix": "/"
        },
        "music": {
            "ffmpeg_path": "ffmpeg",
            "ffmpeg_before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "ffmpeg_options": "-vn",
            "auto_leave_timeout": 10,
            "max_queue_size": 9000,
            "default_volume": 50,
            "messages": {
                "join_voice_channel_first": ":warning: You need to be in a voice channel first.",
                "bot_not_in_voice_channel": ":warning: The bot is not in a voice channel.",
                "already_connected": ":information_source: Already connected to a voice channel.",
                "not_connected_to_your_channel": ":warning: Not connected to your voice channel.",
                "must_be_in_same_channel": ":warning: You must be in the same voice channel as the bot.",

                "now_playing": ":notes: Now Playing: **{title}** (`{duration}`) - Requested by: **{requester_display_name}**",
                "added_to_queue": ":ballot_box_with_check: Added to queue: **{title}** (`{duration}`) - Requested by: **{requester_display_name}**",
                "added_playlist_to_queue": ":ballot_box_with_check: Added **{count}** songs from the playlist to the queue.",

                "queue_empty": ":page_facing_up: The queue is empty.",
                "queue_ended": ":information_source: Playback queue has ended.",
                "queue_title": "Queue ({count} tracks)",

                "skipped_song": ":track_next: Skipped: **{title}**",
                "nothing_to_skip": ":information_source: There is nothing to skip.",
                "stopped_playback": ":stop_button: Playback stopped and queue cleared.",
                "playback_paused": ":pause_button: Playback paused.",
                "playback_resumed": ":arrow_forward: Playback resumed.",

                "volume_set": ":loud_sound: Volume set to **{volume}%**.",
                "invalid_volume": ":warning: Volume must be between 0 and 200.",
                "queue_shuffled": ":twisted_rightwards_arrows: Queue shuffled.",
                "now_playing_nothing": ":information_source: Nothing is currently playing.",
                "queue_cleared": ":wastebasket: Queue cleared.",

                "loop_off": ":arrow_right_hook: Loop turned off.",
                "loop_one": ":repeat_one: Looping current song.",
                "loop_all": ":repeat: Looping entire queue.",
                "invalid_loop_option": ":warning: Invalid loop option. Please specify `off`, `one`, or `all`.",

                "song_removed": ":x: Removed from queue: **{title}**",
                "invalid_queue_number": ":warning: Invalid queue number. Check with `{prefix}queue`.",

                "error_playing": ":x: An error occurred during playback: `{error}`",
                "error_playing_stream": ":x: Failed to get stream URL or prepare for playback: `{error}`",
                "error_fetching_song": ":x: Failed to fetch song information. Check the URL/search query or try another song. Error: `{error}`",

                "leaving_voice_channel": ":wave: Leaving voice channel.",
                "auto_leave_empty_channel_countdown": ":timer: Auto-leaving in {timeout} seconds as the channel is empty...",
                "auto_leave_countdown_cancelled": ":white_check_mark: Auto-leave countdown cancelled.",
                "auto_left_empty_channel": ":door: Left the voice channel because it became empty.",

                "search_no_results": ":mag: No results found for \"{query}\".",
                "max_queue_size_reached": ":no_entry_sign: Max queue size ({max_size} songs) reached. Cannot add more."
            }
        },
        "niconico": {
            "email": "",
            "password": "",
            "comment": "ニコニコ動画のログイン情報（オプション）"
        }
    }

    with open("config-example.json", "w", encoding="utf-8") as f:
        json.dump(config_example, f, ensure_ascii=False, indent=2)

    logger.info("config-example.json を作成しました。")


def load_config():
    """設定ファイルを読み込む"""
    config_path = Path("config.json")
    config_example_path = Path("config-example.json")

    # config.jsonが存在しない場合
    if not config_path.exists():
        # config-example.jsonも存在しない場合は作成
        if not config_example_path.exists():
            create_config_example()
            print("\n[初回起動] config-example.json を作成しました。")

        # config-example.jsonをconfig.jsonにコピー
        try:
            shutil.copy2(config_example_path, config_path)
            print("[初回起動] config-example.json を config.json にコピーしました。")
            print("[重要] config.json を編集してBotトークンを設定してください。")
            print("設定後、再度このプログラムを実行してください。")
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] 設定ファイルのコピーに失敗しました: {e}")
            sys.exit(1)

    # config.jsonを読み込む
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # トークンが設定されているか確認
        if config.get("bot", {}).get("token") == "YOUR_BOT_TOKEN_HERE":
            print("\n[ERROR] config.json にBotトークンが設定されていません。")
            print("config.json を編集してBotトークンを設定してください。")
            sys.exit(1)

        return config
    except json.JSONDecodeError as e:
        print(f"[ERROR] config.json の読み込みに失敗しました (JSON形式エラー): {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] config.json の読み込みに失敗しました: {e}")
        sys.exit(1)


# --- MusicBot本体 ---
class MusicBot(commands.Bot):
    def __init__(self, config: dict):
        # Botの初期設定
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        intents.members = True

        super().__init__(
            command_prefix=config.get('bot', {}).get('prefix', '/'),
            intents=intents,
            help_command=None  # デフォルトのヘルプコマンドを無効化
        )

        self.config = config
        self.music_config = config.get('music', {})
        self.guild_states: Dict[int, GuildState] = {}
        self.ffmpeg_path = self.music_config.get('ffmpeg_path', 'ffmpeg')
        self.ffmpeg_before_options = self.music_config.get('ffmpeg_before_options',
                                                           "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5")
        self.ffmpeg_options = self.music_config.get('ffmpeg_options', "-vn")
        self.auto_leave_timeout = self.music_config.get('auto_leave_timeout', 10)
        self.max_queue_size = self.music_config.get('max_queue_size', 9000)

    def _get_guild_state(self, guild_id: int) -> GuildState:
        if guild_id not in self.guild_states:
            self.guild_states[guild_id] = GuildState(self, guild_id, self.config)
        return self.guild_states[guild_id]

    def _get_message(self, key: str, **kwargs) -> str:
        template = self.music_config.get('messages', {}).get(key, f"Message key '{key}' not found.")
        kwargs.setdefault('prefix', '/')
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"メッセージ '{key}' の表示エラー: {e}"

    async def _send_response(self, interaction: discord.Interaction, message_key: str, ephemeral: bool = False,
                             **kwargs):
        content = self._get_message(message_key, **kwargs)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(content, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(content, ephemeral=ephemeral)
        except discord.errors.InteractionResponded:
            try:
                await interaction.followup.send(content, ephemeral=ephemeral)
            except Exception as e:
                logger.error(f"Followup送信エラー: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"応答送信エラー: {e}", exc_info=True)

    async def _send_background_message(self, channel_id: int, message_key: str, **kwargs):
        channel = self.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            content = self._get_message(message_key, **kwargs)
            try:
                await channel.send(content)
            except discord.Forbidden:
                logger.warning(f"Ch:{channel_id} へのBGメッセージ送信権限なし。")
            except Exception as e:
                logger.error(f"BGメッセージ送信エラー: {e}", exc_info=True)

    async def _ensure_voice(self, interaction: discord.Interaction, connect_if_not_in: bool = True) -> Optional[
        discord.VoiceClient]:
        state = self._get_guild_state(interaction.guild.id)
        state.update_last_text_channel(interaction.channel.id)
        user_voice = interaction.user.voice

        if not user_voice or not user_voice.channel:
            await self._send_response(interaction, "join_voice_channel_first", ephemeral=True)
            return None

        vc = state.voice_client
        if not vc or not vc.is_connected():
            if connect_if_not_in:
                try:
                    state.voice_client = await user_voice.channel.connect(timeout=15.0, reconnect=True)
                    await interaction.guild.me.edit(deafen=True)
                    return state.voice_client
                except Exception as e:
                    await self._send_response(interaction, "error_playing", ephemeral=True,
                                              error=f"VC接続失敗: {type(e).__name__}")
                    return None
            else:
                await self._send_response(interaction, "bot_not_in_voice_channel", ephemeral=True)
                return None

        if vc.channel != user_voice.channel:
            await self._send_response(interaction, "must_be_in_same_channel", ephemeral=True)
            return None

        return vc

    async def _play_next_song(self, guild_id: int):
        state = self._get_guild_state(guild_id)
        if state.auto_leave_task and not state.auto_leave_task.done():
            state.auto_leave_task.cancel()
        if state.is_paused or (state.voice_client and state.voice_client.is_playing()):
            return

        track_to_play: Optional[Track] = None
        if state.loop_mode == LoopMode.ONE and state.current_track:
            track_to_play = state.current_track
        elif not state.queue.empty():
            track_to_play = await state.queue.get()
            state.queue.task_done()

        if not track_to_play:
            state.current_track, state.is_playing = None, False
            if state.last_text_channel_id:
                await self._send_background_message(state.last_text_channel_id, "queue_ended")
            self._schedule_auto_leave(guild_id)
            return

        state.current_track, state.is_playing, state.is_paused = track_to_play, True, False

        try:
            if not track_to_play.stream_url or not Path(track_to_play.stream_url).is_file():
                updated_track = await ensure_stream(track_to_play)
                if updated_track and updated_track.stream_url:
                    track_to_play.stream_url = updated_track.stream_url
                else:
                    raise RuntimeError("ストリームURLの取得/更新に失敗しました。")

            source = discord.FFmpegPCMAudio(
                track_to_play.stream_url,
                executable=self.ffmpeg_path,
                before_options=self.ffmpeg_before_options,
                options=self.ffmpeg_options
            )
            transformed_source = discord.PCMVolumeTransformer(source, volume=state.volume)
            state.voice_client.play(transformed_source, after=lambda e: self._song_finished_callback(e, guild_id))

            logger.info(f"ギルドID {guild_id}: 再生開始 - {track_to_play.title}")

            if state.last_text_channel_id and track_to_play.requester_id:
                try:
                    requester = self.get_user(track_to_play.requester_id) or await self.fetch_user(
                        track_to_play.requester_id)
                except discord.NotFound:
                    requester = None
                await self._send_background_message(
                    state.last_text_channel_id, "now_playing",
                    title=track_to_play.title,
                    duration=format_duration(track_to_play.duration),
                    requester_display_name=requester.display_name if requester else "不明"
                )
        except Exception as e:
            logger.error(f"再生準備中エラー: {e}", exc_info=True)
            if state.last_text_channel_id:
                await self._send_background_message(state.last_text_channel_id, "error_playing", error=str(e))
            if state.loop_mode == LoopMode.ALL and track_to_play:
                await state.queue.put(track_to_play)
            state.current_track = None
            asyncio.create_task(self._play_next_song(guild_id))

    def _song_finished_callback(self, error: Optional[Exception], guild_id: int):
        state = self._get_guild_state(guild_id)
        finished_track, state.is_playing, state.current_track = state.current_track, False, None

        if error:
            logger.error(f"再生エラー (after): {error}")
            if state.last_text_channel_id:
                asyncio.run_coroutine_threadsafe(
                    self._send_background_message(state.last_text_channel_id, "error_playing", error=str(error)),
                    self.loop
                )

        if finished_track and state.loop_mode == LoopMode.ALL:
            asyncio.run_coroutine_threadsafe(state.queue.put(finished_track), self.loop)

        asyncio.run_coroutine_threadsafe(self._play_next_song(guild_id), self.loop)

    def _schedule_auto_leave(self, guild_id: int):
        state = self._get_guild_state(guild_id)
        if state.auto_leave_task and not state.auto_leave_task.done():
            state.auto_leave_task.cancel()
        if state.voice_client and state.voice_client.is_connected():
            state.auto_leave_task = asyncio.create_task(self._auto_leave_coroutine(guild_id))

    async def _auto_leave_coroutine(self, guild_id: int):
        await asyncio.sleep(self.auto_leave_timeout)
        state = self._get_guild_state(guild_id)
        if state.voice_client and state.voice_client.is_connected():
            if not [m for m in state.voice_client.channel.members if not m.bot]:
                if state.last_text_channel_id:
                    await self._send_background_message(state.last_text_channel_id, "auto_left_empty_channel")
                await state.voice_client.disconnect()

    async def _cleanup_guild_state(self, guild_id: int):
        if guild_id in self.guild_states:
            state = self.guild_states[guild_id]
            if state.voice_client and state.voice_client.is_connected():
                state.voice_client.stop()
            if state.auto_leave_task and not state.auto_leave_task.done():
                state.auto_leave_task.cancel()
            del self.guild_states[guild_id]
            logger.info(f"ギルドID {guild_id}: GuildStateクリーンアップ完了。")

    async def on_ready(self):
        logger.info(f"{self.user.name} が正常に起動しました！")
        logger.info(f"接続サーバー数: {len(self.guilds)}")
        logger.info("コマンドを同期中...")
        try:
            synced = await self.tree.sync()
            logger.info(f"{len(synced)}個のコマンドが同期されました。")
        except Exception as e:
            logger.error(f"コマンド同期エラー: {e}")

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        if member.id == self.user.id and before.channel and not after.channel:
            await self._cleanup_guild_state(member.guild.id)
            return

        guild_id = member.guild.id
        if guild_id not in self.guild_states:
            return

        state = self._get_guild_state(guild_id)
        if not state.voice_client or not state.voice_client.is_connected():
            return

        current_vc_channel = state.voice_client.channel
        if before.channel != current_vc_channel and after.channel != current_vc_channel:
            return

        human_members_in_vc = [m for m in current_vc_channel.members if not m.bot]
        if not human_members_in_vc:
            if not state.auto_leave_task or state.auto_leave_task.done():
                self._schedule_auto_leave(guild_id)
        elif state.auto_leave_task and not state.auto_leave_task.done():
            state.auto_leave_task.cancel()


# Botインスタンスを作成（後で初期化）
bot: Optional[MusicBot] = None


# --- スラッシュコマンド定義 ---
def setup_commands(bot: MusicBot):
    """Botインスタンスにコマンドを登録"""

    @bot.tree.command(name="play", description="曲を再生またはキューに追加します。")
    @app_commands.describe(query="再生したい曲のタイトル、またはURL")
    async def play_slash(interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        state = bot._get_guild_state(interaction.guild.id)
        vc = await bot._ensure_voice(interaction, connect_if_not_in=True)
        if not vc: return

        if state.queue.qsize() >= bot.max_queue_size:
            await bot._send_response(interaction, "max_queue_size_reached", ephemeral=True, max_size=bot.max_queue_size)
            return

        try:
            extracted_media = await extract_audio_data(query, shuffle_playlist=False)
        except Exception as e:
            await bot._send_response(interaction, "error_fetching_song", ephemeral=True, error=str(e))
            return

        if not extracted_media:
            await bot._send_response(interaction, "search_no_results", ephemeral=True, query=query)
            return

        tracks = extracted_media if isinstance(extracted_media, list) else [extracted_media]
        added_count, first_track = 0, None

        for track in tracks:
            if state.queue.qsize() < bot.max_queue_size:
                track.requester_id = interaction.user.id
                await state.queue.put(track)
                if added_count == 0:
                    first_track = track
                added_count += 1
            else:
                await bot._send_response(interaction, "max_queue_size_reached", ephemeral=True,
                                         max_size=bot.max_queue_size)
                break

        if added_count > 1:
            await bot._send_response(interaction, "added_playlist_to_queue", count=added_count)
        elif added_count == 1 and first_track:
            await bot._send_response(interaction, "added_to_queue",
                                     title=first_track.title,
                                     duration=format_duration(first_track.duration),
                                     requester_display_name=interaction.user.display_name)
        if not state.is_playing:
            await bot._play_next_song(interaction.guild.id)

    @bot.tree.command(name="pause", description="再生を一時停止します。")
    async def pause_slash(interaction: discord.Interaction):
        state = bot._get_guild_state(interaction.guild.id)
        vc = await bot._ensure_voice(interaction, connect_if_not_in=False)
        if not vc: return

        if not state.is_playing:
            await bot._send_response(interaction, "error_playing", ephemeral=True, error="再生中ではありません。")
            return
        if state.is_paused:
            await bot._send_response(interaction, "error_playing", ephemeral=True, error="既に一時停止中です。")
            return

        state.voice_client.pause()
        state.is_paused = True
        await bot._send_response(interaction, "playback_paused")

    @bot.tree.command(name="resume", description="一時停止中の再生を再開します。")
    async def resume_slash(interaction: discord.Interaction):
        state = bot._get_guild_state(interaction.guild.id)
        vc = await bot._ensure_voice(interaction, connect_if_not_in=False)
        if not vc: return

        if not state.is_paused:
            await bot._send_response(interaction, "error_playing", ephemeral=True, error="一時停止中ではありません。")
            return

        state.voice_client.resume()
        state.is_paused = False
        await bot._send_response(interaction, "playback_resumed")

    @bot.tree.command(name="skip", description="再生中の曲をスキップします。")
    async def skip_slash(interaction: discord.Interaction):
        state = bot._get_guild_state(interaction.guild.id)
        await interaction.response.defer()
        vc = await bot._ensure_voice(interaction, connect_if_not_in=False)

        if not vc or not state.current_track:
            await bot._send_response(interaction, "nothing_to_skip", ephemeral=True)
            return

        await bot._send_response(interaction, "skipped_song", title=state.current_track.title)
        state.voice_client.stop()

    @bot.tree.command(name="stop", description="再生を停止し、キューをクリアします。")
    async def stop_slash(interaction: discord.Interaction):
        state = bot._get_guild_state(interaction.guild.id)
        await interaction.response.defer()
        vc = await bot._ensure_voice(interaction, connect_if_not_in=False)
        if not vc: return

        state.loop_mode = LoopMode.OFF
        await state.clear_queue()
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop()
        state.is_playing, state.is_paused, state.current_track = False, False, None
        await bot._send_response(interaction, "stopped_playback")

    @bot.tree.command(name="queue", description="現在の再生キューを表示します。")
    async def queue_slash(interaction: discord.Interaction):
        state = bot._get_guild_state(interaction.guild.id)
        state.update_last_text_channel(interaction.channel.id)

        if state.queue.empty() and not state.current_track:
            await interaction.response.send_message(bot._get_message("queue_empty"), ephemeral=True)
            return

        items_per_page = 10
        queue_list = list(state.queue._queue)
        total_items = len(queue_list)
        total_pages = math.ceil(len(queue_list) / items_per_page) if len(queue_list) > 0 else 1

        async def get_page_embed(page_num: int):
            embed = discord.Embed(
                title=bot._get_message("queue_title", count=total_items + (1 if state.current_track else 0)),
                color=discord.Color.blue()
            )
            lines = []

            if page_num == 1 and state.current_track:
                track = state.current_track
                try:
                    requester = interaction.guild.get_member(track.requester_id) or await bot.fetch_user(
                        track.requester_id)
                except:
                    requester = None
                lines.append(
                    f"**{'▶️' if state.is_playing else '⏸️'} {track.title}** (`{format_duration(track.duration)}`) - Req: **{requester.display_name if requester else '不明'}**\n")

            start = (page_num - 1) * items_per_page
            end = start + items_per_page

            for i, track in enumerate(queue_list[start:end], start=start + 1):
                try:
                    requester = interaction.guild.get_member(track.requester_id) or await bot.fetch_user(
                        track.requester_id)
                except:
                    requester = None
                lines.append(
                    f"`{i}.` **{track.title}** (`{format_duration(track.duration)}`) - Req: **{requester.display_name if requester else '不明'}**")

            embed.description = "\n".join(lines) if lines else "このページには曲がありません。"
            if total_pages > 1:
                embed.set_footer(text=f"ページ {page_num}/{total_pages}")
            return embed

        current_page = 1
        await interaction.response.send_message(embed=await get_page_embed(current_page))
        message = await interaction.original_response()

        if total_pages <= 1:
            return

        controls = ["⏪", "◀️", "▶️", "⏩", "⏹️"]
        for control in controls:
            await message.add_reaction(control)

        def check(reaction, user):
            return user == interaction.user and str(reaction.emoji) in controls and reaction.message.id == message.id

        while True:
            try:
                reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)
                new_page = current_page

                if str(reaction.emoji) == "⏪":
                    new_page = 1
                elif str(reaction.emoji) == "◀️":
                    new_page = max(1, current_page - 1)
                elif str(reaction.emoji) == "▶️":
                    new_page = min(total_pages, current_page + 1)
                elif str(reaction.emoji) == "⏩":
                    new_page = total_pages
                elif str(reaction.emoji) == "⏹️":
                    await message.clear_reactions()
                    return

                if new_page != current_page:
                    current_page = new_page
                    await message.edit(embed=await get_page_embed(current_page))

                try:
                    await message.remove_reaction(reaction, user)
                except discord.Forbidden:
                    pass
            except asyncio.TimeoutError:
                try:
                    await message.clear_reactions()
                except:
                    pass
                break

    @bot.tree.command(name="nowplaying", description="現在再生中の曲の情報を表示します。")
    async def nowplaying_slash(interaction: discord.Interaction):
        state = bot._get_guild_state(interaction.guild.id)
        if not state.current_track:
            await interaction.response.send_message(bot._get_message("now_playing_nothing"), ephemeral=True)
            return

        track = state.current_track
        status_icon = "▶️" if state.is_playing else ("⏸️" if state.is_paused else "⏹️")

        try:
            requester = interaction.guild.get_member(track.requester_id) or await bot.fetch_user(track.requester_id)
        except:
            requester = None

        embed = discord.Embed(
            title=f"{status_icon} {track.title}",
            url=track.url,
            description=f"長さ: `{format_duration(track.duration)}`\nリクエスト: **{requester.display_name if requester else '不明'}**\nURL: {track.url}\nループモード: `{state.loop_mode.name.lower()}`",
            color=discord.Color.green() if state.is_playing else (
                discord.Color.orange() if state.is_paused else discord.Color.light_grey())
        )
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="shuffle", description="再生キューをシャッフルします。")
    async def shuffle_slash(interaction: discord.Interaction):
        state = bot._get_guild_state(interaction.guild.id)
        vc = await bot._ensure_voice(interaction, connect_if_not_in=False)
        if not vc: return

        if state.queue.qsize() < 2:
            await bot._send_response(interaction, "error_playing", ephemeral=True,
                                     error="シャッフルするにはキューに2曲以上必要です。")
            return

        queue_list = list(state.queue._queue)
        random.shuffle(queue_list)
        state.queue = asyncio.Queue()
        for item in queue_list:
            await state.queue.put(item)
        await bot._send_response(interaction, "queue_shuffled")

    @bot.tree.command(name="clear", description="再生キューを空にします（再生中の曲は停止しません）。")
    async def clear_slash(interaction: discord.Interaction):
        state = bot._get_guild_state(interaction.guild.id)
        await bot._ensure_voice(interaction, connect_if_not_in=False)
        await state.clear_queue()
        await bot._send_response(interaction, "queue_cleared")

    @bot.tree.command(name="remove", description="キューから指定した番号の曲を削除します。")
    @app_commands.describe(index="削除したい曲のキュー番号")
    async def remove_slash(interaction: discord.Interaction, index: app_commands.Range[int, 1, None]):
        state = bot._get_guild_state(interaction.guild.id)
        if state.queue.empty():
            await interaction.response.send_message(bot._get_message("queue_empty"), ephemeral=True)
            return

        actual_index = index - 1
        if not (0 <= actual_index < state.queue.qsize()):
            await bot._send_response(interaction, "invalid_queue_number", ephemeral=True)
            return

        queue_list = list(state.queue._queue)
        removed_track = queue_list.pop(actual_index)
        state.queue = asyncio.Queue()
        for item in queue_list:
            await state.queue.put(item)
        await bot._send_response(interaction, "song_removed", title=removed_track.title)

    @bot.tree.command(name="volume", description="音量を変更します (0-200)。")
    @app_commands.describe(level="設定したい音量レベル (0-200)")
    async def volume_slash(interaction: discord.Interaction, level: app_commands.Range[int, 0, 200]):
        state = bot._get_guild_state(interaction.guild.id)
        state.volume = level / 100.0
        if state.voice_client and state.voice_client.source:
            state.voice_client.source.volume = state.volume
        await bot._send_response(interaction, "volume_set", volume=level)

    @bot.tree.command(name="loop", description="ループ再生モードを設定します。")
    @app_commands.describe(mode="ループのモードを選択してください。")
    @app_commands.choices(mode=[
        app_commands.Choice(name="オフ (Loop Off)", value="off"),
        app_commands.Choice(name="現在の曲をループ (Loop One)", value="one"),
        app_commands.Choice(name="キュー全体をループ (Loop All)", value="all")
    ])
    async def loop_slash(interaction: discord.Interaction, mode: app_commands.Choice[str]):
        state = bot._get_guild_state(interaction.guild.id)
        await interaction.response.defer()

        if mode.value == "off":
            state.loop_mode = LoopMode.OFF
        elif mode.value == "one":
            state.loop_mode = LoopMode.ONE
        elif mode.value == "all":
            state.loop_mode = LoopMode.ALL

        await bot._send_response(interaction, f"loop_{mode.value}")

    @bot.tree.command(name="join", description="ボットをあなたのいるボイスチャンネルに接続します。")
    async def join_slash(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = await bot._ensure_voice(interaction, connect_if_not_in=True)
        if vc:
            await interaction.followup.send(bot._get_message("already_connected"), ephemeral=True)

    @bot.tree.command(name="leave", description="ボットをボイスチャンネルから切断します。")
    async def leave_slash(interaction: discord.Interaction):
        state = bot._get_guild_state(interaction.guild.id)
        await interaction.response.defer()

        if not state.voice_client or not state.voice_client.is_connected():
            await bot._send_response(interaction, "bot_not_in_voice_channel", ephemeral=True)
            return

        await bot._send_response(interaction, "leaving_voice_channel")
        await state.voice_client.disconnect()

    @bot.tree.command(name="music_help", description="音楽機能のコマンド一覧と使い方を表示します。")
    async def music_help_slash(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        embed = discord.Embed(
            title="🎵 音楽機能 ヘルプ / Music Feature Help",
            description="音楽再生に関するコマンドの一覧です。\nAll commands start with a slash (`/`).",
            color=discord.Color.from_rgb(79, 194, 255)
        )

        command_info = {
            "▶️ 再生コントロール / Playback Control": [
                {"name": "play", "args": "<song name or URL>", "desc_ja": "曲を再生/キュー追加",
                 "desc_en": "Play/add a song to queue"},
                {"name": "pause", "args": "", "desc_ja": "一時停止", "desc_en": "Pause playback"},
                {"name": "resume", "args": "", "desc_ja": "再生再開", "desc_en": "Resume playback"},
                {"name": "stop", "args": "", "desc_ja": "再生停止＆キュークリア",
                 "desc_en": "Stop playback & clear queue"},
                {"name": "skip", "args": "", "desc_ja": "現在の曲をスキップ", "desc_en": "Skip the current song"},
                {"name": "volume", "args": "<level 0-200>", "desc_ja": "音量変更", "desc_en": "Change volume"},
            ],
            "💿 キュー管理 / Queue Management": [
                {"name": "queue", "args": "", "desc_ja": "キュー表示", "desc_en": "Display the queue"},
                {"name": "nowplaying", "args": "", "desc_ja": "現在再生中の曲", "desc_en": "Show current song"},
                {"name": "shuffle", "args": "", "desc_ja": "キューをシャッフル", "desc_en": "Shuffle the queue"},
                {"name": "clear", "args": "", "desc_ja": "キューをクリア", "desc_en": "Clear the queue"},
                {"name": "remove", "args": "<queue number>", "desc_ja": "指定番号の曲を削除",
                 "desc_en": "Remove a song by number"},
                {"name": "loop", "args": "<off|one|all>", "desc_ja": "ループモード設定", "desc_en": "Set loop mode"},
            ],
            "🔊 ボイスチャンネル / Voice Channel": [
                {"name": "join", "args": "", "desc_ja": "VCに接続", "desc_en": "Join voice channel"},
                {"name": "leave", "args": "", "desc_ja": "VCから切断", "desc_en": "Leave voice channel"},
            ]
        }

        for category, commands_in_category in command_info.items():
            field_value = ""
            for cmd_info in commands_in_category:
                usage = f"`/{cmd_info['name']}{(' ' + cmd_info['args']) if cmd_info['args'] else ''}`"
                field_value += f"{usage:<25} | {cmd_info['desc_ja']} / {cmd_info['desc_en']}\n"
            if field_value:
                embed.add_field(name=f"**{category}**", value=field_value, inline=False)

        embed.set_footer(text="<> は引数を表します / <> denotes an argument.")
        await interaction.followup.send(embed=embed)


# --- メイン実行 ---
async def main():
    """メイン実行関数"""
    # 設定ファイルを読み込む
    config = load_config()

    # Botインスタンスを作成
    bot = MusicBot(config)

    # コマンドを設定
    setup_commands(bot)

    # Botを起動
    token = config.get("bot", {}).get("token")
    await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Botを停止しています...")
    except Exception as e:
        logger.error(f"予期しないエラー: {e}", exc_info=True)