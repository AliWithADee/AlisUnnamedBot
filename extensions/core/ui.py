from typing import Callable

from nextcord import Interaction, Embed, Colour
from nextcord.ui import View, Button

from bot import AlisUnnamedBot
from extensions.core.database import DatabaseCog
from extensions.core.emojis import CROSS


class NotMenuOwnerEmbed(Embed):
    def __init__(self):
        super().__init__()
        self.title = "**You Can't Do That!**"
        self.description = f"{CROSS} This menu doesn't belong to you!"
        self.colour = Colour.red()


# TODO: Base classes for reusable "Menus" and "Buttons"


class SelectUserItemsMenu(View):
    def __init__(self, original_inter: Interaction, user_items: list[dict], callback: Callable, database: DatabaseCog):
        super().__init__()
        self.original_inter = original_inter
        self.user_items = user_items
        self.callback = callback
        self.database = database

        self.current_index = 0
        self.selected_items = []

        self.add_item(ButtonPrevious(self))
        self.add_item(ButtonNext(self))
        self.button_select = ButtonSelect(self)
        self.add_item(self.button_select)
        self.add_item(ButtonConfirm(self))

    @classmethod
    async def create(cls, original_inter: Interaction, items: list[dict], callback: Callable, database: DatabaseCog):
        menu = SelectUserItemsMenu(original_inter, items, callback, database)
        await original_inter.send(view=menu)
        await menu.update_menu()
        return menu

    async def update_menu(self):
        if not self.user_items:
            return
        if not self.original_inter.response.is_done():
            return
        user_item = self.user_items[self.current_index]
        selected = user_item in self.selected_items
        self.button_select.label = "Deselect" if selected else "Select"

        user_item_id = user_item.get("_id")
        name = await self.database.get_user_item_name(user_item_id)

        # TODO: Improve item display in SelectUserItemsMenu. Eg: Add "item #1 out of 12 items" etc
        # TODO: Add "Cancel" button?
        # TODO: Add "Select All" button

        embed = Embed()
        embed.title = name
        embed.colour = Colour.dark_blue()
        embed.description = "Selected" if selected else "Not Selected"
        await self.original_inter.edit_original_message(view=self, embed=embed)

    async def disable_buttons(self):
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
        await self.original_inter.edit_original_message(view=self)

    async def on_button_previous(self):
        previous_index = self.current_index - 1
        if previous_index >= 0:
            self.current_index = previous_index
            await self.update_menu()

    async def on_button_next(self):
        next_index = self.current_index + 1
        if next_index < len(self.user_items):
            self.current_index = next_index
            await self.update_menu()

    async def on_button_select(self):
        user_item = self.user_items[self.current_index]
        if user_item in self.selected_items:
            self.selected_items.remove(user_item)
        else:
            self.selected_items.append(user_item)
        await self.update_menu()

    async def on_button_confirm(self):
        await self.disable_buttons()
        await self.callback(self.original_inter, self.selected_items)

    async def on_timeout(self):
        await self.disable_buttons()


class ButtonPrevious(Button):
    def __init__(self, menu: SelectUserItemsMenu, **kwargs):
        super().__init__(**kwargs, label="Previous")  # TODO: Add arrows to "Next" and "Previous" buttons
        self.menu = menu

    async def callback(self, inter: Interaction):
        if self.menu.original_inter.user.id != inter.user.id:
            return await inter.send(embed=NotMenuOwnerEmbed(), ephemeral=True)
        await self.menu.on_button_previous()


class ButtonNext(Button):
    def __init__(self, menu: SelectUserItemsMenu, **kwargs):
        super().__init__(**kwargs, label="Next")  # TODO: Add arrows to "Next" and "Previous" buttons
        self.menu = menu

    async def callback(self, inter: Interaction):
        if self.menu.original_inter.user.id != inter.user.id:
            return await inter.send(embed=NotMenuOwnerEmbed(), ephemeral=True)
        await self.menu.on_button_next()


class ButtonSelect(Button):
    def __init__(self, menu: SelectUserItemsMenu, **kwargs):
        super().__init__(**kwargs, label="Select")
        self.menu = menu

    async def callback(self, inter: Interaction):
        if self.menu.original_inter.user.id != inter.user.id:
            return await inter.send(embed=NotMenuOwnerEmbed(), ephemeral=True)
        await self.menu.on_button_select()


class ButtonConfirm(Button):
    def __init__(self, menu: SelectUserItemsMenu, **kwargs):
        super().__init__(**kwargs, label="Confirm")
        self.menu = menu

    async def callback(self, inter: Interaction):
        if self.menu.original_inter.user.id != inter.user.id:
            return await inter.send(embed=NotMenuOwnerEmbed(), ephemeral=True)
        await self.menu.on_button_confirm()


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info("Loading UI extension...")
