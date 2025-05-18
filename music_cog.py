import discord
from discord.ext import commands
import wavelink
from typing import cast, Optional, Union
import asyncio


# main.py から get_message をインポート (または MusicCog 内に同様のヘルパーを定義)
# この例では、bot インスタンス経由でアクセスできると仮定するか、
# MusicCog の __init__ で bot.get_message のような形で参照を持たせます。
# もしくは、main.py の get_message を MusicCog でも使えるようにします。
# 簡単なのは MusicCog 内で bot.config_data['messages'] を直接参照することです。

class MusicCog(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # config_data と messages へのショートカット
        self.config = bot.config_data
        self.messages_config = self.config['messages']['music']  # 音楽関連メッセージに限定
        self.general_messages_config = self.config['messages']  # 一般メッセージ用

        self.bot.loop.create_task(self.connect_nodes())

    # メッセージ取得ヘルパーメソッド (Cog内)
    def _(self, key: str, section: str = 'music', **kwargs) -> str:
        try:
            message_store = self.config['messages']
            if section:  # 'music.some_key' のようにセクション指定があれば
                message_store = message_store.get(section, {})

            # 'a.b.c' のようなネストしたキーに対応
            actual_key_parts = key.split('.')
            msg_template = message_store
            for part in actual_key_parts:
                if isinstance(msg_template, dict):
                    msg_template = msg_template.get(part)
                else:  # 途中で辞書でなくなった場合
                    msg_template = None
                    break

            if msg_template is None:
                raise KeyError(f"Key part not found leading to '{key}' in section '{section}'")

            if 'prefix' not in kwargs and 'prefix' in self.config['discord']:  # グローバルprefixをkwargsに追加
                kwargs['prefix'] = self.config['discord']['prefix']

            return str(msg_template).format(**kwargs)  # str()で囲むのは稀に数値などが来た場合のため
        except KeyError:
            print(f"Warning: Message key '{key}' (section: '{section}') not found in config!")
            return f"MSG_KEY_ERR: {section}.{key}"
        except Exception as e:
            print(f"Error formatting message for key '{key}' (section: '{section}'): {e}")
            return f"MSG_FMT_ERR: {section}.{key}"

    async def connect_nodes(self):
        await self.bot.wait_until_ready()
        node_conf = self.config['lavalink']
        node = wavelink.Node(
            uri=f"http://{node_conf['host']}:{node_conf['port']}",
            password=node_conf['password'],
            identifier=node_conf.get('identifier', self.bot.user.name)
        )
        await wavelink.Pool.connect(client=self.bot, nodes=[node])

    @wavelink.เมื่อ(wavelink.TrackStartEvent)
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEvent):
        player: wavelink.Player = payload.player
        original_track = payload.original or payload.track

        if not player or not player.guild:
            return

        embed = discord.Embed(
            title=self._("now_playing_embed_title"),
            description=f"[{original_track.title}]({original_track.uri})",
            color=discord.Color.green()
        )
        if original_track.artwork:
            embed.set_thumbnail(url=original_track.artwork)

        requester = getattr(original_track, 'requester', getattr(player.current, 'requester', None))
        if requester:
            embed.set_footer(
                text=self._("requested_by_footer", requester_name=requester.display_name),
                icon_url=requester.display_avatar.url
            )

        text_channel_id = getattr(player, 'text_channel_id', None)
        if text_channel_id:
            text_channel = self.bot.get_channel(text_channel_id)
            if text_channel:
                try:
                    await text_channel.send(embed=embed)
                except discord.HTTPException:
                    pass

    @wavelink.เมื่อ(wavelink.TrackEndEvent)
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEvent):
        player: wavelink.Player = payload.player
        reason = payload.reason

        if reason == wavelink.TrackEndReason.REPLACED:
            return

        if player.queue.mode == wavelink.QueueMode.loop_track and payload.track:
            await player.queue.put_at_front(payload.track)

        if not player.queue.is_empty:
            try:
                next_track = await player.queue.get_wait()
                await player.play(next_track)
            except wavelink.QueueEmpty:
                pass
            except Exception as e:
                print(f"Error playing next track: {e}")  # これはログ用
        elif player.queue.mode != wavelink.QueueMode.normal:
            pass  # ループモードなら何もしない
        else:
            text_channel_id = getattr(player, 'text_channel_id', None)
            if text_channel_id:
                text_channel = self.bot.get_channel(text_channel_id)
                if text_channel:
                    try:
                        await text_channel.send(self._("queue_ended"))
                    except discord.HTTPException:
                        pass

    @wavelink.เมื่อ(wavelink.NodeReadyEvent)
    async def on_node_ready(self, payload: wavelink.NodeReadyEvent):
        print(self._("lavalink_node_ready", identifier=payload.node.identifier))

    async def cog_check(self, ctx: commands.Context) -> bool:
        if not ctx.guild:
            # main.py の on_command_error で処理されるか、ここで直接送るか
            # ここで送る場合:
            await ctx.send(self.bot.config_data['messages']['error_check_failure_guild_only'].format(
                prefix=self.config['discord']['prefix']))
            return False
        return True

    async def ensure_voice(self, ctx: commands.Context, should_connect: bool = True) -> Optional[wavelink.Player]:
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(self._("voice_channel_needed"))
            return None

        player = cast(wavelink.Player, ctx.voice_client)

        if not player:
            if should_connect:
                try:
                    player = await ctx.author.voice.channel.connect(cls=wavelink.Player, self_deaf=True)
                    await ctx.send(self._("connected_to_vc", channel_mention=ctx.author.voice.channel.mention))
                except discord.ClientException:
                    await ctx.send(self._("fail_connect_vc"))
                    return None
                except asyncio.TimeoutError:
                    await ctx.send(self._("timeout_connect_vc"))
                    return None
            else:
                return None
        elif player.channel != ctx.author.voice.channel:
            # このメッセージはconfigにないので追加を検討 or 固定
            await ctx.send("BOTと同じボイスチャンネルに参加してください。")
            return None

        setattr(player, 'text_channel_id', ctx.channel.id)
        return player

    @commands.hybrid_command(name="connect", aliases=['join'], description="BOTをボイスチャンネルに接続します。")
    async def connect_command(self, ctx: commands.Context, *, channel: Optional[discord.VoiceChannel] = None):
        if not channel:
            if not ctx.author.voice or not ctx.author.voice.channel:
                return await ctx.send(self._("voice_channel_needed"))  # 修正: configから取得
            channel = ctx.author.voice.channel

        player = cast(wavelink.Player, ctx.voice_client)
        if player and player.is_connected():
            if player.channel == channel:
                return await ctx.send(self._("already_connected", channel_mention=channel.mention))
            else:
                await player.move_to(channel)
                setattr(player, 'text_channel_id', ctx.channel.id)
                return await ctx.send(self._("moved_to_vc", channel_mention=channel.mention))
        try:
            new_player = await channel.connect(cls=wavelink.Player, self_deaf=True)
            setattr(new_player, 'text_channel_id', ctx.channel.id)
            await ctx.send(self._("connected_to_vc", channel_mention=channel.mention))
        except Exception as e:
            await ctx.send(self._("fail_connect_vc") + f": {e}")  # エラー詳細を追加

    @commands.hybrid_command(name="play", aliases=['p'], description="曲を再生します。曲名またはURLを指定してください。")
    async def play_command(self, ctx: commands.Context, *, query: str):
        player = await self.ensure_voice(ctx)
        if not player:
            return

        try:
            tracks: Union[
                wavelink.Searchable, wavelink.Playlist, list[wavelink.Playable]] = await wavelink.Playable.search(query,
                                                                                                                  source=wavelink.TrackSource.YouTube)
        except wavelink.LavalinkLoadException as e:
            return await ctx.send(self._("loading_failed", error=str(e)))
        except Exception as e:
            return await ctx.send(self._("search_error", error=str(e)))

        if not tracks:
            return await ctx.send(self._("no_song_found", query=query))

        def add_requester_info(track, requester):
            track.requester = requester
            return track

        added_message = ""
        if isinstance(tracks, wavelink.Playlist):
            processed_tracks = [add_requester_info(track, ctx.author) for track in tracks.tracks]
            count = await player.queue.put_wait(processed_tracks)
            added_message = self._("playlist_added", playlist_name=tracks.name, count=count)
        elif isinstance(tracks, list) and len(tracks) > 0:
            track_to_play = add_requester_info(tracks[0], ctx.author)
            await player.queue.put_wait(track_to_play)
            added_message = self._("song_added_to_queue", song_title=track_to_play.title)
        elif isinstance(tracks, wavelink.Playable):
            track_to_play = add_requester_info(tracks, ctx.author)
            await player.queue.put_wait(track_to_play)
            added_message = self._("song_added_to_queue", song_title=track_to_play.title)
        else:
            return await ctx.send(self._("no_valid_song_or_playlist"))

        if added_message:
            await ctx.send(added_message)

        if not player.is_playing():
            try:
                first_track = await player.queue.get_wait()
                await player.play(first_track)
            except wavelink.QueueEmpty:
                await ctx.send(self._("queue_empty_on_play"))
            except Exception as e:
                await ctx.send(self._("error_playing_next", error=str(e)))

    @commands.hybrid_command(name="skip", aliases=['s'], description="現在の曲をスキップします。")
    async def skip_command(self, ctx: commands.Context):
        player = await self.ensure_voice(ctx, should_connect=False)
        if not player or not player.is_playing():
            return await ctx.send(self._("no_song_to_skip"))

        current_title = player.current.title if player.current else "現在の曲"
        await player.skip(force=True)
        await ctx.send(self._("song_skipped", song_title=current_title))

    @commands.hybrid_command(name="stop", aliases=['disconnect', 'leave', 'dc'],
                             description="再生を停止し、VCから切断します。")
    async def stop_command(self, ctx: commands.Context):
        player = await self.ensure_voice(ctx, should_connect=False)
        if not player or not player.is_connected():
            return await ctx.send(self._("not_in_vc"))

        if player.is_playing() or not player.queue.is_empty:
            player.queue.clear()
            await player.stop()
            await ctx.send(self._("stopped_and_cleared_queue"))

        await player.disconnect()
        await ctx.send(self._("disconnected_from_vc"))

    @commands.hybrid_command(name="queue", aliases=['q'], description="現在の再生キューを表示します。")
    async def queue_command(self, ctx: commands.Context):
        player = cast(wavelink.Player, ctx.voice_client)  # ensure_voiceはVC参加を強制するため、ここでは直接取得
        if not player or not player.is_connected():
            return await ctx.send(self._("not_in_vc"))

        if player.queue.is_empty and not player.current:
            return await ctx.send(self._("queue_is_empty"))

        embed = discord.Embed(title=self._("queue_embed_title"), color=discord.Color.blue())
        if player.current:
            requester_name = player.current.requester.display_name if hasattr(player.current,
                                                                              'requester') and player.current.requester else "N/A"
            embed.add_field(
                name=self._("now_playing_in_queue_field"),
                value=f"[{player.current.title}]({player.current.uri})\n`{self._('requested_by_footer', requester_name=requester_name)}`",
                inline=False
            )

        queue_list = []
        max_display = 10
        for i, track in enumerate(list(player.queue)[:max_display]):
            requester_name = track.requester.display_name if hasattr(track, 'requester') and track.requester else "N/A"
            queue_list.append(
                f"{i + 1}. [{track.title}]({track.uri})\n   `{self._('requested_by_footer', requester_name=requester_name)}`")

        if queue_list:
            embed.description = "\n".join(queue_list)
        elif not player.current:
            embed.description = self._("queue_is_empty")  # メッセージ修正

        if len(player.queue) > max_display:
            embed.set_footer(text=self._("queue_footer_more", count=len(player.queue) - max_display))
        elif player.queue.count == 0 and player.current:
            embed.set_footer(text=self._("queue_footer_empty_else"))
        elif player.queue.count > 0:  # キューに曲がある場合のみ全曲数を表示
            embed.set_footer(text=self._("queue_footer_total", count=player.queue.count))

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="nowplaying", aliases=['np'], description="現在再生中の曲を表示します。")
    async def nowplaying_command(self, ctx: commands.Context):
        player = cast(wavelink.Player, ctx.voice_client)
        if not player or not player.current:
            return await ctx.send(self._("no_song_to_skip"))  # "再生中の曲なし" の方が適切

        track = player.current
        embed = discord.Embed(title=self._("now_playing_embed_title_current"),
                              description=f"[{track.title}]({track.uri})", color=discord.Color.gold())
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)

        position = divmod(int(player.position / 1000), 60)
        duration = divmod(int(track.length / 1000), 60)
        embed.add_field(name=self._("playback_time_field"),
                        value=f"{position[0]:02d}:{position[1]:02d} / {duration[0]:02d}:{duration[1]:02d}")

        if hasattr(track, 'requester') and track.requester:
            embed.set_footer(text=self._("requested_by_footer", requester_name=track.requester.display_name),
                             icon_url=track.requester.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pause", description="再生を一時停止します。")
    async def pause_command(self, ctx: commands.Context):
        player = cast(wavelink.Player, ctx.voice_client)
        if not player or not player.is_playing():
            return await ctx.send(self._("no_song_to_skip"))  # 再生中ではない
        if player.is_paused():
            return await ctx.send(self._("already_paused"))

        await player.pause(True)
        await ctx.send(self._("paused"))

    @commands.hybrid_command(name="resume", description="一時停止を解除します。")
    async def resume_command(self, ctx: commands.Context):
        player = cast(wavelink.Player, ctx.voice_client)
        if not player or not player.is_connected():
            return await ctx.send(self._("not_in_vc"))
        if not player.is_paused():
            return await ctx.send(self._("not_paused"))

        await player.pause(False)
        await ctx.send(self._("resumed"))

    @commands.hybrid_command(name="volume", aliases=['vol'], description="音量を設定します (0-100)。")
    async def volume_command(self, ctx: commands.Context, volume: int):
        player = cast(wavelink.Player, ctx.voice_client)
        if not player or not player.is_connected():
            return await ctx.send(self._("not_in_vc"))

        if not 0 <= volume <= 100:
            return await ctx.send(self._("volume_out_of_range"))

        await player.set_volume(volume)
        await ctx.send(self._("volume_set", volume=volume))

    @commands.hybrid_command(name="loop", description="ループモードを設定します (off, track, queue)。")
    async def loop_command(self, ctx: commands.Context, mode: str):
        player = cast(wavelink.Player, ctx.voice_client)
        if not player or not player.is_connected():
            return await ctx.send(self._("not_in_vc"))

        mode = mode.lower()
        if mode == "off":
            player.queue.mode = wavelink.QueueMode.normal
            await ctx.send(self._("loop_off"))
        elif mode in ["track", "song"]:
            player.queue.mode = wavelink.QueueMode.loop_track
            await ctx.send(self._("loop_track"))
        elif mode in ["queue", "all"]:
            player.queue.mode = wavelink.QueueMode.loop_all
            await ctx.send(self._("loop_queue"))
        else:
            await ctx.send(self._("loop_invalid_mode"))

    @commands.hybrid_command(name="shuffle", description="再生キューをシャッフルします。")
    async def shuffle_command(self, ctx: commands.Context):
        player = cast(wavelink.Player, ctx.voice_client)
        if not player or not player.is_connected():
            return await ctx.send(self._("not_in_vc"))
        if player.queue.is_empty:
            return await ctx.send(self._("shuffle_fail_empty_queue"))

        player.queue.shuffle()
        await ctx.send(self._("shuffled_queue"))


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))