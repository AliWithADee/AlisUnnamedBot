from nextcord import ApplicationInvokeError, Interaction, Embed, Colour
from nextcord.ext.application_checks import ApplicationNotOwner
from nextcord.ext.commands import Cog

from bot import AlisUnnamedBot
from extensions.core.utilities import EmbedError
from extensions.core.emojis import CROSS


# Cog to handle bot events, such as error handling
class BotEventsCog(Cog):
    def __init__(self, bot: AlisUnnamedBot):
        self.bot = bot

    @Cog.listener()
    async def on_application_command_error(self, inter: Interaction, error):
        error_embed = Embed()
        if isinstance(error, ApplicationInvokeError):
            if isinstance(error.original, EmbedError):
                error_embed.title = error.original.embed_title
                error_embed.colour = error.original.embed_colour
                error_embed.description = f"{CROSS} {error.original.embed_desc}"
                await inter.send(embed=error_embed)
        elif isinstance(error, ApplicationNotOwner):
            error_embed.title = "**Missing Permissions**"
            error_embed.colour = Colour.red()
            error_embed.description = f"{CROSS} You must be the owner of the bot to use this command!"
            await inter.send(embed=error_embed)
        if not inter.response.is_done():
            try:
                error_embed.title = "**Application Command Error**"
                error_embed.colour = Colour.red()
                error_embed.description = f"{CROSS} {error}"
                await inter.send(embed=error_embed)
            finally:
                raise error


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info("Loading Bot Events extension...")
    bot.add_cog(BotEventsCog(bot))
