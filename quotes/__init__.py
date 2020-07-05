from .quotes import Quotes


async def setup(bot):
    bot.add_cog(Quotes(bot))
