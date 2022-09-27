from decimal import Decimal, ROUND_HALF_UP
from os import environ

from bson.decimal128 import Decimal128
from motor.motor_asyncio import AsyncIOMotorClient
from nextcord.ext.commands import Cog
from nextcord.user import User

from bot import AlisUnnamedBot


# Cog to handle database queries and manipulation
class DatabaseCog(Cog):
    def __init__(self, bot: AlisUnnamedBot, client: AsyncIOMotorClient):
        self.bot = bot
        self.client = client
        self.database = client[environ["DB_DATABASE"]]

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

    async def user_exists(self, user: User) -> bool:
        return await self.database.users.find_one({"userID": user.id}) is not None

    async def add_user(self, user: User) -> [int, int]:
        wallet = self.bot.config.get("new_user_wallet", 0)
        bank_capacity = self.bot.config.get("new_user_bank_cap", 0)
        await self.database.users.insert_one(
            {
                "userID": user.id,
                "level": 1,
                "exp": 0,
                "wallet": Decimal128(Decimal(str(wallet)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "bank": Decimal128("0.00"),
                "bankCap": Decimal128(Decimal(str(bank_capacity)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            }
        )
        return wallet, bank_capacity

    async def get_user_profile(self, user: User) -> dict:
        result = await self.database.users.find_one(
            {
                "userID": user.id
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
        return await self.database.users.find_one(
            {
                "userID": user.id
            },
            {
                "_id": 0,
                "level": 1,
                "exp": 1
            }
        )

    async def get_user_balance(self, user: User) -> dict:
        result = await self.database.users.find_one(
            {
                "userID": user.id
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
        return await self.database.users.update_one(
            {
                "userID": user.id
            },
            {
                "$set": {
                    "wallet": Decimal128(new_wallet)
                }
            }
        )

    async def set_user_bank(self, user: User, new_bank: Decimal):
        return await self.database.users.update_one(
            {
                "userID": user.id
            },
            {
                "$set": {
                    "bank": Decimal128(new_bank)
                }
            }
        )


def setup(bot: AlisUnnamedBot):
    bot.logger.info("Loading Database extension...")
    client = AsyncIOMotorClient(environ["DB_HOST"], int(environ["DB_PORT"]), io_loop=bot.loop)
    bot.add_cog(DatabaseCog(bot, client))
