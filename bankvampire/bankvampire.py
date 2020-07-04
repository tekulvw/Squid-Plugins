import asyncio
import math
import random
import time
import logging

from redbot.core import bank
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import box

###
# The function used to calculate loss is as follows:
#   PERCENT = max_percent * ((2^difficulty)^random() - 1) / ((2^difficulty) - 1)
###
from redbot.core.utils.chat_formatting import pagify

log = logging.getLogger("red.cogs.bankvampire")


class BankVampire(commands.Cog):
    def __init__(self, bot):
        super().__init__()

        self.bot = bot
        self.config = Config.get_conf(self, 6133, force_registration=True)
        global_defaults = {
            "min_delay": 15,  # minutes
            "delay": 30,  # minutes
            "max_delay": 180,  # minutes
            "wrecklevel": 500000,
            "max_percent": 5,
            "enabled": True,
            "next_attack": 0,
            "count": 1,
        }
        self.config.register_global(**global_defaults)

        guild_defaults = {
            "reporting_channel": None,
        }
        self.config.register_guild(**guild_defaults)

        user_defaults = {
            "hit_count": 0,
            "loss_total": 0,
            "gain_total": 0,
            "spent": 0,
        }
        self.config.register_user(**user_defaults)

        self.attack_origin = None

        self.task = self.bot.loop.create_task(self.safety_loop())

    def cog_unload(self):
        self.task.cancel()

    def __unload(self):
        self.task.cancel()

    @commands.command()
    async def vampattack(self, ctx):
        """
        Commands the Vampires to attack!

        Costs a (large) random amount.
        """
        cost = min(max(int(random.expovariate(1 / 5000)), 500), 10000)
        if not await bank.can_spend(ctx.author, cost):
            await ctx.send(f"You can't afford it.")
            return

        await bank.withdraw_credits(ctx.author, cost)

        if self.attack_origin is None:
            if ctx.guild is not None:
                self.attack_origin = f"{ctx.author} on {ctx.guild}"
            else:
                self.attack_origin = ctx.author

        spent = cost + await self.config.user(ctx.author).spent()
        await self.config.user(ctx.author).spent.set(spent)
        await self.config.next_attack.set(0)

        await ctx.send(f"Congratulations, you spent {cost} to make the vampires attack.")

    @commands.command()
    async def vampstat(self, ctx, user: commands.UserConverter = None):
        """
        Check the vampire stats for yourself or others.
        """
        if user is None:
            user = ctx.author
        hit_count = await self.config.user(user).hit_count()
        loss_total = await self.config.user(user).loss_total()
        gain_total = await self.config.user(user).gain_total()
        spent = await self.config.user(user).spent()

        await ctx.send(
            f"Over the course of your short life you've been attacked {hit_count} times, lost {loss_total}"
            f" and gained {gain_total}. And sadly, you've spent {spent} to attack others. Peasant."
        )

    @commands.group()
    async def vampset(self, ctx):
        """
        Settings for the vampires.
        """
        pass

    @vampset.command(name="percent")
    async def vampset_percent(self, ctx, percent: int):
        """
        Sets the percentage of a users balance they could lose.

        This value should be between 0 and 15.
        """
        if percent <= 0:
            percent = 1
        elif percent >= 15:
            percent = 10

        await self.config.max_percent.set(percent)
        await ctx.send(f"Vamp percent set to {percent}%.")

    @vampset.command(name="wrecklevel")
    async def vampset_wrecklevel(self, ctx, amount: int):
        """
        Sets the minimum balance to trigger a much more aggressive loss function.

        Default is 500K. Be careful with this.
        """
        if amount < 100000:
            amount = 500000

        await self.config.wrecklevel.set(amount)
        await ctx.send(f"Difficulty set to {amount}.")

    @vampset.command(name="delay")
    async def vampset_delay(self, ctx, delay: int):
        """
        Set the delay between vampire attacks.

        `delay` in minutes.
        """
        min_delay = await self.config.min_delay()
        max_delay = await self.config.max_delay()
        if delay < min_delay:
            await ctx.send(f"Delay must be greater than {min_delay} minutes.")
            return
        elif delay > max_delay:
            delay = max_delay

        await self.config.delay.set(delay)
        await ctx.send(f"Delay has been set to {delay}!")

    @vampset.command(name="toggle")
    async def vampset_toggle(self, ctx):
        """
        Toggle vampire attacks. If they're already enabled, you've got a
        1% chance of actually disabling them. Vamps are tough.
        """
        enabled = await self.config.enabled()
        if not enabled:
            await self.config.enabled.set(not enabled)
            await ctx.send("Vampire attacks have been enabled!")
            return

        chance = random.random()
        if chance >= 0.99:
            await self.config.enabled.set(False)
            await ctx.send("Vamp attacks have been disabled. Would you like to try again?")
        else:
            await ctx.send("The vampires have evaded your attempts to shut them down.")

        loss_chance = random.random()
        if chance < 0.99 and loss_chance <= 0.05:
            balance = await bank.get_balance(ctx.author)
            half = balance // 2
            await bank.set_balance(ctx.author, half)
            await ctx.send(f"The vampires took {half} in retribution for the failed attempt.")
        elif loss_chance > 0.05:
            await ctx.send("You escaped unscathed.")

    @commands.guild_only()
    @vampset.command(name="channel")
    async def vampset_channel(self, ctx, channel: commands.TextChannelConverter = None):
        """
        Sets the reporting channel for the vampire attacks. Defaults to this one.

        Use this command with no channel specified to clear the saved channel for the guild.
        """
        curr_chan = await self.config.guild(ctx.guild).reporting_channel()
        if channel is None:
            if curr_chan is not None:
                await self.config.guild(ctx.guild).clear()
                await ctx.send("Reporting channel cleared.")
                return
            channel = ctx.channel

        await self.config.guild(channel.guild).reporting_channel.set(channel.id)
        await ctx.send("Reporting channel set.")

    @vampset.command(name="count")
    async def vampset_count(self, ctx, count: int):
        """
        Defines the number of attacks per round the vampires make.
        """
        if count < 0:
            count = 5
        if count > 100:
            count = 20

        await self.config.count.set(count)
        await ctx.send(f"Attack count set to {count}.")

    @vampset.command(name="settings")
    async def vampset_settings(self, ctx):
        """
        Show the current settings.
        """
        guild_data = await self.config.guild(ctx.guild).all()
        global_data = await self.config.all()

        reporting_channel = (
            self.bot.get_channel(guild_data["reporting_channel"]).name
            if guild_data["reporting_channel"]
            else "None"
        )
        delay = (
            f"Min: {global_data['min_delay']} minutes / Max: {global_data['max_delay']} minutes"
        )
        wrecklevel = f"Users over {global_data['wrecklevel']} credits"
        max_percent = f"{global_data['max_percent']}% of balance"
        count_plural = "" if global_data["count"] == 1 else "s"
        count = f"{global_data['count']} attack{count_plural}"
        vamp_attacks = "Globally enabled" if global_data["enabled"] else "Globally disabled"

        msg = (
            f"[Vamp attacks]:                {vamp_attacks}\n"
            f"[Vamp attack report channel]:  {reporting_channel}\n"
            f"[Vamp attack count]:           {count}\n"
            f"[Vamp attack max percentage]:  {max_percent}\n"
            f"[Attacks are more cruel to]:   {wrecklevel}\n"
            f"[Vamp attack delay]:           {delay}\n"
        )

        await ctx.send(box(msg, lang="ini"))

    async def calculate_loss(self, balance: int, is_slime: bool = False):
        """
        Get rekt kiddies.
        """
        max_percent = await self.config.max_percent() / 100
        wrecking_min = await self.config.wrecklevel()

        if is_slime:
            max_percent = 0.25

        chance = random.random()

        # raw_loss_percent = ((2**difficulty)**chance - 1) / (2**difficulty - 1)
        if balance <= wrecking_min:
            raw_loss_percent = 0.2 + math.exp(3 * (chance - 0.803))
        else:
            raw_loss_percent = 3 + math.sin(3 * math.pi * chance)

        loss_percent = min(max(max_percent * raw_loss_percent, 0.0025), 0.5)

        ret = max(int(balance * loss_percent), 1)

        gain_chance = random.random()
        if gain_chance >= 0.975:
            ret = -5000

        return ret

    async def attack_global(self, user_dict):
        fucked = []
        if len(user_dict) == 0:
            return fucked

        balance = None
        uid = "1"
        while balance is None:
            uid = random.choice(list(user_dict.keys()))
            balance = user_dict[uid].get("balance")

        is_slime = False
        if str(uid) == "204027971516891136":
            # Get fucked slime
            is_slime = True

        user = self.bot.get_user(uid)
        found = False
        if user is not None:
            uid = user
            found = True

        loss = await self.calculate_loss(balance, is_slime=is_slime)

        fucked.append((None, uid, loss))
        if found:
            uid = uid.id
        await bank._config._get_base_group(Config.USER, str(uid)).balance.set(balance - loss)

        return fucked

    async def attack_guilds(self, member_dict):
        fucked = []
        for guildid, user_dict in member_dict.items():
            if len(user_dict) == 0:
                continue

            balance = None
            uid = "1"
            while balance is None:
                uid = random.choice(list(user_dict.keys()))
                balance = user_dict[uid].get("balance")

            user = self.bot.get_user(uid)
            found = False
            if user is not None:
                uid = user
                found = True

            loss = await self.calculate_loss(balance)

            fucked.append((guildid, uid, loss))

            if found:
                uid = uid.id
            await (
                bank._config._get_base_group(Config.MEMBER, str(guildid), str(uid)).balance.set(
                    balance - loss
                )
            )
        return fucked

    async def report_attacks(self, fucked_list):
        if len(fucked_list) == 0:
            return

        output_list = []
        for gid, user, loss in fucked_list:
            msg = "+ "
            if gid is not None:
                msg += f"GUILD: {gid}, "
            msg += f"USER: {user}: lost {loss}."
            output_list.append(msg)

            if hasattr(user, "id"):
                await self.update_stats(user, loss)
        output_msg = "\n".join(output_list)
        output_msg = f"Vamp Attack by {self.attack_origin} Report:\n" + output_msg
        self.attack_origin = None

        async def report(report_channel):
            for page in pagify(output_msg):
                await report_channel.send(box(page, lang="diff"))

        for g in self.bot.guilds:
            chanid = await self.config.guild(g).reporting_channel()
            channel = self.bot.get_channel(chanid)
            if channel is not None:
                self.bot.loop.create_task(report(channel))

    async def update_stats(self, user, loss):
        hit_count = 1 + await self.config.user(user).hit_count()
        await self.config.user(user).hit_count.set(hit_count)

        if loss > 0:
            loss = loss + await self.config.user(user).loss_total()
            await self.config.user(user).loss_total.set(loss)
        else:
            gain = abs(loss)
            gain = gain + await self.config.user(user).gain_total()
            await self.config.user(user).gain_total.set(gain)

    async def attack(self):
        if await bank.is_global():
            all_accounts = await bank._config.all_users()
            fucked = await self.attack_global(all_accounts)
        else:
            all_accounts = await bank._config.all_members()
            fucked = await self.attack_guilds(all_accounts)
        return fucked

    def reduce_fucked(self, fucked):
        is_global = True
        mid = {}
        for gid, user, loss in fucked:
            if gid is not None:
                is_global = False
            if (gid, user) not in mid:
                mid[(gid, user)] = 0
            mid[(gid, user)] += loss

        if is_global:
            ret = [(gid, user, loss) for (gid, user), loss in mid.items()]
            return sorted(ret, key=lambda x: x[2], reverse=True)
        else:
            mid2 = {}
            for (gid, user), loss in mid.items():
                if gid not in mid2:
                    mid2[gid] = []
                mid2[gid].append((user, loss))

            for gid in mid2.keys():
                mid2[gid] = sorted(mid2[gid], key=lambda x: x[1], reverse=True)
            return [
                (gid, user, loss)
                for gid, userloss_list in mid2.items()
                for user, loss in userloss_list
            ]

    async def vampire_loop(self):
        next_attack = await self.config.next_attack()
        while True:
            while time.time() < next_attack:
                await asyncio.sleep(1)
                next_attack = await self.config.next_attack()

            if self.attack_origin is None:
                self.attack_origin = "Random Vampires"

            if not await self.config.enabled():
                await asyncio.sleep(1)
                continue

            fucked = []
            attack_count = await self.config.count()
            for _ in range(attack_count):
                partial_fucked = await self.attack()
                fucked.extend(partial_fucked)

            reduced_fucked = self.reduce_fucked(fucked)
            await self.report_attacks(reduced_fucked)

            delay = await self.config.delay()
            next_attack = int(time.time()) + delay * 60
            await self.config.next_attack.set(next_attack)

    async def safety_loop(self):
        while True:
            try:
                await self.vampire_loop()
            except asyncio.CancelledError:
                raise
            except:
                log.exception("Vampire loop died, restarting.")
