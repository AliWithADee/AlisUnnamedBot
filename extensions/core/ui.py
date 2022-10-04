from typing import Callable

from bson import ObjectId
from nextcord import Interaction, Embed, Colour, ButtonStyle
from nextcord.ui import View, Button

from bot import AlisUnnamedBot
from extensions.core.database import DatabaseCog
from extensions.core.emojis import CROSS, ARROW_LEFT_ANIMATED, ARROW_RIGHT_ANIMATED, TICK


DEFAULT_MENU_COLOUR = 3092790


class NotMenuOwnerEmbed(Embed):
    def __init__(self):
        super().__init__()
        self.title = "**You Can't Do That!**"
        self.description = f"{CROSS} This menu doesn't belong to you!"
        self.colour = Colour.red()


class Menu(View):
    def __init__(self, title: str, original_inter: Interaction, colour: Colour = Colour(DEFAULT_MENU_COLOUR)):
        super().__init__()
        self.title = title
        self.original_inter = original_inter
        self.colour = colour

    async def send_or_update_menu(self):
        embed = Embed()
        embed.title = self.title
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


class DatabaseMenu(Menu):
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


class SelectUserItemsMenu(ConfirmAndCancelMenu, PreviousAndNextMenu, DatabaseMenu):
    def __init__(self, user_items: list[ObjectId], callback: Callable, **kwargs):
        super().__init__(**kwargs)
        self.user_items = user_items
        self.callback = callback

        self.current_index = 0
        self.num_items = len(self.user_items)
        self.selected_items: list[ObjectId] = []

        self.button_previous = ButtonPrevious(self)
        self.add_item(self.button_previous)

        self.button_select = ButtonSelect(self)
        self.add_item(self.button_select)

        self.button_next = ButtonNext(self)
        self.add_item(self.button_next)

        self.button_select_all = ButtonSelectAll(self)
        self.add_item(self.button_select_all)

        self.button_remove_all = ButtonRemoveAll(self)
        self.add_item(self.button_remove_all)

        self.button_confirm = ButtonConfirm(self)
        self.button_confirm.row = 1
        self.add_item(self.button_confirm)

        self.button_cancel = ButtonCancel(self)
        self.button_cancel.row = 1
        self.add_item(self.button_cancel)

    async def send_or_update_menu(self):
        if not self.user_items:
            return
        # Current item info
        cur_item_id = self.user_items[self.current_index]
        cur_item_name = await self.database.get_user_item_name(cur_item_id)
        selected = cur_item_id in self.selected_items

        # Update button settings
        self.button_previous.disabled = self.current_index == 0
        self.button_next.disabled = self.current_index == self.num_items - 1
        self.button_select.label = "Remove" if selected else "Select"
        self.button_select.style = ButtonStyle.red if selected else ButtonStyle.blurple

        # Setup embed fields
        name = f"{TICK} **{cur_item_name}**" if selected else f"{CROSS} **{cur_item_name}**"
        selected_item_names = []
        for selected_item_id in self.selected_items:
            selected_item_names.append(f"{await self.database.get_user_item_name(selected_item_id)}")
        selected_items = "**Selected Items:**\n- " + "\n- ".join(selected_item_names) if selected_item_names else ""

        # TODO: Add more fields and information about the current item in SelectUserItemsMenu

        # Create and send Embed
        embed = Embed()
        embed.title = self.title
        embed.colour = self.colour
        embed.description = f"{name}\n\n" \
                            f"{selected_items}"
        embed.set_footer(text=f"{self.current_index+1}/{self.num_items}")
        if self.original_inter.response.is_done():
            await self.original_inter.edit_original_message(view=self, embed=embed)
        else:
            await self.original_inter.send(view=self, embed=embed)

    async def on_previous(self):
        previous_index = self.current_index - 1
        if previous_index >= 0:
            self.current_index = previous_index
            await self.send_or_update_menu()

    async def on_next(self):
        next_index = self.current_index + 1
        if next_index < self.num_items:
            self.current_index = next_index
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
