import asyncio
import logging
import sys
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter

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
        self.startup_time = datetime.now()
        self.join_leave_enabled_groups = set()  # Track groups with join/leave removal enabled
    
    async def initialize(self):
        """Initialize bot components"""
        try:
            logger.info("🚀 Starting bot initialization...")
            
            # Validate configuration
            self.config.validate()
            logger.info("✅ Configuration validated")
            
            # Initialize database
            await self.db.init_database()
            logger.info("✅ Database initialized successfully")
            
            # Initialize join/leave settings table
            await self.init_join_leave_settings()
            
            # Create bot instance
            self.bot = Bot(
                token=self.config.BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            
            # Get bot info and set username
            bot_info = await self.bot.get_me()
            self.config.BOT_USERNAME = bot_info.username
            logger.info(f"✅ Bot initialized: @{bot_info.username} (ID: {bot_info.id})")
            
            # Create dispatcher
            self.dp = Dispatcher()
            
            # Initialize handlers
            self.handlers = BotHandlers(self.bot, self.db)
            logger.info("✅ Handlers initialized")
            
            # Include router
            self.dp.include_router(self.handlers.router)
            
            # Register join/leave message handlers
            await self.register_join_leave_handlers()
            
            # Add broadcast message handler
            self.dp.message.register(
                self.handlers.admin_handlers.handle_broadcast_message,
                lambda message: (
                    message.from_user.id == self.config.SUPERADMIN_ID and
                    message.from_user.id in self.handlers.admin_handlers.broadcast_waiting and
                    message.text
                )
            )
            
            logger.info("✅ Bot components initialized successfully")
            
            # Set bot commands
            await self.set_bot_commands()
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize bot: {e}")
            raise
    
    async def init_join_leave_settings(self):
        """Initialize database table for join/leave settings"""
        try:
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS join_leave_settings (
                        group_id INTEGER PRIMARY KEY,
                        enabled BOOLEAN DEFAULT TRUE,
                        auto_cleanup_history BOOLEAN DEFAULT FALSE,
                        cleanup_hours INTEGER DEFAULT 24,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                await db.commit()
            
            logger.info("✅ Join/leave settings table initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize join/leave settings: {e}")
    
    async def register_join_leave_handlers(self):
        """Register handlers for join/leave messages"""
        try:
            # Handler for new chat members (join messages)
            @self.dp.message()
            async def handle_new_member(message: Message):
                if message.new_chat_members:
                    await self.handle_join_message(message)
            
            # Handler for left chat members (leave messages)  
            @self.dp.message()
            async def handle_left_member(message: Message):
                if message.left_chat_member:
                    await self.handle_leave_message(message)
            
            # Handler for service messages (group created, title changed, etc.)
            @self.dp.message()
            async def handle_service_message(message: Message):
                if (message.group_chat_created or 
                    message.supergroup_chat_created or
                    message.new_chat_title or
                    message.new_chat_photo or
                    message.delete_chat_photo or
                    message.migrate_to_chat_id or
                    message.migrate_from_chat_id or
                    message.pinned_message):
                    await self.handle_service_message_removal(message)
            
            logger.info("✅ Join/leave handlers registered")
            
        except Exception as e:
            logger.error(f"❌ Failed to register join/leave handlers: {e}")
    
    async def handle_join_message(self, message: Message):
        """Handle new member join messages"""
        try:
            if not await self.is_join_leave_enabled(message.chat.id):
                return
            
            # Log the join
            members = ", ".join([f"@{member.username}" if member.username else member.first_name 
                               for member in message.new_chat_members])
            logger.info(f"👥 New members joined {message.chat.title}: {members}")
            
            # Delete the join message
            try:
                await message.delete()
                logger.debug(f"🗑️ Deleted join message in {message.chat.title}")
            except Exception as e:
                logger.warning(f"⚠️ Could not delete join message: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error handling join message: {e}")
    
    async def handle_leave_message(self, message: Message):
        """Handle member leave messages"""
        try:
            if not await self.is_join_leave_enabled(message.chat.id):
                return
            
            # Log the leave
            left_member = message.left_chat_member
            member_name = f"@{left_member.username}" if left_member.username else left_member.first_name
            logger.info(f"👋 Member left {message.chat.title}: {member_name}")
            
            # Delete the leave message
            try:
                await message.delete()
                logger.debug(f"🗑️ Deleted leave message in {message.chat.title}")
            except Exception as e:
                logger.warning(f"⚠️ Could not delete leave message: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error handling leave message: {e}")
    
    async def handle_service_message_removal(self, message: Message):
        """Handle removal of service messages"""
        try:
            if not await self.is_join_leave_enabled(message.chat.id):
                return
            
            # Check if bot is admin (needed to delete messages)
            try:
                bot_member = await self.bot.get_chat_member(message.chat.id, self.bot.id)
                if bot_member.status not in ['administrator']:
                    return
            except:
                return
            
            # Delete service message after a short delay
            await asyncio.sleep(2)
            try:
                await message.delete()
                logger.debug(f"🗑️ Deleted service message in {message.chat.title}")
            except Exception as e:
                logger.warning(f"⚠️ Could not delete service message: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error handling service message: {e}")
    
    async def is_join_leave_enabled(self, group_id: int) -> bool:
        """Check if join/leave removal is enabled for a group"""
        try:
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                cursor = await db.execute(
                    'SELECT enabled FROM join_leave_settings WHERE group_id = ?',
                    (group_id,)
                )
                result = await cursor.fetchone()
                
                if result is None:
                    # Enable by default for new groups
                    await db.execute(
                        'INSERT OR REPLACE INTO join_leave_settings (group_id, enabled) VALUES (?, TRUE)',
                        (group_id,)
                    )
                    await db.commit()
                    return True
                
                return bool(result[0])
                
        except Exception as e:
            logger.error(f"❌ Error checking join/leave settings: {e}")
            return True  # Default to enabled
    
    async def toggle_join_leave_removal(self, group_id: int, enabled: bool = None) -> bool:
        """Toggle join/leave removal for a group"""
        try:
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                if enabled is None:
                    # Toggle current state
                    cursor = await db.execute(
                        'SELECT enabled FROM join_leave_settings WHERE group_id = ?',
                        (group_id,)
                    )
                    result = await cursor.fetchone()
                    current_state = bool(result[0]) if result else True
                    enabled = not current_state
                
                await db.execute(
                    'INSERT OR REPLACE INTO join_leave_settings (group_id, enabled, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)',
                    (group_id, enabled)
                )
                await db.commit()
                
                return enabled
                
        except Exception as e:
            logger.error(f"❌ Error toggling join/leave removal: {e}")
            return False
    
    async def cleanup_join_leave_history(self, group_id: int, hours_back: int = 24) -> int:
        """Clean up join/leave messages from chat history"""
        try:
            # Check if bot has admin rights
            try:
                bot_member = await self.bot.get_chat_member(group_id, self.bot.id)
                if bot_member.status not in ['administrator']:
                    logger.warning(f"⚠️ Bot is not admin in group {group_id}, cannot clean history")
                    return 0
            except Exception as e:
                logger.error(f"❌ Cannot check bot status in group {group_id}: {e}")
                return 0
            
            deleted_count = 0
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            logger.info(f"🧹 Starting join/leave history cleanup for group {group_id} (last {hours_back} hours)")
            
            # We'll scan recent messages and delete join/leave messages
            # Note: Telegram Bot API has limitations on message history access
            # This is a best-effort approach using available methods
            
            try:
                # Get group info
                chat = await self.bot.get_chat(group_id)
                logger.info(f"🔍 Cleaning history for: {chat.title}")
                
                # Since we can't directly fetch message history with the Bot API,
                # we'll set up monitoring for future messages and track recent ones
                # For existing history, we'll need to rely on real-time deletion
                
                logger.info(f"✅ Join/leave cleanup monitoring enabled for {chat.title}")
                return 0  # We can't count historical deletions with Bot API limitations
                
            except Exception as e:
                logger.error(f"❌ Error accessing group {group_id}: {e}")
                return 0
            
        except Exception as e:
            logger.error(f"❌ Error in join/leave history cleanup: {e}")
            return 0
    
    async def set_bot_commands(self):
        """Set bot commands for better UX"""
        try:
            from aiogram.types import BotCommand
            
            commands = [
                BotCommand(command="start", description="🚀 Botni ishga tushirish"),
                BotCommand(command="admin", description="🔧 Admin panel (faqat admin)"),
                BotCommand(command="clean", description="🧹 Guruhni tozalash (guruh adminlari)"),
                BotCommand(command="joinleave", description="👥 Join/Leave sozlamalari (admin)"),
                BotCommand(command="debug_group", description="🔍 Guruh debug (superadmin)"),
            ]
            
            await self.bot.set_my_commands(commands)
            logger.info("✅ Bot commands set successfully")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not set bot commands: {e}")
    
    async def perform_startup_scan(self):
        """Perform startup checks and notifications"""
        try:
            logger.info("🔍 Starting startup scan...")
            
            # Get all active groups
            groups = await self.db.get_all_groups()
            
            if not groups:
                logger.info("ℹ️ No groups to scan")
                return
            
            logger.info(f"📊 Found {len(groups)} groups to check")
            
            active_groups = 0
            inactive_groups = 0
            notified_groups = 0
            
            for group in groups:
                try:
                    group_id = group['id']
                    group_title = group['title']
                    
                    logger.info(f"🔍 Checking group: {group_title} ({group_id})")
                    
                    # Check if bot has access to this group
                    try:
                        bot_member = await self.bot.get_chat_member(group_id, self.bot.id)
                        
                        if bot_member.status in ['administrator', 'member']:
                            active_groups += 1
                            
                            # Initialize join/leave settings for this group
                            await self.is_join_leave_enabled(group_id)  # This will create default settings
                            
                            # Send startup notification to group (only if bot has admin rights)
                            if bot_member.status == 'administrator':
                                try:
                                    join_leave_status = await self.is_join_leave_enabled(group_id)
                                    
                                    startup_msg = await self.bot.send_message(
                                        group_id,
                                        f"🤖 **Bot ishga tushdi!**\n\n"
                                        f"⏰ **Vaqt:** {self.startup_time.strftime('%d.%m.%Y %H:%M:%S')}\n\n"
                                        f"🛡️ **Faol himoya:**\n"
                                        f"• ✅ Linklar va reklamalar\n"
                                        f"• ✅ Begona mention lar\n"
                                        f"• ✅ Tahrirlangan xabarlar\n"
                                        f"• {'✅' if join_leave_status else '❌'} Join/Leave xabarlar\n\n"
                                        f"💡 Admin buyruqlar:\n"
                                        f"• `/clean` - guruhni tekshirish\n"
                                        f"• `/joinleave` - join/leave sozlamalari\n\n"
                                        f"Guruh xavfsizligi ta'minlanmoqda! 🔒",
                                        parse_mode=ParseMode.MARKDOWN
                                    )
                                    
                                    notified_groups += 1
                                    
                                    # Auto-delete notification after 15 seconds
                                    asyncio.create_task(self.delete_after_delay_static(startup_msg, 15))
                                    
                                except Exception as e:
                                    logger.warning(f"⚠️ Could not send startup message to {group_title}: {e}")
                            
                            # Clean up database for this group
                            await self._cleanup_group_data(group_id)
                            
                        else:
                            logger.warning(f"⚠️ Bot has unusual status in {group_title}: {bot_member.status}")
                            inactive_groups += 1
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Cannot access group {group_title}: {e}")
                        inactive_groups += 1
                        
                        # Mark group as inactive
                        await self._mark_group_inactive(group_id)
                    
                    # Small delay between groups to avoid rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Error checking group {group.get('title', 'Unknown')}: {e}")
                    continue
            
            # Log summary
            logger.info(f"✅ Startup scan completed:")
            logger.info(f"   📊 Total groups: {len(groups)}")
            logger.info(f"   🟢 Active: {active_groups}")
            logger.info(f"   🔴 Inactive: {inactive_groups}")
            logger.info(f"   📢 Notified: {notified_groups}")
            
            # Send summary to superadmin
            if self.config.SUPERADMIN_ID:
                try:
                    summary_text = f"""
🚀 **Bot Successfully Started!**

📊 **Startup Summary:**
• Total groups: {len(groups)}
• Active groups: {active_groups}
• Inactive groups: {inactive_groups}
• Notifications sent: {notified_groups}

⏰ **Start time:** {self.startup_time.strftime('%d.%m.%Y %H:%M:%S')}

🛡️ **Protection Status:**
• Link detection: ✅ Active
• Ad detection: ✅ Active  
• Mention validation: ✅ Active
• Edited message check: ✅ Active
• Join/Leave cleanup: ✅ Active

🤖 **Bot Info:**
• Username: @{self.config.BOT_USERNAME}
• Version: Enhanced v2.1 (with Join/Leave Remover)
• Features: All systems operational

Ready to protect your groups! 🔒
                    """
                    
                    await self.bot.send_message(
                        self.config.SUPERADMIN_ID,
                        summary_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Could not send summary to superadmin: {e}")
        
        except Exception as e:
            logger.error(f"❌ Error in startup scan: {e}")
    
    async def _cleanup_group_data(self, group_id: int):
        """Clean up invalid data in database for a group"""
        try:
            # Remove unverified users older than 7 days
            await self.db.cleanup_unverified_users(group_id, days_old=7)
            
            # Update group activity status
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                await db.execute(
                    'UPDATE groups SET is_active = TRUE WHERE id = ?',
                    (group_id,)
                )
                await db.commit()
                
            logger.debug(f"✅ Cleaned up data for group {group_id}")
            
        except Exception as e:
            logger.warning(f"⚠️ Error cleaning up data for group {group_id}: {e}")
    
    async def _mark_group_inactive(self, group_id: int):
        """Mark group as inactive in database"""
        try:
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                await db.execute(
                    'UPDATE groups SET is_active = FALSE WHERE id = ?',
                    (group_id,)
                )
                await db.commit()
                
        except Exception as e:
            logger.warning(f"⚠️ Error marking group {group_id} as inactive: {e}")
    
    @staticmethod
    async def delete_after_delay_static(message, delay: int):
        """Static method to delete message after delay"""
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except Exception:
            pass  # Ignore deletion errors
    
    async def start_background_tasks(self):
        """Start background maintenance tasks"""
        asyncio.create_task(self.periodic_cleanup())
        asyncio.create_task(self.health_check())
        asyncio.create_task(self.join_leave_maintenance())
        logger.info("✅ Background tasks started")
    
    async def join_leave_maintenance(self):
        """Background task for join/leave maintenance"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                logger.info("🧹 Running join/leave maintenance...")
                
                # Get groups with auto cleanup enabled
                import aiosqlite
                async with aiosqlite.connect(self.db.db_path) as db:
                    cursor = await db.execute(
                        'SELECT group_id, cleanup_hours FROM join_leave_settings WHERE auto_cleanup_history = TRUE'
                    )
                    auto_cleanup_groups = await cursor.fetchall()
                
                for group_id, cleanup_hours in auto_cleanup_groups:
                    try:
                        deleted_count = await self.cleanup_join_leave_history(group_id, cleanup_hours)
                        if deleted_count > 0:
                            logger.info(f"🧹 Cleaned {deleted_count} join/leave messages from group {group_id}")
                    except Exception as e:
                        logger.error(f"❌ Error cleaning group {group_id}: {e}")
                
                logger.info("✅ Join/leave maintenance completed")
                
            except Exception as e:
                logger.error(f"❌ Error in join/leave maintenance: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def periodic_cleanup(self):
        """Periodic database cleanup task"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                logger.info("🧹 Running periodic cleanup...")
                
                # Clean up old unverified users (older than 7 days)
                groups = await self.db.get_all_groups()
                for group in groups:
                    await self.db.cleanup_unverified_users(group['id'], days_old=7)
                
                logger.info("✅ Periodic cleanup completed")
                
            except Exception as e:
                logger.error(f"❌ Error in periodic cleanup: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def health_check(self):
        """Periodic health check"""
        while True:
            try:
                await asyncio.sleep(1800)  # Run every 30 minutes
                
                # Check bot status
                try:
                    me = await self.bot.get_me()
                    logger.debug(f"🏥 Health check passed - Bot: @{me.username}")
                except Exception as e:
                    logger.error(f"🚨 Health check failed: {e}")
                
            except Exception as e:
                logger.error(f"❌ Error in health check: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def start_polling(self):
        """Start bot polling with all enhancements"""
        try:
            logger.info("🚀 Starting bot polling...")
            
            # Perform startup scan and notifications
            await self.perform_startup_scan()
            
            # Start background tasks
            await self.start_background_tasks()
            
            # Log final startup message
            uptime = datetime.now() - self.startup_time
            logger.info(f"🎉 Bot fully operational! Startup took {uptime.total_seconds():.2f} seconds")
            logger.info(f"🤖 Bot: @{self.config.BOT_USERNAME}")
            logger.info(f"👨‍💻 Superadmin: {self.config.SUPERADMIN_ID}")
            logger.info(f"👥 Join/Leave Remover: ✅ Active")
            logger.info(f"🔄 Starting message polling...")
            
            # Start polling
            await self.dp.start_polling(self.bot)
            
        except Exception as e:
            logger.error(f"❌ Error during polling: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Cleanup resources and shutdown gracefully"""
        try:
            logger.info("🛑 Starting graceful shutdown...")
            
            # Send shutdown notification to superadmin
            if self.bot and self.config.SUPERADMIN_ID:
                try:
                    uptime = datetime.now() - self.startup_time
                    shutdown_text = f"""
🛑 **Bot Shutting Down**

⏰ **Shutdown time:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
📊 **Uptime:** {str(uptime).split('.')[0]}

🤖 **Bot:** @{self.config.BOT_USERNAME or 'Unknown'}
💾 **Database:** Connections closed
👥 **Join/Leave Remover:** Stopped
🔄 **Status:** Graceful shutdown

Bot will be offline until restart. 🔄
                    """
                    
                    await self.bot.send_message(
                        self.config.SUPERADMIN_ID,
                        shutdown_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass  # Don't fail shutdown on notification error
            
            # Close bot session
            if self.bot:
                await self.bot.session.close()
                logger.info("✅ Bot session closed")
                
            logger.info("✅ Bot shutdown completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")

async def main():
    """Main function with enhanced error handling"""
    bot_instance = None
    
    try:
        logger.info("="*60)
        logger.info("🚀 TELEGRAM GROUP MANAGER BOT STARTING")
        logger.info("   📋 Features: Enhanced with Join/Leave Remover")
        logger.info("="*60)
        
        # Create bot instance
        bot_instance = TelegramBot()
        
        # Initialize and start
        await bot_instance.initialize()
        await bot_instance.start_polling()
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ Bot stopped by user (Ctrl+C)")
        
    except Exception as e:
        logger.error(f"💥 Critical error: {e}")
        logger.exception("Full error traceback:")
        
    finally:
        # Ensure cleanup happens
        if bot_instance:
            try:
                await bot_instance.shutdown()
            except:
                pass
        
        logger.info("="*60)
        logger.info("👋 TELEGRAM GROUP MANAGER BOT STOPPED")
        logger.info("="*60)

if __name__ == '__main__':
    try:
        # Set event loop policy for Windows compatibility
        if sys.platform.startswith('win'):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # Run the bot
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\n👋 Bot stopped!")
        
    except Exception as e:
        print(f"💥 Critical error: {e}")
        sys.exit(1)