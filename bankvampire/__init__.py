from .bankvampire import BankVampire

__red_end_user_data_statement__ = "This cog does store discord IDs as needed for operation."


async def setup(bot):
    bot.add_cog(BankVampire(bot))
