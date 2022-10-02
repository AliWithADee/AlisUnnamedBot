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

UNKNOWN = "UNKNOWN"


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

    async def get_item_id(self, item_name: str) -> Optional[ObjectId]:
        result = await self.db.items.find_one({"single": item_name}, {"_id": 1})
        return result.get("_id") if result else None

    async def item_exists(self, item_id: ObjectId) -> bool:
        return await self.db.items.find_one({"_id": item_id}) is not None

    async def item_is_unique(self, item_id: ObjectId) -> bool:
        result = await self.db.items.find_one({"_id": item_id}, {"_id": 0, "isUnique": 1})
        return result.get("isUnique") if result else False

    async def get_item_single_name(self, item_id: ObjectId) -> Optional[str]:
        result = await self.db.items.find_one({"_id": item_id}, {"_id": 0, "single": 1})
        return result.get("single") if result else None

    async def get_item_plural_name(self, item_id: ObjectId) -> Optional[str]:
        result = await self.db.items.find_one({"_id": item_id}, {"_id": 0, "plural": 1})
        return result.get("plural") if result else None

    async def get_user_item_quantity(self, user: User, item_id: ObjectId, location: int = HOME) -> int:
        if await self.item_is_unique(item_id):
            result = await self.db.userItems.find_one(
                {
                    "userId": user.id,
                    "itemId": item_id,
                    "location": location
                }
            )
            return 1 if result else 0
        else:
            result = await self.db.userItems.find_one(
                {
                    "userId": user.id,
                    "itemId": item_id,
                    "location": location
                },
                {
                    "_id": 0,
                    "quantity": 1
                }
            )
            return result.get("quantity") if result else 0

    async def user_has_item(self, user: User, item_id: ObjectId, location: int = HOME) -> bool:
        return await self.get_user_item_quantity(user, item_id, location) > 0

    async def add_user_item(self, user: User, item_id: ObjectId, amount: int = 1, location: int = HOME):
        if amount < 1:
            amount = 1
        if await self.item_is_unique(item_id):
            item = {
                "userId": user.id,
                "itemId": item_id,
                "location": location
            }
            items = [item.copy() for _ in range(amount)]
            await self.db.userItems.insert_many(items)
        elif await self.user_has_item(user, item_id, location):
            await self.db.userItems.update_one(
                {
                    "userId": user.id,
                    "itemId": item_id,
                    "location": location
                },
                {
                    "$inc": {
                        "quantity": amount
                    }
                }
            )
        elif await self.item_exists(item_id):
            await self.db.userItems.insert_one(
                {
                    "userId": user.id,
                    "itemId": item_id,
                    "location": location,
                    "quantity": amount
                }
            )

    async def remove_non_unique_user_item(self, user: User, item_id: ObjectId, amount: int = 1, location: int = HOME):
        if await self.item_is_unique(item_id):
            return
        if not await self.user_has_item(user, item_id, location):
            return
        if amount < 1:
            amount = 1
        result = await self.db.userItems.find_one(
            {
                "userId": user.id,
                "itemId": item_id,
                "location": location
            },
            {
                "_id": 0,
                "quantity": 1
            }
        )
        quantity = result.get("quantity")
        if quantity == amount:
            await self.db.userItems.delete_one(
                {
                    "userId": user.id,
                    "itemId": item_id,
                    "location": location
                }
            )
        elif quantity > amount:
            await self.db.userItems.update_one(
                {
                    "userId": user.id,
                    "itemId": item_id,
                    "location": location
                },
                {
                    "$inc": {
                        "quantity": -amount
                    }
                }
            )

    async def get_user_inventory(self, user: User, location: int = None):
        if not location:
            cursor = self.db.userItems.find(
                {
                    "userId": user.id
                },
                {
                    "_id": 0,
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
                    "_id": 0,
                    "userId": 0
                }
            )
        return [item async for item in cursor]

    async def get_user_bag(self, user: User):
        return await self.get_user_inventory(user, BAG)

    # TODO: Replace set_user_wallet() with add_user_wallet() and remove_user_wallet()
    # TODO: Replace set_user_bank() with add_user_bank() and remove_user_bank()


def setup(bot: AlisUnnamedBot):
    bot.logger.info("Loading Database extension...")
    client = AsyncIOMotorClient(environ["DB_HOST"], int(environ["DB_PORT"]), io_loop=bot.loop)
    bot.add_cog(DatabaseCog(bot, client))
