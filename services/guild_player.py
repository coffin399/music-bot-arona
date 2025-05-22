import asyncio
import logging
from typing import Optional
from pathlib import Path
import discord
from domain.entity.track import Track

logger = logging.getLogger('arona.music.player')

class GuildPlayer:
    def __init__(self, guild: discord.Guild, voice_client: discord.VoiceClient):
        self.guild = guild
        self.voice_client = voice_client
        self.queue: asyncio.Queue[Track] = asyncio.Queue()
        self.player_task: Optional[asyncio.Task] = None
        self.current_track: Optional[Track] = None

    async def enqueue(self, track: Track):
        """Add a track to the queue."""
        await self.queue.put(track)
        return track

    async def player_loop(self):
        """The main player loop that processes tracks from the queue."""
        while True:
            try:
                self.current_track = await self.queue.get()
                
                if not self.voice_client.is_connected():
                    break

                if Path(self.current_track.stream_url).is_file():
                    src = discord.FFmpegPCMAudio(
                        source=self.current_track.stream_url,
                        before_options="-nostdin",
                        options="-vn",
                    )
                else:
                    ffmpeg_opts = {
                        "before_options": (
                            "-nostdin "
                            "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
                        ),
                        "options": "-vn",
                    }
                    src = await discord.FFmpegOpusAudio.from_probe(
                        self.current_track.stream_url,
                        **ffmpeg_opts
                    )
                
                done = asyncio.Event()

                def _after(err):
                    try:
                        if err:
                            logger.error(f"Player error: {err}")
                        
                        # Delete local cache file if it exists
                        if self.current_track and self.current_track.stream_url:
                            try:
                                file_path = Path(self.current_track.stream_url)
                                if file_path.is_file():
                                    file_path.unlink()
                                    logger.debug(f"Deleted local cache file: {file_path}")
                            except Exception as e:
                                logger.error(f"Error deleting cache file {self.current_track.stream_url}: {e}", exc_info=True)
                                
                    finally:
                        done.set()

                self.voice_client.play(src, after=_after)
                try:
                    await done.wait()
                finally:
                    # Ensure cleanup in case of cancellation
                    if hasattr(self, 'current_track') and self.current_track and self.current_track.stream_url:
                        try:
                            file_path = Path(self.current_track.stream_url)
                            if file_path.is_file():
                                file_path.unlink()
                                logger.debug(f"Deleted local cache file during cleanup: {file_path}")
                        except Exception as e:
                            logger.error(f"Error during cleanup of cache file {self.current_track.stream_url}: {e}", exc_info=True)
                
            except Exception as e:
                logger.error(f"Error in player loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    def start(self):
        """Start the player loop."""
        if self.player_task is None or self.player_task.done():
            self.player_task = asyncio.create_task(self.player_loop())

    async def stop(self):
        """Stop the player and clean up resources."""
        if self.player_task and not self.player_task.done():
            self.player_task.cancel()
            try:
                await self.player_task
            except asyncio.CancelledError:
                pass
            self.player_task = None

        if self.voice_client.is_connected():
            await self.voice_client.disconnect()

    def is_playing(self) -> bool:
        """Check if the player is currently playing a track."""
        return self.voice_client.is_playing() or self.voice_client.is_paused()

    def pause(self):
        """Pause the current track."""
        if self.voice_client.is_playing():
            self.voice_client.pause()

    def resume(self):
        """Resume the current track."""
        if self.voice_client.is_paused():
            self.voice_client.resume()

    def skip(self):
        """Skip the current track."""
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
