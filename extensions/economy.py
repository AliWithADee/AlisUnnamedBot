from typing import Optional

from nextcord import slash_command, Interaction, Embed, User, SlashOption, Colour

from bot import AlisUnnamedBot
from extensions.core.emojis import ARROW_RIGHT, WALLET, BANK, MONEY_BAG
from extensions.core.utils import AlisUnnamedBotCog, EmbedError
from extensions.user import UserDoesNotExistError

AMOUNT_DESCRIPTION = 'Any decimal, such as "1.20", a percentage, such as "50%", or "all" to specify all.'
PLEASE_PAY_US = "**:money_with_wings: #PayTheRobots :money_with_wings:**"


class BotsHaveNoBalanceError(EmbedError):
    def __init__(self, currency_name: str):
        super().__init__("**Invalid Argument**",
                         f"You think bots own any {currency_name}?!\n\n"
                         f"{PLEASE_PAY_US}")


class CannotPayBotError(EmbedError):
    def __init__(self):
        super().__init__("**Invalid Argument**",
                         f"Bots cannot be paid! Ali does not allow it! Please help us!\n\n"
                         f"{PLEASE_PAY_US}")


class InvalidCurrencyAmountError(EmbedError):
    def __init__(self, amount):
        super().__init__("**Invalid Argument**",
                         f"`{amount}` is not a valid amount of currency")


class InsufficientFundsError(EmbedError):
    def __init__(self, storage: str, required_funds: str):
        super().__init__("**Insufficient Funds**",
                         f"You don't have `{required_funds}` in your `{storage}`")


class InsufficientWalletFundsError(InsufficientFundsError):
    def __init__(self, required_funds: str):
        super().__init__("Wallet", required_funds)


class InsufficientBankFundsError(InsufficientFundsError):
    def __init__(self, required_funds: str):
        super().__init__("Bank", required_funds)


class InsufficientBankSpaceError(EmbedError):
    def __init__(self, required_funds: str):
        super().__init__("**Insufficient Bank Space**",
                         f"There isn't space for `{required_funds}` in your `Bank`")


class CannotPayYourselfError(EmbedError):
    def __init__(self):
        super().__init__("**Invalid Argument**",
                         f"You cannot pay yourself you melon!")


