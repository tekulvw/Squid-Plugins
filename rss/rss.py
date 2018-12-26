import discord
from discord.ext import commands
import os
import aiohttp
import asyncio
import string
import logging
import copy

from cogs.utils.dataIO import fileIO
from cogs.utils.chat_formatting import *
from __main__ import send_cmd_help

try:
    import feedparser
except:
    feedparser = None

try:
    from bs4 import BeautifulSoup
except:
    BeautifulSoup = None


log = logging.getLogger("data/RSS/feeds.log")


class Settings(object):
    pass


class Feeds(object):
    def __init__(self):
        self.check_folders()
        # {server:{channel:{name:,url:,last_scraped:,template:}}}
        self.feeds = fileIO("data/RSS/feeds.json", "load")

    def save_feeds(self):
        fileIO("data/RSS/feeds.json", "save", self.feeds)

    def check_folders(self):
        if not os.path.exists("data/RSS"):
            print("Creating data/RSS folder...")
            os.makedirs("data/RSS")
        self.check_files()

    def check_files(self):
        f = "data/RSS/feeds.json"
        if not fileIO(f, "check"):
            print("Creating empty feeds.json...")
            fileIO(f, "save", {})

    def update_time(self, server, channel, name, time):
        if server in self.feeds:
            if channel in self.feeds[server]:
                if name in self.feeds[server][channel]:
                    self.feeds[server][channel][name]['last'] = time
                    self.save_feeds()

    async def edit_template(self, ctx, name, template):
        server = ctx.message.server.id
        channel = ctx.message.channel.id
        if server not in self.feeds:
            return False
        if channel not in self.feeds[server]:
            return False
        if name not in self.feeds[server][channel]:
            return False
        self.feeds[server][channel][name]['template'] = template
        self.save_feeds()
        return True

    async def edit_filter(self, ctx, name, filters):
        server = ctx.message.server.id
        channel = ctx.message.channel.id
        if server not in self.feeds:
            return False
        if channel not in self.feeds[server]:
            return False
        if name not in self.feeds[server][channel]:
            return False
        self.feeds[server][channel][name]['filter'] = filters.split(',')
        self.save_feeds()
        return True

    async def reset_filter(self, ctx, name):
        server = ctx.message.server.id
        channel = ctx.message.channel.id
        if server not in self.feeds:
            return False
        if channel not in self.feeds[server]:
            return False
        if name not in self.feeds[server][channel]:
            return False
        self.feeds[server][channel][name]['filter'] = [""]
        self.save_feeds()
        return True

    def add_feed(self, ctx, name, url):
        server = ctx.message.server.id
        channel = ctx.message.channel.id
        if server not in self.feeds:
            self.feeds[server] = {}
        if channel not in self.feeds[server]:
            self.feeds[server][channel] = {}
        self.feeds[server][channel][name] = {}
        self.feeds[server][channel][name]['url'] = url
        self.feeds[server][channel][name]['last'] = ""
        self.feeds[server][channel][name]['template'] = "$name:\n$title"
        self.feeds[server][channel][name]['filter'] = [""]
        self.save_feeds()

    async def delete_feed(self, ctx, name):
        server = ctx.message.server.id
        channel = ctx.message.channel.id
        if server not in self.feeds:
            return False
        if channel not in self.feeds[server]:
            return False
        if name not in self.feeds[server][channel]:
            return False
        del self.feeds[server][channel][name]
        self.save_feeds()
        return True

    def get_feed_names(self, server):
        if isinstance(server, discord.Server):
            server = server.id
        ret = []
        if server in self.feeds:
            for channel in self.feeds[server]:
                ret = ret + list(self.feeds[server][channel].keys())
        return ret

    def get_copy(self):
        return self.feeds.copy()


