from bot import AlisUnnamedBot

# Constants for custom emojis
ICON = "<:alis_unnamed_bot:1025815376036106422>"
TICK = "<:green_tick:1019746883742216233>"
WARNING = "<:yellow_warning:1019746887970062386>"
CROSS = "<:red_cross:1019746886799855626>"
LOADING = "<a:loading:1019746885768056862>"
ARROW_LEFT_ANIMATED = "<a:left_arrow:1026887654610047067>"
ARROW_RIGHT_ANIMATED = "<a:right_arrow:1026887658330406963>"
LEVEL = ICON
WALLET = "<:wallet:1022912717599801475>"
BANK = ":bank:"
MONEY_BAG = ":moneybag:"
BACKPACK = ":school_satchel:"


def setup(bot: AlisUnnamedBot, **kwargs):
    bot.logger.info("Loading Emojis extension...")
