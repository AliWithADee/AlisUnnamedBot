from typing import Optional

from nextcord import slash_command, Interaction, User, SlashOption, Embed

from bot import AlisUnnamedBot
from extensions.core.utils import AlisUnnamedBotCog, EmbedError


class BotsDoNotHaveProfilesError(EmbedError):
    def __init__(self):
        super().__init__("**Invalid Argument**",
                         f"Bots don't have user profiles")


class UserDoesNotExistError(EmbedError):
    def __init__(self, user: User):
        super().__init__("**Invalid Argument**",
                         f"Who the hell is {user.mention}? I don't recognise that user in my database!\n\n"
                         f"*Get your friend to use the bot, in order to interact with them...*")


class UserCog(AlisUnnamedBotCog):
    def __init__(self, bot: AlisUnnamedBot):
        super().__init__(bot)

    @slash_command(description="View your own, or another user's, profile.")
    async def profile(self, inter: Interaction,
                      user: Optional[User] = SlashOption(
                          required=False,
                          description="You may specify a user to see their profile."
                      )):
        if not await self.database.user_exists(inter.user):
            return await self.utils.add_and_welcome_new_user(inter, inter.user)
        elif not user:
            user = inter.user
        elif user.bot:
            raise BotsDoNotHaveProfilesError
        elif not await self.database.user_exists(user):
            raise UserDoesNotExistError(user)
        profile = await self.database.get_user_profile(user)
        level = profile.get("level")
        wallet = profile.get("wallet")
        bank = profile.get("bank")

        embed = Embed()
        embed.set_author(name=f"{user.name}'s Profile", icon_url=user.avatar.url)
        embed.colour = self.bot.config.get("colour")
        embed.set_thumbnail(user.avatar.url)
        embed.description = f"**Level: `{level}`**\n" \
                            f"**Total Balance: `{self.utils.to_currency_str(wallet + bank)}`**"
        await inter.send(embed=embed)

    @slash_command(description="View your own, or another user's, level.")
    async def level(self, inter: Interaction,
                    user: Optional[User] = SlashOption(
                        required=False,
                        description="You may specify a user to see their level."
                    )):
        if not await self.database.user_exists(inter.user):
            return await self.utils.add_and_welcome_new_user(inter, inter.user)
        elif not user:
            user = inter.user
        elif user.bot:
            raise BotsDoNotHaveProfilesError
        elif not await self.database.user_exists(user):
            raise UserDoesNotExistError(user)
        level_data = await self.database.get_user_level_data(user)
        level = level_data.get("level")
        exp = level_data.get("exp")

        embed = Embed()
        embed.set_author(name=f"{user.name}'s Level", icon_url=user.avatar.url)
        embed.colour = self.bot.config.get("colour")
        embed.description = f"**Level: `{level}`**\n**Exp: `{exp}`**"
        await inter.send(embed=embed)


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info(f"Loading User extension...")
    bot.add_cog(UserCog(bot))
