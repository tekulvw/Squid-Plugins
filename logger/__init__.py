from .logger import Logger

__red_end_user_data_statement__ = (
    "This cog does not persistently store data or metadata about users."
)


async def setup(bot):
    cog = Logger(bot)
    bot.add_cog(cog)

    await cog.refresh_levels()
