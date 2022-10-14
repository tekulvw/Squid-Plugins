import contextlib
import logging
import tabulate

from redbot.core import commands, Config
from redbot.core.utils import chat_formatting
from redbot.core.utils.chat_formatting import humanize_list

try:
    from red_commons.logging  import VERBOSE, TRACE
except ImportError:
    VERBOSE = logging.DEBUG - 3
    TRACE = logging.DEBUG - 5

log = logging.getLogger("red.cogs.Squid-Plugins.Logger")


class Logger(commands.Cog):
    LOGGER_CATEGORY = "LOGGER"

    def __init__(self, bot):
        super().__init__()

        self.conf = Config.get_conf(self, 6133)

        logger_defaults = {
            "override": None,
            "original": None,
        }

        self.conf.init_custom(self.LOGGER_CATEGORY, 1)

        self.conf.register_custom(
            self.LOGGER_CATEGORY,
            **logger_defaults
        )

        self.level_map = {
            logging.CRITICAL: "Critical",
            logging.ERROR: "Error",
            logging.WARNING: "Warning",
            logging.INFO: "Info",
            logging.DEBUG: "Debug",
            VERBOSE: "Verbose",
            TRACE: "Trace",
            logging.NOTSET: "Not set"
        }

        self.name_to_int_map = {v.lower().replace(" ", ""): k for k, v in self.level_map.items()}

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete."""
        return

    async def refresh_levels(self):
        all_data = await self.conf.custom(self.LOGGER_CATEGORY).all()
        for name, data in all_data.items():
            logger = logging.getLogger(name)
            level = data['override']
            log.debug("refresh_levels - Setting %s to %s", name, level)
            logger.setLevel(level)

    def _available_loggers(self):
        loggers = logging.Logger.manager.loggerDict.keys()
        return sorted(l for l in loggers if l.split('.')[0] in ('red', 'discord'))

    def _int_to_name(self, level_int):
        return self.level_map.get(level_int, "Unknown")

    def _name_to_int(self, level_name: str):
        with contextlib.suppress(ValueError):
            if level_name.isdigit() and int(level_name) in self.level_map:
                return int(level_name)

        if level_name.lower().replace(" ", "") in self.name_to_int_map:
            value = self.name_to_int_map[level_name.lower().replace(" ", "")]
            return value
        raise AttributeError

    def _loggers_with_levels(self):
        loggers = self._available_loggers()

        levels = [logging.getLogger(l).getEffectiveLevel() for l in loggers]
        levels = [self._int_to_name(l) for l in levels]

        return zip(loggers, levels)

    def _get_logger(self, name):
        for logger, _ in self._loggers_with_levels():
            if name == logger:
                return logging.getLogger(name)

    async def _set_level(self, logger, level):
        curr_level = logger.getEffectiveLevel()

        group = self.conf.custom(self.LOGGER_CATEGORY, logger.name)

        curr_default = await group.original()

        if curr_default is None:
            await group.original.set(curr_level)
        log.debug("_set_level - Setting %s to %s", logger.name, level)
        await group.override.set(level)

        logger.setLevel(level)

    @commands.group()
    @commands.is_owner()
    async def logger(self, ctx):
        """
        Commands for modifying logging levels.
        """
        pass

    @logger.command(name='list')
    async def logger_list(self, ctx):
        """
        List available loggers.
        """
        data = self._loggers_with_levels()
        headers = ['Logger', 'Level']
        msg = tabulate.tabulate(data, headers, tablefmt='psql')
        for page in chat_formatting.pagify(msg, delims="\n", shorten_by=10):
            await ctx.send(chat_formatting.box(page))

    @logger.command(name='setlevel')
    async def logger_setlevel(self, ctx, name: str, level: str):
        """
        Set a specific log level.
        """
        curr_log = self._get_logger(name)
        if curr_log is None:
            await ctx.send("That logger is either unaccessible or does not exist.")
            return

        try:
            to_level = self._name_to_int(level)
        except AttributeError:
            await ctx.send(f"Invalid level, levels are {humanize_list(list(self.name_to_int_map.keys()))}")
            return

        await self._set_level(curr_log, to_level)
        await ctx.tick()
