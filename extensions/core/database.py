from decimal import Decimal, ROUND_HALF_UP
from os import environ
from typing import Set, Optional

from bson import ObjectId, Decimal128
from motor.motor_asyncio import AsyncIOMotorClient
from nextcord import BaseApplicationCommand
from nextcord.ext.commands import Cog
from nextcord.user import User

from bot import AlisUnnamedBot


# Inventory locations
HOME: int = 0
BAG: int = 1


# Cog to handle database services
class DatabaseCog(Cog):
    def __init__(self, bot: AlisUnnamedBot, client: AsyncIOMotorClient):
        self.bot = bot
        self.client = client
        self.db = client[environ["DB_DATABASE"]]

    def close_connection(self):
        self.bot.logger.info("Closing MongoDB client...")
        self.client.close()

    @staticmethod
    def convert_decimal128_fields_to_decimal(obj):
        if obj is None: return

        if isinstance(obj, dict):
            for key, value in list(obj.items()):
                obj[key] = DatabaseCog.convert_decimal128_fields_to_decimal(value)
        elif isinstance(obj, list):
            new_obj = []
            for value in obj:
                new_obj.append(DatabaseCog.convert_decimal128_fields_to_decimal(value))
            obj = new_obj
        elif isinstance(obj, Decimal128):
            obj = obj.to_decimal()

        return obj

    # Returns a dictionary mapping item names to item ids
    async def get_item_choices(self) -> dict:
        cursor = self.db.items.find(
            {},
            {
                "_id": 1,
                "single": 1  # Use the singular name, not the plural name
            }
        )
        choices = {}
        async for item in cursor:
            item_id = item.get("_id")
            item_name = item.get("single")
            if item_name and item_id:
                # ObjectId is not json serializable, so convert it to a string
                choices[item_name] = str(item_id)
        return choices

    # Sets the choices for any ItemSlashOptions that appear in application commands
    async def setup_item_slash_option_choices(self):
        commands: Set[BaseApplicationCommand] = self.bot.get_all_application_commands()
        for command in commands:
            for name, option in command.options.items():
                if name == "item":
                    option.choices = await self.get_item_choices()

    async def user_exists(self, user: User) -> bool:
        return await self.db.users.find_one({"_id": user.id}) is not None

    async def add_user(self, user: User) -> [int, int]:
        wallet = self.bot.config.get("new_user_wallet", 0)
        bank_capacity = self.bot.config.get("new_user_bank_cap", 0)
        await self.db.users.insert_one(
            {
                "_id": user.id,
                "level": 1,
                "exp": 0,
                "wallet": Decimal128(Decimal(str(wallet)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "bank": Decimal128("0.00"),
                "bankCap": Decimal128(Decimal(str(bank_capacity)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            }
        )
        return wallet, bank_capacity

    async def get_user_profile(self, user: User) -> dict:
        result = await self.db.users.find_one(
            {
                "_id": user.id
            },
            {
                "_id": 0,
                "level": 1,
                "wallet": 1,
                "bank": 1
            }
        )
        return self.convert_decimal128_fields_to_decimal(result)

    async def get_user_level_data(self, user: User) -> dict:
        return await self.db.users.find_one(
            {
                "_id": user.id
            },
            {
                "_id": 0,
                "level": 1,
                "exp": 1
            }
        )

    async def get_user_balance(self, user: User) -> dict:
        result = await self.db.users.find_one(
            {
                "_id": user.id
            },
            {
                "_id": 0,
                "wallet": 1,
                "bank": 1,
                "bankCap": 1
            }
        )
        return self.convert_decimal128_fields_to_decimal(result)

    async def set_user_wallet(self, user: User, new_wallet: Decimal):
        return await self.db.users.update_one(
            {
                "_id": user.id
            },
            {
                "$set": {
                    "wallet": Decimal128(new_wallet)
                }
            }
        )

    async def set_user_bank(self, user: User, new_bank: Decimal):
        return await self.db.users.update_one(
            {
                "_id": user.id
            },
            {
                "$set": {
                    "bank": Decimal128(new_bank)
                }
            }
        )

    # ===========
    # Item Types
    # ===========

    async def get_item_type_name(self, item_type_id: ObjectId) -> Optional[str]:
        result = await self.db.itemTypes.find_one({"_id": item_type_id}, {"_id": 0, "name": 1})
        return result.get("name") if result else None

    async def get_item_type_properties(self, item_type_id: ObjectId) -> Optional[dict]:
        result = await self.db.itemTypes.find_one({"_id": item_type_id}, {"_id": 0, "properties": 1})
        return result.get("properties") if result else None

    # ===========
    # Items
    # ===========

    # This is really just useful for debugging more than anything
    async def get_item_id(self, item_name: str) -> Optional[ObjectId]:
        result = await self.db.items.find_one({"single": item_name}, {"_id": 1})
        return result.get("_id") if result else None

    async def item_exists(self, item_id: ObjectId) -> bool:
        return await self.db.items.find_one({"_id": item_id}) is not None

    async def get_item_single_name(self, item_id: ObjectId) -> Optional[str]:
        result = await self.db.items.find_one({"_id": item_id}, {"_id": 0, "single": 1})
        return result.get("single") if result else None

    async def get_item_plural_name(self, item_id: ObjectId) -> Optional[str]:
        result = await self.db.items.find_one({"_id": item_id}, {"_id": 0, "plural": 1})
        return result.get("plural") if result else None

    async def get_item_name(self, item_id: ObjectId, amount: int = 1):
        return await self.get_item_single_name(item_id) if amount == 1 else await self.get_item_plural_name(item_id)

    async def get_item_type_id(self, item_id: ObjectId) -> Optional[ObjectId]:
        result = await self.db.items.find_one({"_id": item_id}, {"_id": 0, "itemTypeId": 1})
        return result.get("itemTypeId") if result else None

    async def item_is_unique(self, item_id: ObjectId) -> bool:
        result = await self.db.items.find_one({"_id": item_id}, {"_id": 0, "isUnique": 1})
        return result.get("isUnique") if result else False

    # Merges new_props onto old_props
    # Values from new_props will take priority over values in old_props
    def merge_properties(self, old_props: dict, new_props: dict) -> dict:
        # List of keys from both dictionaries (no duplicates)
        keys = list(old_props.keys()) + list(set(new_props.keys()) - set(old_props.keys()))
        out = {}
        for key in keys:
            if key in old_props and key in new_props:
                old = old_props[key]  # Original value
                new = new_props[key]  # New value
                if isinstance(old, dict) and isinstance(new, dict):
                    out[key] = self.merge_properties(old, new)
                else:
                    out[key] = new  # New value takes priority / overrides old value
            elif key in old_props:
                out[key] = old_props[key]
            else:
                out[key] = new_props[key]
        return out

    async def get_item_properties(self, item_id: ObjectId) -> Optional[dict]:
        item_type_id = await self.get_item_type_id(item_id)
        item_type_properties = await self.get_item_type_properties(item_type_id)
        result = await self.db.items.find_one({"_id": item_id}, {"_id": 0, "properties": 1})
        item_properties = result.get("properties") if result else None
        if item_type_properties and item_properties:
            return self.merge_properties(item_type_properties, item_properties)
        else:
            return item_properties if item_properties else item_type_properties

    # ===========
    # User Items
    # ===========

    async def get_user_item_item_id(self, user_item_id: ObjectId) -> Optional[ObjectId]:
        result = await self.db.userItems.find_one({"_id": user_item_id}, {"itemId": 1})
        return result.get("itemId") if result else None

    async def get_user_item_type_id(self, user_item_id: ObjectId) -> Optional[ObjectId]:
        item_id = await self.get_user_item_item_id(user_item_id)
        return await self.get_item_type_id(item_id)

    async def get_user_item_name(self, user_item_id: ObjectId, amount: int = 1):
        item_id = await self.get_user_item_item_id(user_item_id)
        if await self.item_is_unique(item_id):
            result = await self.db.userItems.find_one(
                {
                    "_id": user_item_id
                },
                {
                    "_id": 0,
                    "name": 1
                }
            )
            if result:
                return result.get("name")
            return f"{await self.get_item_single_name(item_id)} ({user_item_id})"
        else:
            return await self.get_item_name(item_id, amount)

    async def get_user_item_quantity(self, user: User, item_id: ObjectId, location: int = None) -> int:
        if await self.item_is_unique(item_id):
            quantity = 0
            if location == HOME or location is None:
                home = self.db.userItems.find(
                    {
                        "userId": user.id,
                        "itemId": item_id,
                        "location": HOME
                    }
                )
                async for _ in home:
                    quantity += 1
            if location == BAG or location is None:
                bag = self.db.userItems.find(
                    {
                        "userId": user.id,
                        "itemId": item_id,
                        "location": BAG
                    }
                )
                async for _ in bag:
                    quantity += 1
            return quantity
        else:
            quantity = 0
            if location == HOME or location is None:
                home = await self.db.userItems.find_one(
                    {
                        "userId": user.id,
                        "itemId": item_id,
                        "location": HOME
                    },
                    {
                        "_id": 0,
                        "quantity": 1
                    }
                )
                if home:
                    quantity += home.get("quantity")
            if location == BAG or location is None:
                bag = await self.db.userItems.find_one(
                    {
                        "userId": user.id,
                        "itemId": item_id,
                        "location": BAG
                    },
                    {
                        "_id": 0,
                        "quantity": 1
                    }
                )
                if bag:
                    quantity += bag.get("quantity")
            return quantity

    async def get_user_item_properties(self, user_item_id: ObjectId) -> dict:
        item_id = await self.get_user_item_item_id(user_item_id)
        item_properties = await self.get_item_properties(item_id)
        result = await self.db.userItems.find_one({"_id": user_item_id}, {"_id": 0, "properties": 1})
        user_item_properties = result.get("properties") if result else None
        if item_properties and user_item_properties:
            return self.merge_properties(item_properties, user_item_properties)
        else:
            return user_item_properties if user_item_properties else item_properties

    async def user_has_item(self, user: User, item_id: ObjectId, location: int = None) -> bool:
        return await self.get_user_item_quantity(user, item_id, location) > 0

    async def get_user_inventory(self, user: User, location: int = None) -> list[dict]:
        if location is None:
            cursor = self.db.userItems.find(
                {
                    "userId": user.id
                },
                {
                    "userId": 0
                }
            )
        else:
            cursor = self.db.userItems.find(
                {
                    "userId": user.id,
                    "location": location
                },
                {
                    "userId": 0
                }
            )
        return [item async for item in cursor]

    async def get_user_bag(self, user: User) -> list[dict]:
        return await self.get_user_inventory(user, BAG)

    async def get_specific_user_items(self, user: User, item_id: ObjectId, location: int = None) -> list[ObjectId]:
        if location is None:
            cursor = self.db.userItems.find(
                {
                    "userId": user.id,
                    "itemId": item_id
                },
                {
                    "_id": 1
                }
            )
        else:
            cursor = self.db.userItems.find(
                {
                    "userId": user.id,
                    "itemId": item_id,
                    "location": location
                },
                {
                    "_id": 1
                }
            )
        return [item.get("_id") async for item in cursor]

    async def set_user_item_quantity(self, user: User, item_id: ObjectId, amount: int, location: int):
        if await self.item_is_unique(item_id):
            return
        if amount < 1:
            await self.db.userItems.delete_one(
                {
                    "userId": user.id,
                    "itemId": item_id,
                    "location": location
                }
            )
        elif await self.user_has_item(user, item_id, location):
            await self.db.userItems.update_one(
                {
                    "userId": user.id,
                    "itemId": item_id,
                    "location": location
                },
                {
                    "$set": {
                        "quantity": amount
                    }
                }
            )
        else:
            await self.db.userItems.insert_one(
                {
                    "userId": user.id,
                    "itemId": item_id,
                    "location": location,
                    "quantity": amount
                }
            )

    async def add_unique_user_item(self, user: User, item_id: ObjectId, location: int, amount: int = 1):
        if not await self.item_is_unique(item_id):
            return
        if amount < 1:
            amount = 1
        max_unique_items = self.bot.config.get("max_unique_items")
        quantity = await self.get_user_item_quantity(user, item_id)
        if quantity >= max_unique_items:
            return
        if quantity + amount > max_unique_items:
            amount = max_unique_items - quantity
        item = {
            "userId": user.id,
            "itemId": item_id,
            "location": location
        }
        items = [item.copy() for _ in range(amount)]
        return await self.db.userItems.insert_many(items)

    async def remove_unique_user_item(self, user_item_id: ObjectId):
        item_id = await self.get_user_item_item_id(user_item_id)
        if not await self.item_is_unique(item_id):
            return
        await self.db.userItems.delete_one({"_id": user_item_id})

    async def set_unique_user_item_location(self, user_item_id: ObjectId, location: int):
        item_id = await self.get_user_item_item_id(user_item_id)
        if not await self.item_is_unique(item_id):
            return
        await self.db.userItems.update_one(
            {
                "_id": user_item_id
            },
            {
                "$set": {
                    "location": location
                }
            }
        )


def setup(bot: AlisUnnamedBot):
    bot.logger.info("Loading Database extension...")
    client = AsyncIOMotorClient(environ["DB_HOST"], int(environ["DB_PORT"]), io_loop=bot.loop)
    bot.add_cog(DatabaseCog(bot, client))
