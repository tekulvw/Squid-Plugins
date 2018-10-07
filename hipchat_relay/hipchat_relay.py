from aiohttp import ClientSession
import logging

import discord
from discord.ext import commands

from redbot.core import Config

log = logging.getLogger("red.squid.hipchat")

BaseCog = getattr(commands, "Cog", object)


class HipchatRelay(BaseCog):
    def __init__(self):
        self.conf = Config.get_conf(self, 6133, force_registration=True)

        self.conf.register_global(
            token=None,
            room=None,
            server=None,
            enabled=False
        )

        self.enabled = None
        self.token = None
        self.server = None
        self.room = None

        self.session = ClientSession()

    async def initialize(self, bot):
        self.enabled = await self.conf.enabled()
        self.token = await self.conf.token()
        self.server = await self.conf.server()
        self.room = await self.conf.room()

        if self.enabled:
            bot.add_listener(self.relay, 'on_message')

    @commands.command()
    async def hiptoken(self, ctx, token: str):
        """
        Set the token to use to relay messages.

        This should be a PERSONAL TOKEN and needs to be generated from
        HIPCHAT_SERVER/account/api.
        """
        self.token = token
        await self.conf.token.set(token)
        await ctx.send("Token set.")

    @commands.command()
    async def hipserver(self, ctx, server: str, room: str):
        """
        Set the hipchat server and room to send relayed messages to.
        Room is case sensitive!

        Should be in form: http(s)://HIPCHAT_SERVER.TLD
        """
        server = server.strip('/')
        await self.conf.server.set(server)
        await self.conf.room.set(room)

    @commands.command()
    async def hiprelay(self, ctx, status: bool):
        """
        Enables/disables the hipchat relay.

        Usage:
        [p]hiprelay on
        [p]hiprelay off
        """
        if self.enabled is None:
            self.enabled = await self.conf.enabled()

        if self.enabled != status:
            self.enabled = status
            await self.conf.enabled.set(status)
            if status is True:
                ctx.bot.add_listener(self.relay, 'on_message')
            else:
                ctx.bot.remove_listener(self.relay, 'on_message')

    async def send(self, message: discord.Message):
        if None in (self.token, self.server, self.room):
            return

        guild = message.guild if hasattr(message.channel, 'guild') else "DM"
        channel = message.channel if hasattr(message.channel, 'guild') else None
        author = message.author
        time = message.created_at.strftime("%m-%d-%Y %H:%M:%S")

        if channel is None:
            content = "[{}] [{}] [{}]: {}".format(
                guild, author, time, message.clean_content
            )
        else:
            content = "[{}] [{}] [{}] [{}]: {}".format(
                guild, channel, author, time, message.clean_content
            )

        headers = {'Authorization': 'Bearer {}'.format(self.token)}
        payload = {'message': content}
        url = "{}/v2/room/{}/message".format(self.server, self.room)

        async with self.session.post(url, headers=headers, json=payload) as r:
            if r.status >= 300:
                log.info("Bad configuration, got status {}".format(r.status))
                log.info('Config: {} {} {}'.format(headers, payload, url))

    async def relay(self, message):
        if not self.enabled:
            return

        await self.send(message)
