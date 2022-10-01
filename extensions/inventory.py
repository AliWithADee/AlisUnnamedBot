from typing import Optional

from nextcord import slash_command, Interaction, User, SlashOption, Embed

from bot import AlisUnnamedBot
from extensions.core.database import BAG, HOME
from extensions.core.emojis import BACKPACK
from extensions.core.utils import AlisUnnamedBotCog, EmbedError
from extensions.user import UserDoesNotExistError

IN_BAG = f"*- In {BACKPACK} **Bag***"


class BotsDoNotHaveInventoriesError(EmbedError):
    def __init__(self):
        super().__init__("**Invalid Argument**",
                         f"Bots don't have inventories")


class InventoryCog(AlisUnnamedBotCog):
    def __init__(self, bot: AlisUnnamedBot):
        super().__init__(bot)

    @slash_command(description="View your own, or another user's, inventory.")
    async def inventory(self, inter: Interaction,
                        user: Optional[User] = SlashOption(
                            required=False,
                            description="You may specify a user to view their inventory."
                        )):
        if not await self.database.user_exists(inter.user):
            return await self.utils.add_and_welcome_new_user(inter, inter.user)
        elif not user:
            user = inter.user
        elif user.bot:
            raise BotsDoNotHaveInventoriesError
        elif not await self.database.user_exists(user):
            raise UserDoesNotExistError(user)
        inventory = await self.database.get_user_inventory(user)

        if inventory:
            item_list = []
            for item in inventory:
                item_id = item.get("itemId")
                location = item.get("location", HOME)
                if await self.database.item_is_unique(item_id):
                    quantity = 1
                    name = item.get("name", await self.database.get_item_single_name(item_id))
                else:
                    quantity = item.get("quantity", 1)
                    name = await self.database.get_item_single_name(item_id) if quantity == 1 \
                        else await self.database.get_item_plural_name(item_id)

                item_desc = f"`{quantity}` **{name}**"
                item_list.append(item_desc + f" {IN_BAG}" if location == BAG else item_desc)

            embed_desc = "- " + "\n- ".join(item_list)
        else:
            subject = "Your" if user.id == inter.user.id else f"{user.mention}'s"
            embed_desc = f"*{subject} inventory is empty*"

        embed = Embed()
        embed.set_author(name=f"{user.name}'s Inventory", icon_url=user.avatar.url)
        embed.colour = self.bot.config.get("colour")
        embed.description = embed_desc
        await inter.send(embed=embed)

    @slash_command(description="View the contents of your own, or another user's, bag.")
    async def bag(self, inter: Interaction,
                  user: Optional[User] = SlashOption(
                      required=False,
                      description="You may specify a user to view the contents of their bag."
                  )):
        if not await self.database.user_exists(inter.user):
            return await self.utils.add_and_welcome_new_user(inter, inter.user)
        elif not user:
            user = inter.user
        elif user.bot:
            raise BotsDoNotHaveInventoriesError
        elif not await self.database.user_exists(user):
            raise UserDoesNotExistError(user)
        bag = await self.database.get_user_bag(user)

        if bag:
            item_list = []
            for item in bag:
                item_id = item.get("itemId")
                if await self.database.item_is_unique(item_id):
                    quantity = 1
                    name = item.get("name", await self.database.get_item_single_name(item_id))
                else:
                    quantity = item.get("quantity", 1)
                    name = await self.database.get_item_single_name(item_id) if quantity == 1 \
                        else await self.database.get_item_plural_name(item_id)

                item_list.append(f"`{quantity}` **{name}**")

            embed_desc = "- " + "\n- ".join(item_list)
        else:
            subject = "Your" if user.id == inter.user.id else f"{user.mention}'s"
            embed_desc = f"*{subject} bag is empty*"

        embed = Embed()
        embed.set_author(name=f"{user.name}'s Bag", icon_url=user.avatar.url)
        embed.colour = self.bot.config.get("colour")
        embed.description = embed_desc
        await inter.send(embed=embed)


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info(f"Loading Inventory extension...")
    bot.add_cog(InventoryCog(bot))
