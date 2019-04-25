from .bankvampire import BankVampire


async def setup(bot):
    bot.add_cog(BankVampire(bot))
