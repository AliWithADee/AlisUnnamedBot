from decimal import Decimal

from aiomysql import Cursor, DictCursor, Pool
from nextcord.ext.commands import Cog
from nextcord.user import User

from bot import AlisUnnamedBot


# Cog to handle database queries and manipulation
class DatabaseCog(Cog):
    def __init__(self, bot: AlisUnnamedBot, pool: Pool):
        self.bot = bot
        self.pool = pool

    async def user_exists(self, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            cursor: Cursor = await conn.cursor()
            record = await cursor.execute(f"""
                SELECT 1 FROM User WHERE UserID = {user_id}
            """)
            return record == 1

    async def add_user(self, user: User) -> [int, int]:
        wallet = self.bot.config.get("new_user_wallet", 0)
        bank_capacity = self.bot.config.get("new_user_bank_cap", 0)
        async with self.pool.acquire() as conn:
            cursor: Cursor = await conn.cursor()
            await cursor.execute(f"""
                        INSERT INTO User (UserID, Wallet, BankCap) VALUES
                        ({user.id}, {wallet}, {bank_capacity})
                    """)
        return wallet, bank_capacity

    async def get_user_profile(self, user: User) -> dict:
        async with self.pool.acquire() as conn:
            cursor: Cursor = await conn.cursor(DictCursor)
            await cursor.execute(f"""
                SELECT Level, Wallet, Bank FROM User WHERE UserID = {user.id}
            """)
            result = await cursor.fetchone()
        return {} if result is None else result

    async def get_user_level_data(self, user: User) -> dict:
        async with self.pool.acquire() as conn:
            cursor: Cursor = await conn.cursor(DictCursor)
            await cursor.execute(f"""
                SELECT Level, Exp FROM User WHERE UserID = {user.id}
            """)
            result = await cursor.fetchone()
        return {} if result is None else result

    async def get_user_balance(self, user: User) -> dict:
        async with self.pool.acquire() as conn:
            cursor: Cursor = await conn.cursor(DictCursor)
            await cursor.execute(f"""
                SELECT Wallet, Bank, BankCap FROM User WHERE UserID = {user.id}
            """)
            result = await cursor.fetchone()
        return {} if result is None else result

    async def get_user_wallet(self, user: User) -> Decimal:
        async with self.pool.acquire() as conn:
            cursor: Cursor = await conn.cursor(DictCursor)
            await cursor.execute(f"""
                SELECT Wallet FROM User WHERE UserID = {user.id}
            """)
            result = await cursor.fetchone()
        return Decimal("0") if result is None else result.get("Wallet")

    async def set_user_wallet(self, user: User, new_wallet: Decimal):
        async with self.pool.acquire() as conn:
            cursor: Cursor = await conn.cursor(DictCursor)
            await cursor.execute(f"""
                UPDATE User SET Wallet = {new_wallet} WHERE UserID = {user.id}
            """)

    async def set_user_bank(self, user: User, new_bank: Decimal):
        async with self.pool.acquire() as conn:
            cursor: Cursor = await conn.cursor(DictCursor)
            await cursor.execute(f"""
                UPDATE User SET Bank = {new_bank} WHERE UserID = {user.id}
            """)


def setup(bot: AlisUnnamedBot, pool: Pool):
    bot.logger.info("Loading Database extension...")
    bot.add_cog(DatabaseCog(bot, pool))
