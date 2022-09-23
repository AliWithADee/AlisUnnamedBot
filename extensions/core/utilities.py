from decimal import Decimal, DecimalException, ROUND_HALF_UP
from typing import Optional

from nextcord import Colour
from nextcord.ext.commands import Cog

from bot import AlisUnnamedBot
from extensions.core.database import DatabaseCog


# Base class for certain cogs that need access to the Utils and Database cogs
class AlisUnnamedBotCog(Cog):
    def __init__(self, bot: AlisUnnamedBot):
        self.bot = bot
        self.utils: Optional[UtilsCog] = None
        self.database: Optional[DatabaseCog] = None


# Base class for errors that should be sent back to the user via a discord embed
# Handled by the error handler found in extensions.core.bot_events
class EmbedError(Exception):
    def __init__(self, embed_title: str, embed_desc: str, embed_colour: int = Colour.red()):
        self.embed_title = embed_title
        self.embed_desc = embed_desc
        self.embed_colour = embed_colour
        super().__init__(embed_desc.replace("*", "").replace("`", "'"))


# Cog that provides helper functions for other cogs to use
class UtilsCog(Cog):
    def __init__(self, bot: AlisUnnamedBot):
        self.bot = bot
        self.currency_symbol = bot.config.get("currency_symbol")

    # Returns whether value can be successfully converted to a Decimal
    @staticmethod
    def is_decimal(value) -> bool:
        try:
            Decimal(str(value))
            return True
        except DecimalException:
            return False

    # Returns value as a Decimal, if value can be converted to a Decimal, else returns "0" as a Decimal
    @staticmethod
    def to_decimal(value) -> Decimal:
        if UtilsCog.is_decimal(value):
            return Decimal(str(value))
        return Decimal("0")

    # Returns whether value is a string formatted to represent a percentage, such as "50%" or "33.3%"
    @staticmethod
    def is_percentage(value) -> bool:
        if isinstance(value, str):
            if value.endswith("%"):
                if UtilsCog.is_decimal(value.replace("%", "")):
                    return True
        return False

    # Returns value as a Decimal with "0.01" as its exponent, if value can be converted to a Decimal,
    # else returns "0" as a Decimal with "0.01" as its exponent
    @staticmethod
    def to_currency_value(value) -> Decimal:
        return UtilsCog.to_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Returns value as a string with currency formatting applied, if value can be converted to a Decimal,
    # else returns "0" as a string with currency formatting applied
    def to_currency_str(self, value) -> str:
        return self.currency_symbol + "{:,}".format(self.to_currency_value(value))


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info("Loading Utilities extension...")
    bot.add_cog(UtilsCog(bot))
