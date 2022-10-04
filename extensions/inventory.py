from typing import Optional

from bson import ObjectId
from nextcord import slash_command, Interaction, User, SlashOption, Embed, Colour

from bot import AlisUnnamedBot
from extensions.core.database import BAG, HOME
from extensions.core.emojis import BACKPACK
from extensions.core.ui import SelectUserItemsMenu
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


class InsufficientBelongingsError(EmbedError):
    def __init__(self, item_name: str, amount: int):
        super().__init__("**Insufficient Belongings**",
                         f"You don't have `{amount}` **{item_name}**")


class ItemNotFoundInBagError(EmbedError):
    def __init__(self, item_name: str):
        super().__init__("**Insufficient Belongings**",
                         f"Your {BACKPACK} **Bag** does not contain any **{item_name}**!")


class ItemNotFoundInInventoryError(EmbedError):
    def __init__(self, item_name: str):
        super().__init__("**Insufficient Belongings**",
                         f"Your home inventory does not contain any **{item_name}**!\n\n"
                         f"*The {item_name} may be in your {BACKPACK} **Bag** instead...*")


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
        for user_item in inventory:
            user_item_id = user_item.get("_id")
            item_id = user_item.get("itemId")
            location = user_item.get("location", HOME)
            quantity = 1 if await self.database.item_is_unique(item_id) else user_item.get("quantity", 0)
            if quantity > 0:
                name = await self.database.get_user_item_name(user_item_id, quantity)
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
        for user_item in bag:
            user_item_id = user_item.get("_id")
            item_id = user_item.get("itemId")
            quantity = 1 if await self.database.item_is_unique(item_id) else user_item.get("quantity", 0)
            if quantity > 0:
                name = await self.database.get_user_item_name(user_item_id, quantity)
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
                    item_id_string: str = ItemSlashOption(
                        description="The item you wish to bring with you."
                    ),
                    amount: Optional[str] = SlashOption(
                        description=AMOUNT_DESCRIPTION,
                        default="0"
                    )):
        user = inter.user
        if not await self.database.user_exists(user):
            return await self.utils.add_and_welcome_new_user(inter, user)

        item_id = ObjectId(item_id_string)

        if await self.database.item_is_unique(item_id):
            item_plural_name = await self.database.get_item_plural_name(item_id)
            home_items = await self.database.get_specific_user_items(user, item_id, HOME)
            if not home_items:
                raise ItemNotFoundInInventoryError(item_plural_name)
            elif amount.lower() == "all":
                await self.bring_selected_items(inter, home_items)
            else:
                menu = SelectUserItemsMenu(user_items=home_items, callback=self.bring_selected_items,
                                           title=f"Select {item_plural_name}",
                                           original_inter=inter, database=self.database)
                await menu.send_or_update_menu()
        else:
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

            item_name = await self.database.get_item_name(item_id, brought)

            if brought < 0:
                raise InvalidItemAmountError(amount)
            if brought == 0:
                raise ItemAmountTooLowError()
            if brought > total_quantity:
                raise InsufficientBelongingsError(item_name, brought)

            in_bag = brought
            at_home = total_quantity - in_bag
            item_name_at_home = await self.database.get_item_name(item_id, at_home)

            await self.database.set_user_item_quantity(user, item_id, in_bag, BAG)
            await self.database.set_user_item_quantity(user, item_id, at_home, HOME)

            embed = Embed()
            embed.colour = Colour.dark_red()
            embed.description = f"You added `{in_bag}` **{item_name}** to your {BACKPACK} **Bag**\n\n" \
                                f"You left `{at_home}` **{item_name_at_home}** in your home inventory"
            await inter.send(embed=embed)

    async def bring_selected_items(self, inter: Interaction, selected_items: list[ObjectId]):
        brought_items = selected_items
        if brought_items:
            brought_item_names = []
            for user_item_id in brought_items:
                await self.database.set_unique_user_item_location(user_item_id, BAG)
                user_item_name = await self.database.get_user_item_name(user_item_id)
                brought_item_names.append(f"**{user_item_name}**")
            embed = Embed()
            embed.colour = Colour.dark_red()
            embed.description = f"You added the following items to your {BACKPACK} **Bag**:\n\n" \
                                f"- " + "\n- ".join(brought_item_names)
            await inter.send(embed=embed)
        else:
            embed = Embed()
            embed.colour = Colour.dark_red()
            embed.title = "**No Items Were Selected**"
            embed.description = f"*No changes were made to your inventory...*"
            await inter.send(embed=embed)

    @slash_command(description="Transfer items from your bag to your inventory.")
    async def leave(self, inter: Interaction,
                    item_id_string: str = ItemSlashOption(
                        description="The item you wish to leave behind."
                    ),
                    amount: Optional[str] = SlashOption(
                        description=AMOUNT_DESCRIPTION,
                        default="0"
                    )):
        user = inter.user
        if not await self.database.user_exists(user):
            return await self.utils.add_and_welcome_new_user(inter, user)

        item_id = ObjectId(item_id_string)

        if await self.database.item_is_unique(item_id):
            item_plural_name = await self.database.get_item_plural_name(item_id)
            bag_items = await self.database.get_specific_user_items(user, item_id, BAG)
            if not bag_items:
                raise ItemNotFoundInBagError(item_plural_name)
            elif amount.lower() == "all":
                await self.leave_selected_items(inter, bag_items)
            else:
                menu = SelectUserItemsMenu(user_items=bag_items, callback=self.leave_selected_items,
                                           title=f"Select {item_plural_name}",
                                           original_inter=inter, database=self.database)
                await menu.send_or_update_menu()
        else:
            total_quantity = await self.database.get_user_item_quantity(user, item_id)

            if amount.lower() == "all":
                left = total_quantity
            elif self.utils.is_int(amount):
                left = int(amount)
            elif self.utils.is_percentage(amount):
                multiplier = self.utils.to_decimal(amount.replace("%", "")) / 100
                left = int(total_quantity * multiplier)
            else:
                raise InvalidItemAmountError(amount)

            item_name = await self.database.get_item_name(item_id, left)

            if left < 0:
                raise InvalidItemAmountError(amount)
            if left == 0:
                raise ItemAmountTooLowError()
            if left > total_quantity:
                raise InsufficientBelongingsError(item_name, left)

            at_home = left
            in_bag = total_quantity - at_home
            item_name_in_bag = await self.database.get_item_name(item_id, in_bag)

            await self.database.set_user_item_quantity(user, item_id, at_home, HOME)
            await self.database.set_user_item_quantity(user, item_id, in_bag, BAG)

            embed = Embed()
            embed.colour = Colour.dark_red()
            embed.description = f"You left `{at_home}` **{item_name}** in your home inventory\n\n" \
                                f"You kept `{in_bag}` **{item_name_in_bag}** in your {BACKPACK} **Bag**"

            await inter.send(embed=embed)

    async def leave_selected_items(self, inter: Interaction, selected_items: list[ObjectId]):
        left_items = selected_items
        if left_items:
            left_item_names = []
            for user_item_id in left_items:
                await self.database.set_unique_user_item_location(user_item_id, HOME)
                user_item_name = await self.database.get_user_item_name(user_item_id)
                left_item_names.append(f"**{user_item_name}**")
            embed = Embed()
            embed.colour = Colour.dark_red()
            embed.description = f"You left the following items in your home inventory:\n\n" \
                                f"- " + "\n- ".join(left_item_names)
            await inter.send(embed=embed)
        else:
            embed = Embed()
            embed.colour = Colour.dark_red()
            embed.title = "**No Items Were Selected**"
            embed.description = f"*No changes were made to your inventory...*"
            await inter.send(embed=embed)


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info(f"Loading Inventory extension...")
    bot.add_cog(InventoryCog(bot))
