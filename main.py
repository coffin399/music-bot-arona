import discord
from discord.ext import commands
import os
import yaml  # PyYAMLをインポート
from typing import Any


# config.yaml から設定を読み込む関数
def load_config(filename: str = "config.yaml") -> dict[str, Any]:
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        if not config_data:
            raise ValueError("Config file is empty or invalid.")
        # 必須キーのチェック (例)
        if 'discord' not in config_data or 'token' not in config_data['discord']:
            raise ValueError("Discord token not found in config.yaml")
        if 'lavalink' not in config_data:
            raise ValueError("Lavalink configuration not found in config.yaml")
        return config_data
    except FileNotFoundError:
        print(f"エラー: {filename} が見つかりません。作成してください。")
        exit(1)
    except yaml.YAMLError as e:
        print(f"エラー: {filename} の解析に失敗しました: {e}")
        exit(1)
    except ValueError as e:
        print(f"エラー: {e}")
        exit(1)


# 設定ファイルを読み込む
config = load_config()

TOKEN = config['discord']['token']
BOT_PREFIX = config['discord'].get('prefix', '!')  # prefixがない場合のデフォルト

# BOTのIntents設定
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True


class MyBot(commands.Bot):
    def __init__(self, config_data: dict[str, Any]):
        super().__init__(command_prefix=commands.when_mentioned_or(BOT_PREFIX), intents=intents)
        self.config_data = config_data  # BOTインスタンスに設定全体を保持
        self.initial_extensions = ['music_cog']

    async def setup_hook(self):
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"Loaded extension: {extension}")
            except Exception as e:
                print(f"Failed to load extension {extension}: {e}")
                import traceback
                traceback.print_exc()

        # スラッシュコマンドの同期 (必要に応じてギルド指定)
        try:
            # synced = await self.tree.sync()
            # print(f"Synced {len(synced)} slash commands globally.")
            pass  # MusicCogのNode接続後に同期した方が良い場合もある
        except Exception as e:
            print(f"Failed to sync slash commands: {e}")

    async def on_ready(self):
        print(f'Logged in as {self.user.name} (ID: {self.user.id})')
        print('------')
        activity_name = self.config_data.get('discord', {}).get('activity_name', f"音楽 | {BOT_PREFIX}help")
        activity = discord.Activity(type=discord.ActivityType.listening, name=activity_name)
        await self.change_presence(activity=activity)


bot = MyBot(config_data=config)


# メッセージ取得ヘルパー (グローバルに置くか、BOTのメソッドにする)
def get_message(key: str, **kwargs) -> str:
    try:
        keys = key.split('.')
        message_template = bot.config_data['messages']  # botインスタンスからconfigを参照
        for k_part in keys:
            message_template = message_template[k_part]

        # プレフィックスを自動的にフォーマット引数に追加
        if 'prefix' not in kwargs:
            kwargs['prefix'] = BOT_PREFIX

        return message_template.format(**kwargs)
    except KeyError:
        print(f"Warning: Message key '{key}' not found in config.yaml!")
        return f"Message key '{key}' not found."  # フォールバックメッセージ
    except Exception as e:
        print(f"Error formatting message for key '{key}': {e}")
        return f"Error formatting message for key '{key}'."


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(get_message("error_command_not_found"))
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(get_message("error_missing_argument", argument=error.param.name,
                                   command=ctx.command.qualified_name if ctx.command else "this command"))
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(get_message("error_cooldown", seconds=error.retry_after))
    elif isinstance(error, commands.CheckFailure):
        # cog_checkでメッセージ送信済みの場合が多いので、ここではログのみか何もしない
        # MusicCog の cog_check でメッセージを送るようにする
        print(f"Check failed for command {ctx.command}: {error}")
    elif isinstance(error, commands.HybridCommandError) and isinstance(error.original, wavelink.LavalinkLoadException):
        await ctx.send(get_message("music.error_lavalink_load", error=str(error.original)))
    else:
        print(f"Unhandled command error in {ctx.command}: {error}")
        # await ctx.send(get_message("error_generic", error=str(error))) # デバッグ用


if __name__ == '__main__':
    if TOKEN is None:  # load_configでチェックされるが念のため
        print("エラー: DISCORD_TOKENが設定されていません。config.yamlを確認してください。")
    else:
        bot.run(TOKEN)