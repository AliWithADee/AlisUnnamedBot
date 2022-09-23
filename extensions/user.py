from typing import Optional

from nextcord import slash_command, Interaction, User, SlashOption, Embed

from bot import AlisUnnamedBot
from extensions.core.utilities import AlisUnnamedBotCog, EmbedError


class BotsDoNotHaveProfilesError(EmbedError):
    def __init__(self):
        super().__init__("**Invalid Argument**",
                         f"Bots don't have user profiles")


class UserCog(AlisUnnamedBotCog):
    def __init__(self, bot: AlisUnnamedBot):
        super().__init__(bot)

    @slash_command(description="View your own, or another user's, profile.")
    async def profile(self, inter: Interaction,
                      user: Optional[User] = SlashOption(
                          required=False,
                          description="You may specify a user to see their profile."
                      )):
        if not user:
            user = inter.user
        if user.bot:
            raise BotsDoNotHaveProfilesError
        profile = await self.database.get_user_profile(user)
        level = profile.get("Level")
        wallet = profile.get("Wallet")
        bank = profile.get("Bank")

        embed = Embed()
        embed.set_author(name=f"{user.name}'s Profile", icon_url=user.avatar.url)
        embed.colour = self.bot.config.get("colour")
        embed.description = f"**Level: `{level}`**\n" \
                            f"**Total Balance: `{self.utils.to_currency_str(wallet + bank)}`**"
        await inter.send(embed=embed)

    @slash_command(description="View your own, or another user's, level.")
    async def level(self, inter: Interaction,
                    user: Optional[User] = SlashOption(
                        required=False,
                        description="You may specify a user to see their level."
                    )):
        if not user:
            user = inter.user
        if user.bot:
            raise BotsDoNotHaveProfilesError
        level_data = await self.database.get_user_level_data(user)
        level = level_data.get("Level")
        exp = level_data.get("Exp")

        embed = Embed()
        embed.set_author(name=f"{user.name}'s Level", icon_url=user.avatar.url)
        embed.colour = self.bot.config.get("colour")
        embed.description = f"**Level: `{level}`**\n**Exp: `{exp}`**"
        await inter.send(embed=embed)


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info(f"Loading User extension...")
    bot.add_cog(UserCog(bot))
