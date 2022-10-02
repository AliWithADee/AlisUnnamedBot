from typing import Optional

from bson import ObjectId
from nextcord import slash_command, Interaction, User, SlashOption, Embed, Colour

from bot import AlisUnnamedBot
from extensions.core.database import BAG, HOME
from extensions.core.emojis import BACKPACK
from extensions.core.utils import AlisUnnamedBotCog, EmbedError, ItemSlashOption, AMOUNT_DESCRIPTION
from extensions.user import UserDoesNotExistError

IN_BAG = f"- ***In {BACKPACK} Bag***"


class BotsDoNotHaveInventoriesError(EmbedError):
    def __init__(self):
        super().__init__("**Invalid Argument**",
                         f"Bots don't have inventories")


class InvalidItemAmountError(EmbedError):
    def __init__(self, amount):
        super().__init__("**Invalid Argument**",
                         f"`{amount}` is not a valid amount of items")


class ItemAmountTooLowError(EmbedError):
    def __init__(self, greater_than: int = 0):
        super().__init__("**Invalid Argument**",
                         f"Amount of items must be greater than `{greater_than}`")


class InsufficientBelongings(EmbedError):
    def __init__(self, item_name: str, amount: int):
        super().__init__("**Insufficient Belongings**",
                         f"You don't have `{amount}` **{item_name}**")


class InventoryCog(AlisUnnamedBotCog):
    def __init__(self, bot: AlisUnnamedBot):
        super().__init__(bot)

    @slash_command(description="View your own, or another user's, inventory.")
    async def inventory(self, inter: Interaction,
                        user: Optional[User] = SlashOption(
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

        item_list = []
        for item in inventory:
            item_id = item.get("itemId")
            location = item.get("location", HOME)
            if await self.database.item_is_unique(item_id):
                quantity = 1
                name = item.get("name", await self.database.get_item_single_name(item_id))
            else:
                quantity = item.get("quantity", 0)
                name = await self.database.get_item_single_name(item_id) if quantity == 1 \
                    else await self.database.get_item_plural_name(item_id)

            if quantity > 0:
                item_desc = f"`{quantity}` **{name}**"
                item_list.append(item_desc + f" {IN_BAG}" if location == BAG else item_desc)

        if item_list:
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

        item_list = []
        for item in bag:
            item_id = item.get("itemId")
            if await self.database.item_is_unique(item_id):
                quantity = 1
                name = item.get("name", await self.database.get_item_single_name(item_id))
            else:
                quantity = item.get("quantity", 0)
                name = await self.database.get_item_single_name(item_id) if quantity == 1 \
                    else await self.database.get_item_plural_name(item_id)

            if quantity > 0:
                item_list.append(f"`{quantity}` **{name}**")

        if item_list:
            embed_desc = "- " + "\n- ".join(item_list)
        else:
            subject = "Your" if user.id == inter.user.id else f"{user.mention}'s"
            embed_desc = f"*{subject} {BACKPACK} **Bag** is empty*"

        embed = Embed()
        embed.set_author(name=f"{user.name}'s Bag", icon_url=user.avatar.url)
        embed.colour = self.bot.config.get("colour")
        embed.description = embed_desc
        await inter.send(embed=embed)

    @slash_command(description="Transfer items from your inventory to your bag.")
    async def bring(self, inter: Interaction,
                    amount: str = SlashOption(
                        description=AMOUNT_DESCRIPTION
                    ),
                    item_id_string: str = ItemSlashOption(
                        description="The item you wish to bring with you."
                    )):
        user = inter.user
        if not await self.database.user_exists(user):
            return await self.utils.add_and_welcome_new_user(inter, user)

        item_id = ObjectId(item_id_string)
        total_quantity = await self.database.get_user_item_quantity(user, item_id)

        if amount.lower() == "all":
            brought = total_quantity
        elif self.utils.is_int(amount):
            brought = int(amount)
        elif self.utils.is_percentage(amount):
            multiplier = self.utils.to_decimal(amount.replace("%", "")) / 100
            brought = int(total_quantity * multiplier)
        else:
            raise InvalidItemAmountError(amount)

        item_name = await self.database.get_item_single_name(item_id) if brought == 1 \
            else await self.database.get_item_plural_name(item_id)

        if brought < 0:
            raise InvalidItemAmountError(amount)
        if brought == 0:
            raise ItemAmountTooLowError()
        if brought > total_quantity:
            raise InsufficientBelongings(item_name, brought)

        if await self.database.item_is_unique(item_id):
            await inter.send(f"Pick which {item_name} to bring...")
        else:
            in_bag = brought
            at_home = total_quantity - in_bag
            await self.database.set_user_item_quantity(user, item_id, in_bag, BAG)
            await self.database.set_user_item_quantity(user, item_id, at_home, HOME)

            embed = Embed()
            embed.colour = Colour.dark_red()
            embed.description = f"Your {BACKPACK} **Bag** now contains `{in_bag}` **{item_name}**\n\n"\
                                f"You have `{at_home}` **{item_name}** left in your inventory"
            await inter.send(embed=embed)

    @slash_command(description="Transfer items from your bag to your inventory.")
    async def leave_behind(self, inter: Interaction,
                           amount: str = SlashOption(
                               description=AMOUNT_DESCRIPTION
                           ),
                           item_id_string: str = ItemSlashOption(
                               description="The item you wish to leave behind."
                           )):
        user = inter.user
        if not await self.database.user_exists(user):
            return await self.utils.add_and_welcome_new_user(inter, user)

        item_id = ObjectId(item_id_string)
        total_quantity = await self.database.get_user_item_quantity(user, item_id)

        if amount.lower() == "all":
            left_behind = total_quantity
        elif self.utils.is_int(amount):
            left_behind = int(amount)
        elif self.utils.is_percentage(amount):
            multiplier = self.utils.to_decimal(amount.replace("%", "")) / 100
            left_behind = int(total_quantity * multiplier)
        else:
            raise InvalidItemAmountError(amount)

        item_name = await self.database.get_item_single_name(item_id) if left_behind == 1 \
            else await self.database.get_item_plural_name(item_id)

        if left_behind < 0:
            raise InvalidItemAmountError(amount)
        if left_behind == 0:
            raise ItemAmountTooLowError()
        if left_behind > total_quantity:
            raise InsufficientBelongings(item_name, left_behind)

        if await self.database.item_is_unique(item_id):
            await inter.send(f"Pick which {item_name} to leave behind...")
        else:
            at_home = left_behind
            in_bag = total_quantity - at_home
            await self.database.set_user_item_quantity(user, item_id, at_home, HOME)
            await self.database.set_user_item_quantity(user, item_id, in_bag, BAG)

            embed = Embed()
            embed.colour = Colour.dark_red()
            embed.description = f"Your {BACKPACK} **Bag** now contains `{in_bag}` **{item_name}**\n\n" \
                                f"You have `{at_home}` **{item_name}** left in your inventory"
            await inter.send(embed=embed)


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info(f"Loading Inventory extension...")
    bot.add_cog(InventoryCog(bot))
