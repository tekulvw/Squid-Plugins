from .logger import Logger


async def setup(bot):
    cog = Logger(bot)
    bot.add_cog(cog)

    await cog.refresh_levels()
