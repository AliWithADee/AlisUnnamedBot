from typing import Callable

from bson import ObjectId
from nextcord import Interaction, Embed, Colour, ButtonStyle, SelectOption
from nextcord.ui import View, Button, Select

from bot import AlisUnnamedBot
from extensions.core.database import DatabaseCog
from extensions.core.emojis import CROSS, ARROW_LEFT_ANIMATED, ARROW_RIGHT_ANIMATED, TICK


DEFAULT_MENU_COLOUR = 3092790


class NotMenuOwnerEmbed(Embed):
    def __init__(self):
        super().__init__()
        self.title = "**Hands Off!**"
        self.description = f"{CROSS} This menu doesn't belong to you!"
        self.colour = Colour.red()


class MaximumUniqueItemsExceeded(Embed):
    def __init__(self, max_items: int, item_name: str):
        super().__init__()
        self.title = "**Maximum Unique Items Exceeded**"
        self.description = f"{CROSS} You have more than the maximum amount of **{item_name}**" \
                           f", which is `{max_items}`." \
                           f"\n\n*I recommend contacting the owner of the bot for assistance.\n" \
                           f"Some {item_name} may need to be removed manually.*"
        self.colour = Colour.red()


class Menu(View):
    def __init__(self, original_inter: Interaction, title: str = None, colour: Colour = Colour(DEFAULT_MENU_COLOUR)):
        super().__init__()
        self.original_inter = original_inter
        self.title = title
        self.colour = colour

    async def send_or_update_menu(self):
        embed = Embed()
        embed.title = self.title if self.title else "Menu Title"
        embed.colour = self.colour
        if self.original_inter.response.is_done():
            await self.original_inter.edit_original_message(view=self, embed=embed)
        else:
            await self.original_inter.send(view=self, embed=embed)

    async def disable_buttons(self):
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
        await self.original_inter.edit_original_message(view=self)

    async def on_timeout(self):
        await self.disable_buttons()


