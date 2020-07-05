import discord
import tabulate
from redbot.core import commands, checks, Config
from redbot.core.utils.chat_formatting import box


class Karma(commands.Cog):
    """Keep track of user scores through @mention ++/--

    Example: ++ @\u200BWill (or @\u200BWill ++)"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 6133, force_registration=True)

        default_guild = {"respond_on_point": True}

        default_user = {
            "score": 0,
            "reasons": [],
        }

        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)


    async def _process_scores(self, member: discord.Member, score_to_add: int):
        score = await self.config.user(member).score()
        await self.config.user(member).score.set(score + score_to_add)

    async def _add_reason(self, member: discord.Member, reason: str):
        if reason.lstrip() == "":
            return
        member_reasons = await self.config.user(member).reasons()
        if member_reasons:
            new_reasons = [reason] + member_reasons[:4]
            await self.config.user(member).reasons.set(new_reasons)
        else:
            await self.config.user(member).reasons.set([reason])

    def _fmt_reasons(self, reasons: list):
        if len(reasons) == 0:
            return None
        ret = "Latest Reasons:\n"
        for num, reason in enumerate(reasons):
            ret += f"\t{num + 1}) {reason}\n"
        return ret

    @commands.command()
    async def karma(self, ctx, user_id_or_mention: discord.Member):
        """Checks a user's karma.

        Example: [p]karma @Red"""
        user_data = await self.config.user(user_id_or_mention).all()
        if user_data["score"] != 0:
            await ctx.send(f"{user_id_or_mention.name} has {user_data['score']} points!")
            if user_data["reasons"]:
                try:
                    reasons = self._fmt_reasons(user_data["reasons"])
                    await ctx.author.send(box(reasons))
                except discord.errors.Forbidden:
                    pass
        else:
            await ctx.send(f"{user_id_or_mention.name} has no karma!")

    @commands.command()
    async def karmaboard(self, ctx):
        """Karma leaderboard"""
        all_users = await self.config.all_users()
        member_ids = [m.id for m in ctx.guild.members]
        karma_server_members = [key[0] for key in all_users.items() if key[0] in member_ids]
        names = list(map(lambda mid: discord.utils.get(ctx.guild.members, id=mid).name, karma_server_members))
        scores = list(map(lambda mid: all_users[mid]["score"], karma_server_members))
        headers = ["User", "Karma"]
        body = sorted(zip(names, scores), key=lambda tup: tup[1], reverse=True)[:10]
        table = tabulate.tabulate(body, headers, tablefmt="psql")
        await ctx.send(box(table))

    @commands.group()
    @checks.mod_or_permissions(manage_messages=True)
    async def karmaset(self, ctx):
        """Manage karma settings."""
        pass

    @karmaset.command(name="respond")
    async def _karmaset_respond(self, ctx):
        """Toggles if bot will respond when points get added/removed."""
        respond = await self.config.guild(ctx.guild).respond_on_point()
        if respond:
            await ctx.send("Responses disabled.")
        else:
            await ctx.send("Responses enabled.")
        await self.config.guild(ctx.guild).respond_on_point.set(not respond)

    @checks.is_owner()
    @karmaset.command(name="score")
    async def _karmaset_score(self, ctx, user_id_or_mention: discord.User, score: int):
        """Set a user's score."""
        topend = 2 ** 63 - 1
        if score < topend:
            await self.config.user(user_id_or_mention).score.set(score)
            await ctx.send(f"Set {user_id_or_mention.name}'s score to {score}.")
        else:
            await ctx.send(f"The score must be less than {topend}.")

    @checks.is_owner()
    @karmaset.command(name="reasons")
    async def _karmaset_reasons(self, ctx, user_id_or_mention: discord.User):
        """Clear a user's reasons."""
        await self.config.user(user_id_or_mention).reasons.set([])
        await ctx.send(f"Cleared {user_id_or_mention.name}'s reasons.")

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if not message.mentions:
            return
        if not message.guild:
            return
        if message.author.bot:
            return
        if not message.channel.permissions_for(message.guild.me).send_messages:
            return
        splitted = message.content.split(" ")
        if len(splitted) > 1:
            if "++" == splitted[0] or "--" == splitted[0]:
                if len(splitted[0]) == 2:
                    first_word = "".join(splitted[:2])
                else:
                    first_word = "".join(splitted[:1])
            elif "++" == splitted[1] or "--" == splitted[1]:
                first_word = "".join(splitted[:2])
            else:
                first_word = splitted[0]
        else:
            first_word = splitted[0]
        reason = message.content[len(first_word) + 1 :].lstrip()
        target_user = message.mentions[0]
        if target_user == message.author:
            if "++" or "--" in first_word:
                await message.channel.send("You can't modify your own rep, jackass.")
                return
        if "++" in first_word:
            await self._process_scores(target_user, 1)
            await self._add_reason(target_user, reason)
        elif "--" in first_word:
            await self._process_scores(target_user, -1)
            await self._add_reason(target_user, reason)
        else:
            return

        if await self.config.guild(message.guild).respond_on_point():
            score = await self.config.user(target_user).score()
            msg = f"{target_user.name} now has {score} points."
            await message.channel.send(msg)
