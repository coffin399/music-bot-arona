import discord
import logging
from discord.ext import commands
import asyncio
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('arona')

class AronaBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            command_prefix=config.get('discord.prefix', '!'),
            intents=discord.Intents.all(),
            *args,
            **kwargs
        )
        self.initial_extensions = [
            'cogs.music',
        ]

    async def setup_hook(self) -> None:
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f'Loaded extension: {extension}')
            except Exception as e:
                logger.error(f'Failed to load extension {extension}: {e}')
        
        await self.tree.sync()
        logger.info('Synced application commands')

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info('------')


async def main():
    bot = AronaBot()
    
    token = config.get('discord.token')
    if not token or token == 'YOUR_DISCORD_TOKEN_HERE':
        logger.error("Error: Please set your Discord token in config.yaml")
        return
    
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Error in main: {e}")