class RSS(object):
    def __init__(self, bot):
        self.bot = bot

        self.settings = Settings()
        self.feeds = Feeds()
        self.session = aiohttp.ClientSession()

    def __unload(self):
        self.session.close()

    def get_channel_object(self, channel_id):
        channel = self.bot.get_channel(channel_id)
        if channel and \
                channel.permissions_for(channel.server.me).send_messages:
            return channel
        return None

    async def _get_feed(self, url):
        text = None
        try:
            with aiohttp.ClientSession() as session:
                with aiohttp.Timeout(3):
                    async with session.get(url) as r:
                        text = await r.text()
        except:
            pass
        return text

    async def valid_url(self, url):
        text = await self._get_feed(url)
        rss = feedparser.parse(text)
        if rss.bozo:
            return False
        else:
            return True

    @commands.group(pass_context=True)
    async def rss(self, ctx):
        """RSS feed stuff"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @rss.command(pass_context=True, name="add")
    async def _rss_add(self, ctx, name: str, url: str):
        """Add an RSS feed to the current channel"""
        channel = ctx.message.channel
        valid_url = await self.valid_url(url)
        if valid_url:
            self.feeds.add_feed(ctx, name, url)
            await self.bot.send_message(
                channel,
                'Feed "{}" added. Modify the template using'
                ' rss template'.format(name))
        else:
            await self.bot.send_message(
                channel,
                'Invalid or unavailable URL.')

    @rss.command(pass_context=True, name="list")
    async def _rss_list(self, ctx):
        """List currently running feeds"""
        msg = "Available Feeds:\n\t"
        msg += "\n\t".join(self.feeds.get_feed_names(ctx.message.server))
        await self.bot.say(box(msg))

    @rss.command(pass_context=True, name="template")
    async def _rss_template(self, ctx, feed_name: str, *, template: str):
        ("""Set a template for the feed alert

        Each variable must start with $, valid variables:
        \tauthor, author_detail, comments, content, contributors, created,"""
         """ create, link, name, published, published_parsed, publisher,"""
         """ publisher_detail, source, summary, summary_detail, tags, title,"""
         """ title_detail, updated, updated_parsed""")
        template = template.replace("\\t", "\t")
        template = template.replace("\\n", "\n")
        success = await self.feeds.edit_template(ctx, feed_name, template)
        if success:
            await self.bot.say("Template added successfully.")
        else:
            await self.bot.say('Feed not found!')

    @rss.command(pass_context=True, name="filter")
    async def _rss_filter(self, ctx, feed_name: str, *, filters: str):
        ("""Set a filter for the feed alert
        set a comma-seperated list of keywords for filterung feeds.

        Negation is done by a leading '!'
        Example:
        [p]rss filter rss_name news,!computer,games""")
        success = await self.feeds.edit_filter(ctx, feed_name, filters)
        if success:
            await self.bot.say("Filter added successfully.")
        else:
            await self.bot.say('Feed not found!')

    @rss.command(pass_context=True, name="filter_reset")
    async def _rss_filter_reset(self, ctx, feed_name: str):
        """Disables filtering"""
        success = await self.feeds.reset_filter(ctx, feed_name)
        if success:
            await self.bot.say("Filter reseted successfully.")
        else:
            await self.bot.say('Feed not found!')

    @rss.command(pass_context=True, name="force")
    async def _rss_force(self, ctx, feed_name: str):
        """Forces a feed alert"""
        server = ctx.message.server
        channel = ctx.message.channel
        feeds = self.feeds.get_copy()
        if server.id not in feeds:
            await self.bot.say("There are no feeds for this server.")
            return
        if channel.id not in feeds[server.id]:
            await self.bot.say("There are no feeds for this channel.")
            return
        if feed_name not in feeds[server.id][channel.id]:
            await self.bot.say("That feedname doesn't exist.")
            return

        items = copy.deepcopy(feeds[server.id][channel.id][feed_name])
        items['last'] = ''

        message = await self.get_current_feed(server.id, channel.id,
                                              feed_name, items)
        if message is not None:
            await self.bot.say(message)
        else:
            await self.bot.say("Filter didn\'t match.")

    @rss.command(pass_context=True, name="remove")
    async def _rss_remove(self, ctx, name: str):
        """Removes a feed from this server"""
        success = await self.feeds.delete_feed(ctx, name)
        if success:
            await self.bot.say('Feed deleted.')
        else:
            await self.bot.say('Feed not found!')

    async def get_current_feed(self, server, chan_id, name, items):
        log.debug("getting feed {} on sid {}".format(name, server))
        url = items['url']
        last_title = items['last']
        template = items['template']

        filters_contains = list()
        filters_containsnot = list()
        for i in list(items['filter']):
            if i.startswith('!'):
                filters_containsnot.append(i[1:])
            else:
                filters_contains.append(i)
        message = None

        try:
            async with self.session.get(url) as resp:
                html = await resp.read()
        except:
            log.exception("failure accessing feed at url:\n\t{}".format(url))
            return None

        rss = feedparser.parse(html)
        rss.entries[0]['description'] = BeautifulSoup(rss.entries[0]['description'].replace('<br>', '\n'), 'html5lib').get_text()

        if rss.bozo:
            log.debug("Feed at url below is bad.\n\t".format(url))
            return None

        try:
            curr_title = rss.entries[0].title
        except IndexError:
            log.debug("no entries found for feed {} on sid {}".format(
                name, server))
            return message

        if curr_title != last_title:
            log.debug("New entry found for feed {} on sid {}".format(
                name, server))
            latest = rss.entries[0]
            to_fill = string.Template(template)

            filter_positive = True
            filter_negative = True
            if filters_contains:
                if not any(word in curr_title for word in filters_contains):
                    filter_positive = False
            if filters_containsnot:
                if any(word in curr_title for word in filters_containsnot):
                    filter_negative = False
            if filter_positive and filter_negative:
                message = to_fill.safe_substitute(
                    name=bold(name),
                    **latest
                )

            self.feeds.update_time(
                server, chan_id, name, curr_title)

        return message

    async def read_feeds(self):
        await self.bot.wait_until_ready()
        while self == self.bot.get_cog('RSS'):
            feeds = self.feeds.get_copy()
            for server in feeds:
                for chan_id in feeds[server]:
                    for name, items in feeds[server][chan_id].items():
                        log.debug("checking {} on sid {}".format(name, server))
                        channel = self.get_channel_object(chan_id)
                        if channel is None:
                            log.debug("response channel not found, continuing")
                            continue
                        msg = await self.get_current_feed(server, chan_id,
                                                          name, items)
                        if msg is not None:
                            await self.bot.send_message(channel, msg)
            await asyncio.sleep(300)


def setup(bot):
    if feedparser is None:
        raise NameError("You need to run `pip3 install feedparser`")
    if BeautifulSoup is None:
        raise NameError("You need to run `pip3 install beautifulsoup4`")
    n = RSS(bot)
    bot.add_cog(n)
    bot.loop.create_task(n.read_feeds())
