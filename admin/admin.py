import discord
from discord.ext import commands
from cogs.utils import checks
from __main__ import settings
from copy import deepcopy
import asyncio
import logging


log = logging.getLogger("red.admin")


class Admin:
    """Admin tools, more to come."""

    def __init__(self, bot):
        self.bot = bot
        self._announce_msg = None

    def _role_from_string(self, server, rolename):
        role = discord.utils.find(lambda r: r.name.lower() == rolename.lower(),
                                  server.roles)
        try:
            log.debug("Role {} found from rolename {}".format(
                role.name, rolename))
        except:
            log.debug("Role not found for rolename {}".format(rolename))
        return role

    @commands.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def addrole(self, ctx, rolename, user: discord.Member=None):
        """Adds a role to a user, defaults to author

        Role name must be in quotes if there are spaces."""
        author = ctx.message.author
        channel = ctx.message.channel
        server = ctx.message.server

        if user is None:
            user = author

        role = self._role_from_string(server, rolename)

        if role is None:
            await self.bot.say('That role cannot be found.')
            return

        if not channel.permissions_for(server.me).manage_roles:
            await self.bot.say('I don\'t have manage_roles.')
            return

        if author.id == settings.owner:
            pass
        elif not channel.permissions_for(author).manage_roles:
            raise commands.CheckFailure

        await self.bot.add_roles(user, role)
        await self.bot.say('Added role {} to {}'.format(role.name, user.name))

    @commands.command(pass_context=True)
    @checks.is_owner()
    async def announce(self, ctx, *, msg):
        """Announces a message to all servers that a bot is in."""
        if self._announce_msg is not None:
            await self.bot.say("Already announcing, wait until complete to"
                               " issue a new announcement.")
        else:
            self._announce_msg = msg

    @commands.command(no_pm=True, pass_context=True)
    @checks.admin_or_permissions(manage_roles=True)
    async def removerole(self, ctx, rolename, user: discord.Member=None):
        """Removes a role from user, defaults to author

        Role name must be in quotes if there are spaces."""
        server = ctx.message.server
        author = ctx.message.author

        role = self._role_from_string(server, rolename)
        if role is None:
            await self.bot.say("Role not found.")
            return

        if user is None:
            user = author

        if role in user.roles:
            try:
                await self.bot.remove_roles(user, role)
                await self.bot.say("Role successfully removed.")
            except discord.Forbidden:
                await self.bot.say("I don't have permissions to manage roles!")
        else:
            await self.bot.say("User does not have that role.")

    @commands.command(no_pm=True, pass_context=True)
    async def say(self, ctx, *, text):
        """Repeats what you tell it.

        Can use `message`, `channel`, `server`, and `discord`
        """
        user = ctx.message.author
        if hasattr(user, 'bot') and user.bot is True:
            return
        try:
            evald = eval(text, {}, {'message': ctx.message,
                                    'channel': ctx.message.channel,
                                    'server': ctx.message.server,
                                    'discord': discord})
        except:
            evald = text
        if len(str(evald)) > 2000:
            evald = str(evald)[-1990:] + " you fuck."
        await self.bot.say(evald)

    @commands.command(pass_context=True)
    @checks.is_owner()
    async def sudo(self, ctx, user: discord.Member, *, command):
        """Runs the [command] as if [user] had run it. DON'T ADD A PREFIX
        """
        new_msg = deepcopy(ctx.message)
        new_msg.author = user
        new_msg.content = self.bot.command_prefix[0] + command
        await self.bot.process_commands(new_msg)

    async def announcer(self, msg):
        server_ids = map(lambda s: s.id, self.bot.servers)
        for server_id in server_ids:
            if self != self.bot.get_cog('Admin'):
                break
            server = self.bot.get_server(server_id)
            if server is None:
                continue
            chan = server.default_channel
            log.debug("Looking to announce to {} on {}".format(chan.name,
                                                               server.name))
            me = server.me
            if chan.permissions_for(me).send_messages:
                log.debug("I can send messages to {} on {}, sending".format(
                    server.name, chan.name))
                await self.bot.send_message(chan, msg)
            await asyncio.sleep(1)

    async def announce_manager(self):
        while self == self.bot.get_cog('Admin'):
            if self._announce_msg is not None:
                log.debug("Found new announce message, announcing")
                await self.announcer(self._announce_msg)
                self._announce_msg = None
            await asyncio.sleep(1)

    @commands.command(pass_context=True)
    @checks.is_owner()
    async def partycrash(self, ctx, idnum=None):
        """Lists servers and generates invites for them"""
        owner = ctx.message.author
        if idnum:
            server = discord.utils.get(self.bot.servers, id=idnum)
            if server:
                await self.confirm_invite(server, owner, ctx)
            else:
                await self.bot.say("I'm not in that server")
        else:
            servers = list(self.bot.servers)
            server_list = {}
            msg = ""
            for i in range(0, len(servers)):
                server_list[str(i)] = servers[i]
                msg += "{}: {}\n".format(str(i), servers[i].name)
            msg += "\nTo post an invite for a server just type its number."
            await self.bot.say(msg)
            msg = await self.bot.wait_for_message(author=owner, timeout=15)
            if msg is not None:
                msg = msg.content.strip()
                if msg in server_list.keys():
                    await self.confirm_invite(server_list[msg], owner, ctx)

    async def confirm_invite(self, server, owner, ctx):
        answers = ("yes", "y")
        invite = await self.bot.create_invite(server)
        if ctx.message.channel.is_private:
            await self.bot.say(invite)
        else:
            await self.bot.say("Are you sure you want to post an invite to {} "
                               "here? (yes/no)".format(server.name))
            msg = await self.bot.wait_for_message(author=owner, timeout=15)
            if msg is None:
                await self.bot.say("I guess not.")
            elif msg.content.lower().strip() in answers:
                await self.bot.say(invite)
            else:
                await self.bot.say("Alright then.")


def setup(bot):
    n = Admin(bot)
    bot.add_cog(n)
    bot.loop.create_task(n.announce_manager())
