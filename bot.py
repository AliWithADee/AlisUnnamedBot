import json
import logging
import os
from os import environ

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from nextcord import Intents, Interaction
from nextcord.ext.commands import Bot
from nextcord.ext.commands.errors import ExtensionError


# Formatter used by the bot logger
class ColourFormatter(logging.Formatter):
    PREFIX = "\033["
    FORMAT = "%(asctime)s : %(name)-25s : %(levelname)-8s : %(message)s"
    RESET = f"{PREFIX}0m"

    COLOURS = {
        logging.DEBUG: "32m",
        logging.INFO: "34m",
        logging.WARNING: "33m",
        logging.ERROR: "31m",
        logging.CRITICAL: "31m"
    }

    def format(self, record):
        colour = self.COLOURS.get(record.levelno)
        fmt = f"{self.PREFIX};{colour}{self.FORMAT}{self.RESET}"
        formatter = logging.Formatter(fmt)
        return formatter.format(record)


# The main Bot class for AlisUnnamedBot
class AlisUnnamedBot(Bot):
    def __init__(self, config_path: str, **kwargs):
        super().__init__(**kwargs)
        self.config_path = config_path
        self.config = {}
        self.load_config()
        self.logger = self.create_logger()

    def load_config(self) -> bool:
        if not os.path.isfile(self.config_path) and self.config_path.endswith(".json"):
            self.logger.error("Bot config is not a JSON file")
            return False
        with open(self.config_path, "r", encoding="utf-8") as file:
            self.config = json.load(file)
        self.owner_id = self.config.get("owner_id")
        return True

    def create_logger(self) -> logging.Logger:
        # Configure nextcord logger
        nextcord = logging.getLogger("nextcord")
        nextcord.setLevel(logging.INFO)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(ColourFormatter())
        nextcord.addHandler(stream_handler)

        file_handler = logging.FileHandler(filename=self.config.get("log_file_path"), encoding='utf-8', mode='w')
        file_handler.setFormatter(logging.Formatter(ColourFormatter.FORMAT))
        nextcord.addHandler(file_handler)

        # Create bot logger
        logger = nextcord.getChild(self.config.get("logger"))
        logger.setLevel(logging.DEBUG)
        return logger

    async def reload_extensions(self) -> list[str]:
        extensions_root = self.config.get("extensions_root")

        # Confirm extensions_root is valid
        if not extensions_root:
            self.logger.error("'extensions_root' is not specified in the bot config")
            return []
        elif not os.path.isdir(extensions_root):
            self.logger.error("'extensions_root' is not a directory")
            return []

        # Close MongoDB client, before unloading the database cog
        database = self.get_cog("DatabaseCog")
        if database and hasattr(database, "client") and isinstance(database.client, AsyncIOMotorClient):
            self.logger.info("Closing MongoDB client...")
            database.client.close()

        # Unload currently loaded extensions
        for extension in list(self.extensions):
            self.unload_extension(extension)

        # Load all extensions and create a list of failed extensions
        failed_extensions = []
        for dir_path, _, files in os.walk(extensions_root):
            if dir_path.endswith("__pycache__"):
                continue
            for python_file in list(filter(lambda s: (s.endswith(".py")), files)):
                path = dir_path.replace("\\", ".")
                name = python_file.replace(".py", "")
                extension = f"{path}.{name}"
                try:
                    self.load_extension(extension)
                except ExtensionError as error:
                    failed_extensions.append(extension)
                    self.logger.error(error)

        # Add UtilitiesCog and DatabaseCog to other cogs
        for cog_name in self.cogs:
            cog = self.get_cog(cog_name)
            if hasattr(cog, "utils") and cog_name != "UtilsCog":
                cog.utils = self.get_cog("UtilsCog")
            if hasattr(cog, "database") and cog_name != "DatabaseCog":
                cog.database = self.get_cog("DatabaseCog")

        return failed_extensions

    # Override default application command error handler
    # This prevents handled errors being raised in the console
    async def on_application_command_error(self, inter: Interaction, error):
        pass

    async def start(self, token: str, *, reconnect: bool = True) -> None:
        await self.reload_extensions()  # Loads extensions for the first time
        await super().start(token, reconnect=reconnect)


if __name__ == '__main__':
    load_dotenv()

    # Create client
    intents = Intents.default()
    alis_unnamed_bot = AlisUnnamedBot(config_path=environ["CONFIG_PATH"], intents=intents)

    # Run client
    alis_unnamed_bot.run(environ["TOKEN"])
