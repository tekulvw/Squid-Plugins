import asyncio
import random
import time
import logging

from redbot.core import bank
from redbot.core import commands, Config
from redbot.core.utils import box

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
            "min_delay": 30,  # minutes
            "delay": 60,  # minutes
            "max_delay": 180,  # minutes
            "difficulty": 81,  # 1 to 100
            "max_percent": 5,
            "reporting_channel": None,
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
        }
        self.config.register_user(**user_defaults)

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
        await self.config.next_attack.set(0)

        await ctx.send(f"Congratulations, you spent {cost} to make the vampires attack.")

    @commands.command()
    async def vampstat(self, ctx, user: commands.UserConverter = None):
        if user is None:
            user = ctx.author
        hit_count = await self.config.user(user).hit_count()
        loss_total = await self.config.user(user).loss_total()
        gain_total = await self.config.user(user).gain_total()

        await ctx.send(
            f"Over the course of your short life you've been attacked {hit_count} times, lost {loss_total}"
            f" and gained {gain_total}."
        )

    @commands.group()
    async def vampset(self, ctx):
        pass

    @vampset.command(name="percent")
    async def vampset_percent(self, ctx, percent: int):
        """
        Sets the percentage of a users balance they could lose.

        This value should be between 0 and 100.
        Difficulty affects the chance they lose close to this percent.
        """
        if percent <= 0:
            percent = 5
        elif percent >= 100:
            percent = 5

        await self.config.max_percent.set(percent)
        await ctx.send(f"Vamp percent set to {percent}%.")

    @vampset.command(name="difficulty")
    async def vampset_difficulty(self, ctx, difficulty: int):
        """
        Sets the difficulty.

        The higher the difficulty the more likely a user is to lose a higher
        percentage of their balance.
        This should be between 1 and 100.
        """
        if difficulty < 1:
            difficulty = 50
        elif difficulty > 100:
            difficulty = 100

        await self.set_difficulty(difficulty)
        await ctx.send(f"Difficulty set to {difficulty}.")

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

    @vampset.command(name="channel", no_pm=True)
    async def vampset_channel(self, ctx, channel: commands.TextChannelConverter = None):
        """
        Sets the global reporting channel. Defaults to this one.
        """
        if channel is None:
            channel = ctx.channel
        await self.config.reporting_channel.set(channel.id)
        await ctx.send("Global channel set.")

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

    async def get_difficulty(self):
        return 101 - await self.config.difficulty()

    async def set_difficulty(self, difficulty):
        await self.config.difficulty.set(difficulty)

    async def calculate_loss(self, balance: int):
        """
        Get rekt kiddies.
        """
        max_percent = await self.config.max_percent() / 100
        difficulty = await self.get_difficulty()

        chance = random.random()

        raw_loss_percent = ((2**difficulty)**chance - 1) / (2**difficulty - 1)
        loss_percent = max(max_percent * raw_loss_percent, 0.01)

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

        user = self.bot.get_user(uid)
        found = False
        if user is not None:
            uid = user
            found = True

        loss = await self.calculate_loss(balance)

        fucked.append((None, uid, loss))
        if found:
            uid = uid.id
        await bank._conf._get_base_group(Config.USER, str(uid)).balance.set(balance - loss)

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
                bank._conf._get_base_group(Config.MEMBER, str(guildid), str(uid))
                .balance.set(balance - loss)
            )
        return fucked

    async def report_attacks(self, fucked_list):
        if len(fucked_list) == 0:
            return

        global_report_id = await self.config.reporting_channel()
        report_channel = self.bot.get_channel(global_report_id)
        if report_channel is None:
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
        output_msg = "Vamp Attack Report:\n" + output_msg

        for page in pagify(output_msg):
            await report_channel.send(box(page, lang="diff"))

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
            all_accounts = await bank._conf.all_users()
            fucked = await self.attack_global(all_accounts)
        else:
            all_accounts = await bank._conf.all_members()
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
            return [(gid, user, loss) for gid, userloss_list in mid2.items() for user, loss in userloss_list]

    async def vampire_loop(self):
        next_attack = await self.config.next_attack()
        while True:
            while time.time() < next_attack:
                await asyncio.sleep(1)
                next_attack = await self.config.next_attack()

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
            except:
                log.exception("Vampire loop died, restarting.")
