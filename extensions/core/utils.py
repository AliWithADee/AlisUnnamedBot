from decimal import Decimal, DecimalException, ROUND_HALF_UP
from typing import Optional

from nextcord import Colour, Interaction, User, Embed, ApplicationCommandType, SlashApplicationCommand, SlashOption
from nextcord.ext.commands import Cog

from bot import AlisUnnamedBot
from extensions.core.database import DatabaseCog
from extensions.core.emojis import WALLET, BANK


AMOUNT_DESCRIPTION = 'Any decimal, such as "1.20", a percentage, such as "50%", or "all" to specify all.'


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


# Exactly the same as EmbedError, but is sent with ephemeral=True when caught by the bot events cog
class HiddenEmbedError(EmbedError):
    def __init__(self, *args):
        super().__init__(*args)


# Class that extends SlashOption and sets the "name" attribute to be "item"
# so that this SlashOption is picked up by "setup_item_slash_option_choices()" function in the database cog
class ItemSlashOption(SlashOption):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "item"


# Cog that provides helper functions for other cogs to use
class UtilsCog(AlisUnnamedBotCog):
    def __init__(self, bot: AlisUnnamedBot):
        super().__init__(bot)
        self.currency_symbol = bot.config.get("currency_symbol")

    # Returns whether value can be successfully converted to an integer
    @staticmethod
    def is_int(value) -> bool:
        try:
            int(value)
            return True
        except ValueError:
            return False

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

    # Adds a new user to the database and sends a welcome message as a response to the interaction
    async def add_and_welcome_new_user(self, inter: Interaction, user: User):
        wallet, bank_capacity = await self.database.add_user(user)

        help_command: Optional[SlashApplicationCommand] = self.bot.get_application_command_from_signature(
            "help", ApplicationCommandType.chat_input, None)

        embed = Embed()
        embed.title = "**Hold up there bucko!**"
        embed.colour = self.bot.config.get("colour")
        embed.description = f"Before you run that `/{inter.application_command.name}` command, " \
                            f"I don't believe we've met before, have we?\n" \
                            f"What do they call you then stranger?\n\n" \
                            f"{user.mention} is it? Well hello there, nice to meet you!\n" \
                            f"Let me help you get started. Here take this...\n\n" \
                            f"- You received a {WALLET} **Wallet** containing " \
                            f"`{self.to_currency_str(wallet)}`!\n" \
                            f"- You received a {BANK} **Bank Account** with a capacity of " \
                            f"`{self.to_currency_str(bank_capacity)}`!\n\n" \
                            f"**Consider using the {help_command.get_mention()} command for more information.**"
        await inter.send(embed=embed)


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info("Loading Utils extension...")
    bot.add_cog(UtilsCog(bot))
