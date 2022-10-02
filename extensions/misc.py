from nextcord import slash_command, Interaction, Embed, Colour
from nextcord.ext.application_checks import is_owner

from bot import AlisUnnamedBot
from extensions.core.emojis import TICK, WARNING, LOADING
from extensions.core.utils import AlisUnnamedBotCog


class MiscCog(AlisUnnamedBotCog):
    def __init__(self, bot: AlisUnnamedBot):
        super().__init__(bot)

    @slash_command(description="Ping the bot.")
    async def ping(self, inter: Interaction):
        embed = Embed()
        embed.title = "**Pong!** :ping_pong: "
        embed.colour = self.bot.config.get("colour")
        embed.description = f"Received response after `{self.bot.latency * 1000:.2f}ms`"
        await inter.send(embed=embed)

    @is_owner()
    @slash_command(description="Reload the bot.")
    async def reload(self, inter: Interaction):
        # Defer response
        await inter.response.defer()

        # Embed: Loading bot config...
        embed = Embed()
        embed.title = "**Reload**"
        embed.colour = self.bot.config.get("colour")
        config_text = f"{LOADING} *Reloading bot config...*"
        embed.description = config_text
        await inter.send(embed=embed)

        # Load bot config
        config_loaded = self.bot.load_config()

        # Embed: Bot config result + Loading extensions...
        if config_loaded:
            config_text = f"{TICK} Bot config reloaded!"
        else:
            config_text = f"{WARNING} Failed to load bot config!"
        extensions_text = f"{LOADING} *Reloading extensions...*"
        separator = "\n"
        embed.description = separator.join([config_text, extensions_text])
        await inter.edit_original_message(embed=embed)

        # Reload extensions
        failed_extensions = await self.bot.reload_extensions()
        loaded_extensions = list(self.bot.extensions)

        # Embed: Extensions result + Syncing commands...
        if failed_extensions:
            extensions_text = f"{WARNING} Extensions reloaded with errors!"
        else:
            extensions_text = f"{TICK} Extensions reloaded!"
        app_commands_text = f"{LOADING} *Syncing application commands...*"
        embed.description = separator.join([config_text, extensions_text, app_commands_text])
        await inter.edit_original_message(embed=embed)

        # Sync application commands
        try:
            await self.bot.sync_application_commands()
            commands_synced = True
        except Exception as error:
            self.bot.logger.error(error)
            commands_synced = False

        # Embed: Syncing commands result
        if commands_synced:
            app_commands_text = f"{TICK} Application commands synced!"
        else:
            app_commands_text = f"{WARNING} Failed to sync application commands!"
        embed.description = separator.join([config_text, extensions_text, app_commands_text])
        await inter.edit_original_message(embed=embed)

        # Embed: Final results
        if loaded_extensions:
            embed.add_field(name=f"{TICK} The following extensions have been loaded",
                            value="`" + "`\n`".join(loaded_extensions) + "`",
                            inline=False)
        if failed_extensions:
            embed.add_field(name=f"{WARNING} The following extensions failed to load",
                            value="`" + "`\n`".join(failed_extensions) + "`",
                            inline=False)
        if failed_extensions or (not config_loaded) or (not commands_synced):
            embed.colour = Colour.yellow()
        else:
            embed.colour = Colour.green()

        await inter.edit_original_message(embed=embed)

    @slash_command(description="Shows useful information about each feature of the bot.")
    async def help(self, inter: Interaction):
        embed = Embed()
        embed.title = "**Help**"
        embed.colour = self.bot.config.get("colour")
        embed.description = f"Help stuff here..."
        await inter.send(embed=embed)


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info(f"Loading Misc extension...")
    bot.add_cog(MiscCog(bot))
