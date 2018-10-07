import asyncio

import discord
from discord.ext import commands

from redbot.core import Config
from redbot.core import i18n
from redbot.core import checks

from . import wallet_node

_ = i18n.CogI18n("Tippr", __file__)

BaseCog = getattr(commands, "Cog", object)

class Tippr(BaseCog):
    def __init__(self, loop: asyncio.BaseEventLoop):
        self.config = Config.get_conf(self, 879834294283290, force_registration=True)
        self.config.register_global(
            wallet_address=None,
            rpc__host=None,
            rpc__port=None,
            rpc__username=None,
            rpc__password=None
        )
        self.config.register_user(
            deposit_address=None
        )

        loop.create_task(self.attempt_init(loop))

    async def attempt_init(self, loop: asyncio.BaseEventLoop):
        rpc_info = await self.config.rpc()

        try:
            await wallet_node.initialize(loop, **rpc_info)
        except RuntimeError:
            pass

    async def _get_addr(self, user: discord.User):
        """
        Gets a users unique deposit address if it exists. Otherwise
        this will create one and set it in the config object.

        Parameters
        ----------
        user : discord.User

        Returns
        -------
        str
            BTC address.
        """
        addr = await self.config.user(user).deposit_address()

        if addr is None:
            addr = await wallet_node.get_new_address(str(user.id))
            await self.config.user(user).deposit_address.set(addr)

        return addr

    async def _get_btc_amount(self, user: discord.User) -> int:
        """
        Gets the users current balance in satoshis.

        Parameters
        ----------
        user : discord.User

        Returns
        -------
        int
            Satoshis available to tip.
        """
        return await wallet_node.get_received_by_account(str(user.id))

    async def _tip(self, from_user: discord.User, to_user: discord.User,
                   amount: int):
        """
        Sends ``amount`` from ``from_user`` to ``to_user``.

        Raises
        ------
        ValueError
            If ``from_user`` does not have enough funds.

        Parameters
        ----------
        from_user : discord.User
        to_user : discord.User
        amount : int
            Amount to send in Satoshis
        """
        available_satoshis = await self._get_btc_amount(from_user)

        if amount <= 0:
            raise ValueError("{} <= 0".format(amount))
        elif amount > available_satoshis:
            raise ValueError("{} > {}".format(amount, available_satoshis))

        # Ensure ``to_user`` has an account in the wallet.
        await self._get_addr(to_user)

        await wallet_node.move(str(from_user.id), str(to_user.id), amount)

    @commands.group(invoke_without_command=True)
    async def tip(self, ctx, user: discord.User, amount: float):
        """
        Tips a user.
        """
        satoshi_amount = wallet_node.json_to_amount(amount)

        try:
            await self._tip(ctx.author, user, satoshi_amount)
        except ValueError:
            await ctx.send(_("You don't have enough BCH to tip that!"))

    @tip.command()
    async def deposit(self, ctx):
        """
        Gives a user a unique address to deposit to.
        """
        addr = await self._get_addr(ctx.author)

        await ctx.send(
            _("Please use this address to deposit BCH:\n`{}`").format(
                addr
            ))

    @tip.command()
    async def balance(self, ctx):
        """
        DMs the author's current balance.
        """
        msg = _("You have {:.8} in bitcoin cash!")
        satoshis = await self._get_btc_amount(ctx.author)

        await ctx.author.send(msg.format(
            wallet_node.amount_to_json(satoshis)
        ))

    @tip.command()
    @checks.is_owner()
    async def setup(self, ctx):
        """
        Initial set up of the BCH wallet to use.
        """
        def check(m):
            return m.author == ctx.author

        data = {}

        for noun in ("host", "port", "username", "password"):
            await ctx.author.send(
                _("Please tell me the {}:").format(noun)
            )
            try:
                msg = await ctx.bot.wait_for("message", check=check)
            except asyncio.TimeoutError:
                break
            data[noun] = msg.content
        else:
            await self.config.rpc.set(data)
            await self.attempt_init(ctx.bot.loop)