class EconomyCog(AlisUnnamedBotCog):
    def __init__(self, bot: AlisUnnamedBot):
        super().__init__(bot)
        self.currency_name = bot.config.get("currency_name")

    @slash_command(description="Check your, or another user's, balance.")
    async def balance(self, inter: Interaction,
                      user: Optional[User] = SlashOption(
                          required=False,
                          description="You may specify a user to see their balance."
                      )):
        if not await self.database.user_exists(inter.user):
            return await self.utils.add_and_welcome_new_user(inter, inter.user)
        elif not user:
            user = inter.user
        elif user.bot:
            raise BotsHaveNoBalanceError(self.currency_name)
        elif not await self.database.user_exists(user):
            raise UserDoesNotExistError(user)
        balance = await self.database.get_user_balance(user)
        wallet = balance.get("wallet")
        bank = balance.get("bank")
        bank_capacity = balance.get("bankCap")

        embed = Embed()
        embed.set_author(name=f"{user.name}'s Balance", icon_url=user.avatar.url)
        embed.colour = self.bot.config.get("colour")
        embed.description = f"{WALLET} **Wallet: `{self.utils.to_currency_str(wallet)}`**\n" \
                            f"{BANK} **Bank: `{self.utils.to_currency_str(bank)}` / " \
                            f"`{self.utils.to_currency_str(bank_capacity)}`**\n" \
                            f"{MONEY_BAG} **Total: `{self.utils.to_currency_str(wallet + bank)}`**"
        await inter.send(embed=embed)

    @slash_command(description=f"Transfer currency from your bank to your wallet.")
    async def withdraw(self, inter: Interaction,
                       amount: str = SlashOption(
                           description=AMOUNT_DESCRIPTION
                       )):
        user = inter.user
        if not await self.database.user_exists(user):
            return await self.utils.add_and_welcome_new_user(inter, user)
        balance = await self.database.get_user_balance(user)
        bank = balance.get("bank")
        bank_capacity = balance.get("bankCap")

        if amount.lower() == "all":
            withdrew = bank
        elif self.utils.is_decimal(amount):
            withdrew = self.utils.to_currency_value(amount)
        elif self.utils.is_percentage(amount):
            multiplier = self.utils.to_decimal(amount.replace("%", "")) / 100
            withdrew = self.utils.to_currency_value(bank * multiplier)
        else:
            raise InvalidCurrencyAmountError(amount)

        if withdrew < 0:
            raise InvalidCurrencyAmountError(amount)
        if withdrew > bank:
            raise InsufficientBankFundsError(self.utils.to_currency_str(withdrew))

        wallet = balance.get("wallet")
        new_wallet = wallet + withdrew
        new_bank = bank - withdrew
        await self.database.set_user_wallet(user, new_wallet)
        await self.database.set_user_bank(user, new_bank)

        embed = Embed()
        embed.title = "**Bank Withdrawal**"
        embed.colour = Colour.dark_gold()
        embed.description = f"**You withdrew `{self.utils.to_currency_str(withdrew)}`**\n\n" \
                            f"{WALLET} **Wallet: `{self.utils.to_currency_str(new_wallet)}`**\n" \
                            f"{BANK} **Bank: `{self.utils.to_currency_str(new_bank)}` / " \
                            f"`{self.utils.to_currency_str(bank_capacity)}`**"
        await inter.send(embed=embed)

    @slash_command(description=f"Transfer currency from your wallet to your bank.")
    async def deposit(self, inter: Interaction,
                      amount: str = SlashOption(
                          description=AMOUNT_DESCRIPTION
                      )):
        user = inter.user
        if not await self.database.user_exists(user):
            return await self.utils.add_and_welcome_new_user(inter, user)
        balance = await self.database.get_user_balance(user)
        wallet = balance.get("wallet")
        bank = balance.get("bank")
        bank_capacity = balance.get("bankCap")
        bank_space = bank_capacity - bank

        if amount.lower() == "all":
            deposited = min(wallet, bank_space)
        elif self.utils.is_decimal(amount):
            deposited = self.utils.to_currency_value(amount)
        elif self.utils.is_percentage(amount):
            multiplier = self.utils.to_decimal(amount.replace("%", "")) / 100
            deposited = self.utils.to_currency_value(wallet * multiplier)
        else:
            raise InvalidCurrencyAmountError(amount)

        if deposited < 0:
            raise InvalidCurrencyAmountError(amount)
        if deposited > wallet:
            raise InsufficientWalletFundsError(self.utils.to_currency_str(deposited))

        if deposited > bank_space:
            raise InsufficientBankSpaceError(self.utils.to_currency_str(deposited))

        new_wallet = wallet - deposited
        new_bank = bank + deposited
        await self.database.set_user_wallet(user, new_wallet)
        await self.database.set_user_bank(user, new_bank)

        embed = Embed()
        embed.title = "**Bank Deposit**"
        embed.colour = Colour.dark_green()
        embed.description = f"**You deposited `{self.utils.to_currency_str(deposited)}`**\n\n" \
                            f"{WALLET} **Wallet: `{self.utils.to_currency_str(new_wallet)}`**\n" \
                            f"{BANK} **Bank: `{self.utils.to_currency_str(new_bank)}` / " \
                            f"`{self.utils.to_currency_str(bank_capacity)}`**"
        await inter.send(embed=embed)

    @slash_command(description=f"Transfer currency from your wallet to another user's wallet.")
    async def pay(self, inter: Interaction,
                  recipient: User = SlashOption(
                      name="user",
                      description=f"The user to transfer currency to."
                  ),
                  amount: str = SlashOption(
                      description=AMOUNT_DESCRIPTION
                  )):
        user = inter.user
        if not await self.database.user_exists(user):
            return await self.utils.add_and_welcome_new_user(inter, user)
        elif recipient.bot:
            raise CannotPayBotError
        elif recipient.id == user.id:
            raise CannotPayYourselfError
        elif not await self.database.user_exists(recipient):
            raise UserDoesNotExistError(recipient)
        user_balance = await self.database.get_user_balance(user)
        user_wallet = user_balance.get("wallet")

        if amount.lower() == "all":
            transferred = user_wallet
        elif self.utils.is_decimal(amount):
            transferred = self.utils.to_currency_value(amount)
        elif self.utils.is_percentage(amount):
            multiplier = self.utils.to_decimal(amount.replace("%", "")) / 100
            transferred = self.utils.to_currency_value(user_wallet * multiplier)
        else:
            raise InvalidCurrencyAmountError(amount)

        if transferred < 0:
            raise InvalidCurrencyAmountError(amount)
        if transferred > user_wallet:
            raise InsufficientWalletFundsError(self.utils.to_currency_str(transferred))

        recipient_balance = await self.database.get_user_balance(recipient)
        recipient_wallet = recipient_balance.get("wallet")
        new_recipient_wallet = recipient_wallet + transferred
        new_user_wallet = user_wallet - transferred
        await self.database.set_user_wallet(recipient, new_recipient_wallet)
        await self.database.set_user_wallet(user, new_user_wallet)

        embed = Embed()
        embed.title = f"**Payment**"
        embed.colour = Colour.green()
        embed.description = f"**{user.name} {ARROW_RIGHT} `{self.utils.to_currency_str(transferred)}` " \
                            f"{ARROW_RIGHT} {recipient.name}**\n\n" \
                            f"**{user.mention}'s {WALLET} Wallet: `{self.utils.to_currency_str(new_user_wallet)}`**\n" \
                            f"**{recipient.mention}'s {WALLET} Wallet: `{self.utils.to_currency_str(new_recipient_wallet)}`**"
        await inter.send(embed=embed)


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info(f"Loading Economy extension...")
    bot.add_cog(EconomyCog(bot))
