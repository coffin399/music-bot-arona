import logging
import discord
from discord.ext import commands
from services import ytdlp_wrapper as ytdl
from services.guild_player import GuildPlayer
from domain.entity.track import Track

logger = logging.getLogger('arona.music')

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: dict[int, GuildPlayer] = {}

    def get_player(self, guild: discord.Guild) -> GuildPlayer | None:
        """Get or create a player for the guild."""
        if not guild.voice_client:
            return None
            
        if guild.id not in self.players:
            self.players[guild.id] = GuildPlayer(guild, guild.voice_client)
        return self.players[guild.id]

    @commands.hybrid_command(name="play", description="曲を再生します")
    async def play(self, ctx: commands.Context, *, query: str):
        """Play a song from a query (YouTube, SoundCloud, etc.)"""
        await ctx.defer()

        # Check if user is in a voice channel
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply("You need to be in a voice channel to use this command!")
            return

        # Get or create voice client
        vc = ctx.guild.voice_client
        if vc is None:
            vc = await ctx.author.voice.channel.connect()
        elif vc.channel != ctx.author.voice.channel:
            await ctx.reply("I'm already in a different voice channel!")
            return

        # Extract track info
        try:
            track = await ytdl.extract(query)
            if isinstance(track, list):
                if not track:
                    raise ValueError("No tracks found in the playlist")
                track = track[0]  # Take first track if it's a playlist
                
            track.requester_id = ctx.author.id
        except Exception as e:
            import traceback
            error_details = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
            logger.error(f"Error extracting track: {error_details}")
            
            # Send a more detailed error message to the user
            error_msg = (
                f"Error processing your request: {str(e)}\n"
                "Please try again or try a different URL.\n"
                "If the issue persists, please contact support with the error details."
            )
            await ctx.reply(error_msg)
            return

        # Get or create player and enqueue track
        player = self.get_player(ctx.guild)
        if not player:
            await ctx.reply("Failed to initialize player.")
            return
            
        await player.enqueue(track)
        player.start()

        await ctx.reply(f"Queued: **{track.title}**")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Clean up when the bot is disconnected from voice."""
        if member.id == self.bot.user.id and before.channel and not after.channel:
            # Bot was disconnected from voice
            if member.guild.id in self.players:
                player = self.players.pop(member.guild.id)
                await player.stop()

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