class BotAccessMenu(Menu):
    def __init__(self, bot: AlisUnnamedBot, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot


class DatabaseAccessMenu(Menu):
    def __init__(self, database: DatabaseCog, **kwargs):
        super().__init__(**kwargs)
        self.database = database


class ConfirmAndCancelMenu(Menu):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def on_confirm(self):
        pass

    async def on_cancel(self):
        pass


class PreviousAndNextMenu(Menu):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def on_previous(self):
        pass

    async def on_next(self):
        pass


class DropDownMenu(Menu):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def on_drop_down_list_updated(self):
        pass


class SelectUserItemsMenu(ConfirmAndCancelMenu, DropDownMenu, BotAccessMenu, DatabaseAccessMenu):
    def __init__(self, item_id: ObjectId, user_items: list[ObjectId], callback: Callable, **kwargs):
        super().__init__(**kwargs)
        self.item_id = item_id
        self.user_items = user_items
        self.callback = callback

        self.current_index = 0
        self.num_items = len(self.user_items)
        self.selected_items: list[ObjectId] = []

        self.button_select = ButtonSelect(self)
        self.add_item(self.button_select)

        self.select_item = DropDownList(self)
        self.add_item(self.select_item)

        self.button_select_all = ButtonSelectAll(self)
        self.add_item(self.button_select_all)

        self.button_remove_all = ButtonRemoveAll(self)
        self.add_item(self.button_remove_all)

        self.button_confirm = ButtonConfirm(self)
        self.button_confirm.label = "Done"
        self.button_confirm.row = 2
        self.add_item(self.button_confirm)

        self.button_cancel = ButtonCancel(self)
        self.button_cancel.row = 2
        self.add_item(self.button_cancel)

    async def send_or_update_menu(self):
        if not self.user_items:
            return
        # Current item info
        cur_item_id = self.user_items[self.current_index]
        cur_item_name = await self.database.get_user_item_name(cur_item_id)
        cur_item_properties = await self.database.get_user_item_properties(cur_item_id)
        selected = cur_item_id in self.selected_items

        # Item Properties
        properties = []
        categories = {}
        for prop in cur_item_properties.values():
            if "category" in prop and "properties" in prop:
                category_prop_list = []
                category_properties = prop["properties"]
                for category_prop in category_properties.values():
                    category_prop_name = category_prop["name"]
                    category_prop_value = category_prop["value"]
                    category_prop_list.append(f"{category_prop_name}: `{category_prop_value}`")
                category_name = prop["category"]
                categories[category_name] = category_prop_list
            elif "name" in prop and "value" in prop:
                prop_name = prop["name"]
                prop_value = prop["value"]
                properties.append(f"{prop_name}: `{prop_value}`")

        # Selected Items
        selected_item_names = []
        for selected_item_id in self.selected_items:
            selected_item_names.append(f"{await self.database.get_user_item_name(selected_item_id)}")

        # Update select button
        self.button_select.label = f"Remove" if selected else f"Select"
        self.button_select.emoji = CROSS if selected else TICK

        # Update dropdown menu
        if not self.select_item.options:
            for i in range(self.num_items):
                user_item_id = self.user_items[i]
                user_item_name = await self.database.get_user_item_name(user_item_id)
                option = SelectOption(label=user_item_name, value=str(i))
                self.select_item.append_option(option)
            single_name = await self.database.get_item_single_name(self.item_id)
            self.select_item.placeholder = f"Select {single_name}"

        plural_name = await self.database.get_item_plural_name(self.item_id)

        # Create and send Embed
        embed = Embed()
        embed.title = f"**Select {plural_name}**"
        embed.colour = self.colour
        embed.add_field(name="Current Item", value=cur_item_name, inline=False)
        embed.add_field(name="Properties", value="\n".join(properties))
        for category_name, category_properties in list(categories.items()):
            embed.add_field(name=category_name, value="\n".join(category_properties))
        if selected_item_names:
            embed.add_field(name="Selected Items", value="\n".join(selected_item_names), inline=False)
        embed.set_footer(text=f"Item {self.current_index + 1} of {self.num_items}")
        if self.original_inter.response.is_done():
            await self.original_inter.edit_original_message(view=self, embed=embed)
        else:
            max_unique_items = self.bot.config.get("max_unique_items")
            if self.num_items > max_unique_items:
                await self.original_inter.send(embed=MaximumUniqueItemsExceeded(max_unique_items, plural_name))
            else:
                await self.original_inter.send(view=self, embed=embed)

    async def on_drop_down_list_updated(self):
        if self.select_item.values:
            self.current_index = int(self.select_item.values[0])
            await self.send_or_update_menu()

    async def on_select(self):
        user_item_id = self.user_items[self.current_index]
        if user_item_id in self.selected_items:
            self.selected_items.remove(user_item_id)
        else:
            self.selected_items.append(user_item_id)
        await self.send_or_update_menu()

    async def on_select_all(self):
        self.selected_items = self.user_items.copy()
        await self.send_or_update_menu()

    async def on_remove_all(self):
        self.selected_items = []
        await self.send_or_update_menu()

    async def on_confirm(self):
        await self.disable_buttons()
        await self.callback(self.original_inter, self.selected_items)

    async def on_cancel(self):
        await self.on_remove_all()
        await self.on_confirm()


class DropDownList(Select):
    def __init__(self, menu: DropDownMenu, **kwargs):
        super().__init__(**kwargs)
        self.menu = menu

    async def callback(self, inter: Interaction):
        if self.menu.original_inter.user.id != inter.user.id:
            return await inter.send(embed=NotMenuOwnerEmbed(), ephemeral=True)
        await self.menu.on_drop_down_list_updated()


class ButtonConfirm(Button):
    def __init__(self, menu: ConfirmAndCancelMenu, **kwargs):
        super().__init__(**kwargs, label="Confirm", style=ButtonStyle.green)
        self.menu = menu

    async def callback(self, inter: Interaction):
        if self.menu.original_inter.user.id != inter.user.id:
            return await inter.send(embed=NotMenuOwnerEmbed(), ephemeral=True)
        await self.menu.on_confirm()


class ButtonCancel(Button):
    def __init__(self, menu: ConfirmAndCancelMenu, **kwargs):
        super().__init__(**kwargs, label="Cancel", style=ButtonStyle.red)
        self.menu = menu

    async def callback(self, inter: Interaction):
        if self.menu.original_inter.user.id != inter.user.id:
            return await inter.send(embed=NotMenuOwnerEmbed(), ephemeral=True)
        await self.menu.on_cancel()


class ButtonPrevious(Button):
    def __init__(self, menu: PreviousAndNextMenu, **kwargs):
        super().__init__(**kwargs, emoji=ARROW_LEFT_ANIMATED, style=ButtonStyle.grey)
        self.menu = menu

    async def callback(self, inter: Interaction):
        if self.menu.original_inter.user.id != inter.user.id:
            return await inter.send(embed=NotMenuOwnerEmbed(), ephemeral=True)
        await self.menu.on_previous()


class ButtonNext(Button):
    def __init__(self, menu: PreviousAndNextMenu, **kwargs):
        super().__init__(**kwargs, emoji=ARROW_RIGHT_ANIMATED, style=ButtonStyle.grey)
        self.menu = menu

    async def callback(self, inter: Interaction):
        if self.menu.original_inter.user.id != inter.user.id:
            return await inter.send(embed=NotMenuOwnerEmbed(), ephemeral=True)
        await self.menu.on_next()


class ButtonSelect(Button):
    def __init__(self, menu: SelectUserItemsMenu, **kwargs):
        super().__init__(**kwargs, label="Select", style=ButtonStyle.blurple)
        self.menu = menu

    async def callback(self, inter: Interaction):
        if self.menu.original_inter.user.id != inter.user.id:
            return await inter.send(embed=NotMenuOwnerEmbed(), ephemeral=True)
        await self.menu.on_select()


class ButtonSelectAll(Button):
    def __init__(self, menu: SelectUserItemsMenu, **kwargs):
        super().__init__(**kwargs, emoji=TICK, label="Select All", style=ButtonStyle.grey)
        self.menu = menu

    async def callback(self, inter: Interaction):
        if self.menu.original_inter.user.id != inter.user.id:
            return await inter.send(embed=NotMenuOwnerEmbed(), ephemeral=True)
        await self.menu.on_select_all()


class ButtonRemoveAll(Button):
    def __init__(self, menu: SelectUserItemsMenu, **kwargs):
        super().__init__(**kwargs, emoji=CROSS, label="Remove All", style=ButtonStyle.grey)
        self.menu = menu

    async def callback(self, inter: Interaction):
        if self.menu.original_inter.user.id != inter.user.id:
            return await inter.send(embed=NotMenuOwnerEmbed(), ephemeral=True)
        await self.menu.on_remove_all()


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info("Loading UI extension...")
