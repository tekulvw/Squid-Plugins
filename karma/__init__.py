from .karma import Karma


async def setup(bot):
    bot.add_cog(Karma(bot))
