import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import Config
from database import Database
from handlers import BotHandlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.config = Config
        self.db = Database()
        self.bot = None
        self.dp = None
        self.handlers = None
    
    async def initialize(self):
        """Initialize bot components"""
        try:
            # Validate configuration
            self.config.validate()
            
            # Initialize database
            await self.db.init_database()
            logger.info("Database initialized successfully")
            
            # Create bot instance
            self.bot = Bot(
                token=self.config.BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            
            # Get bot info and set username
            bot_info = await self.bot.get_me()
            self.config.BOT_USERNAME = bot_info.username
            logger.info(f"Bot initialized: @{bot_info.username}")
            
            # Create dispatcher
            self.dp = Dispatcher()
            
            # Initialize handlers
            self.handlers = BotHandlers(self.bot, self.db)
            
            # Include router
            self.dp.include_router(self.handlers.router)
            
            # Add broadcast message handler
            self.dp.message.register(
                self.handlers.admin_handlers.handle_broadcast_message,
                lambda message: (
                    message.from_user.id == self.config.SUPERADMIN_ID and
                    message.from_user.id in self.handlers.admin_handlers.broadcast_waiting and
                    message.text
                )
            )
            
            logger.info("Bot components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def start_polling(self):
        """Start bot polling"""
        try:
            logger.info("Starting bot polling...")
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Error during polling: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Cleanup resources"""
        try:
            if self.bot:
                await self.bot.session.close()
            logger.info("Bot shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

async def main():
    """Main function"""
    bot_instance = TelegramBot()
    
    try:
        await bot_instance.initialize()
        await bot_instance.start_polling()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {e}")
    finally:
        await bot_instance.shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped!")
    except Exception as e:
        print(f"❌ Critical error: {e}")
        sys.exit(1)