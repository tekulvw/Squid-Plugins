import discord
from random import choice as randchoice
from redbot.core import checks, commands, Config
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.utils.common_filters import filter_various_mentions


class Quotes(commands.Cog):
    """Save quotes and read them later."""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 6133, force_registration=True)

        default_guild = {"quotes": []}

        self.config.register_guild(**default_guild)

    @staticmethod
    def _get_random_quote(quotes: list):
        if len(quotes) == 0:
            return "There are no saved quotes!"
        return randchoice(quotes)

    @staticmethod
    def _get_quote(num: int, quotes: list):
        if num > 0 and num <= len(quotes):
            return quotes[num - 1]
        else:
            return "That quote doesn't exist!"

    async def _add_quote(self, ctx, message: str, quotes: list):
        quotes = quotes + [message]
        await self.config.guild(ctx.guild).quotes.set(quotes)

    @staticmethod
    def _fmt_quotes(quotes: list):
        ret = ""
        for num, quote in enumerate(quotes):
            ret += f"{num + 1}) {quote}\n"
        return ret

    async def _try_to_dm(self, ctx, message: str):
        try:
            await ctx.author.send(message)
        except discord.errors.Forbidden:
            await ctx.send("I can't DM you, you've blocked me.")

    @checks.mod_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.command()
    async def delquote(self, ctx, quote_number: int):
        """Deletes a quote by its number.

           Use [p]allquotes to find quote numbers.
           Example: [p]delquote 3"""
        quotes = await self.config.guild(ctx.guild).quotes()
        if quote_number > 0 and quote_number <= len(quotes):
            for i in range(len(quotes)):
                if quote_number - 1 == i:
                    quotes.remove(quotes[i])
                    await ctx.send(f"Quote number {quote_number} has been deleted.")
            await self.config.guild(ctx.guild).quotes.set(quotes)
        else:
            await ctx.send(f"Quote {quote_number} does not exist.")

    @checks.mod_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.command()
    async def delallquote(self, ctx, quote_number: int):
        """Deletes all quotes for the guild."""
        await self.config.guild(ctx.guild).quotes.set([])
        await ctx.send("All quotes for this guild have been deleted.")

    @commands.guild_only()
    @commands.command()
    async def allquotes(self, ctx):
        """Gets a list of all quotes."""
        quotes = await self.config.guild(ctx.guild).quotes()
        if not quotes:
            await ctx.send("There are no saved quotes!")
            return
        strbuffer = self._fmt_quotes(quotes)
        for page in pagify(strbuffer, delims=["\n"], page_length=1980):
            await self._try_to_dm(ctx, box(page))

    @commands.guild_only()
    @commands.command()
    async def quote(self, ctx, *, message = None):
        """Adds quote, retrieves random one, or a numbered one.
               Use [p]allquotes to get a list of all quotes.

           Example: [p]quote The quick brown fox -> adds quote
                    [p]quote -> gets random quote
                    [p]quote 4 -> gets quote #4"""
        quotes = await self.config.guild(ctx.guild).quotes()
        try:
            message_number = int(message)
            await ctx.send(self._get_quote(message_number, quotes))
            return
        except:
            pass
        if not message:
            await ctx.send(self._get_random_quote(quotes))
        else:
            await self._add_quote(ctx, filter_various_mentions(message), quotes)
            await ctx.send("Quote added.")
