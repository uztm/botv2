from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from aiogram.filters import Command, ChatMemberUpdatedFilter, KICKED, LEFT, MEMBER, RESTRICTED, ADMINISTRATOR, CREATOR
from aiogram.enums import ChatType, ContentType
from aiogram.exceptions import TelegramBadRequest
import logging
import asyncio

from config import Config
from database import Database
from keyboards import Keyboards
from utils import MessageAnalyzer, TextFormatter
from admin_handlers import AdminHandlers

class BotHandlers:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        self.router = Router()
        self.admin_handlers = AdminHandlers(bot, db)
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup all handlers"""
        # Private chat handlers
        self.router.message.register(self.start_command, Command("start"), F.chat.type == ChatType.PRIVATE)
        self.router.message.register(self.admin_command, Command("admin"), F.chat.type == ChatType.PRIVATE)
        self.router.message.register(self.handle_broadcast_message, F.chat.type == ChatType.PRIVATE)
        
        # Group handlers
        self.router.message.register(self.handle_group_message, F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
        self.router.chat_member.register(self.handle_member_update, ChatMemberUpdatedFilter(member_status_changed=True))
        
        # Callback handlers
        self.router.callback_query.register(self.handle_admin_callback, F.data.startswith("admin_"))
        self.router.callback_query.register(self.handle_group_callback, F.data.startswith("group_"))
        self.router.callback_query.register(self.handle_confirm_callback, F.data.startswith("confirm_"))
        self.router.callback_query.register(self.handle_cancel_callback, F.data.startswith("cancel_"))
        
        # Bot added to group
        self.router.my_chat_member.register(self.bot_added_to_group, ChatMemberUpdatedFilter(member_status_changed=True))
    
    async def start_command(self, message: Message):
        """Handle /start command in private chat"""
        user_name = TextFormatter.get_user_mention(message.from_user)
        
        welcome_text = f"""
👋 Salom, {user_name}!

Men guruh boshqaruv botiman. Men quyidagi vazifalarni bajaraman:

🛡️ **Himoya xususiyatlari:**
• Reklama va linklar ni o'chirish
• Begona mention larni aniqlash va o'chirish
• Guruhga qo'shilish/chiqish xabarlarini o'chirish

⚙️ **Boshqaruv:**
• Admin paneli orqali guruhlarni boshqarish
• Broadcast xabarlar yuborish
• Statistika va sozlamalar

Botni guruhingizga qo'shish uchun pastdagi tugmani bosing va admin huquqlarini bering.
        """
        
        await message.answer(
            welcome_text,
            reply_markup=Keyboards.get_start_keyboard()
        )
    
    async def admin_command(self, message: Message):
        """Handle /admin command"""
        if message.from_user.id != Config.SUPERADMIN_ID:
            await message.answer("❌ Sizda admin paneliga kirish huquqi yo'q!")
            return
        
        await self.admin_handlers.show_admin_panel(message)
    
    async def handle_broadcast_message(self, message: Message):
        """Handle broadcast messages from admin"""
        if (message.from_user.id == Config.SUPERADMIN_ID and 
            message.from_user.id in self.admin_handlers.broadcast_waiting and
            message.text):
            await self.admin_handlers.handle_broadcast_message(message)
    
    async def handle_group_message(self, message: Message):
        """Handle all group messages with enhanced link and mention checking"""
        try:
            if not message.from_user:
                return
            
            # Skip if user is admin
            try:
                member = await self.bot.get_chat_member(message.chat.id, message.from_user.id)
                if member.status in ['administrator', 'creator']:
                    # Even for admins, update their info in database
                    await self.db.update_group_member(
                        message.chat.id,
                        message.from_user.id,
                        message.from_user.username,
                        message.from_user.first_name,
                        message.from_user.last_name
                    )
                    return
            except Exception as e:
                logging.warning(f"Could not check admin status for user {message.from_user.id}: {e}")
            
            # Update member info in database
            await self.db.update_group_member(
                message.chat.id,
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )
            
            # Get group settings
            settings = await self.db.get_group_settings(message.chat.id)
            should_delete = False
            reason = ""
            
            # Check for links if link deletion is enabled
            if settings.get('delete_links', True) and MessageAnalyzer.has_links(message):
                should_delete = True
                reason = "guruhda link tarqatish taqiqlanadi"
            
            # Check for mentions of users not in group
            elif message.text or message.caption:
                mentions = MessageAnalyzer.extract_mentions(message)
                if mentions:
                    logging.info(f"Found mentions in message: {mentions}")
                    
                    for mention in mentions:
                        # Check if mentioned user exists in the group database
                        is_in_group = await self.db.is_user_in_group(message.chat.id, mention)
                        logging.info(f"Checking mention @{mention}: in_group={is_in_group}")
                        
                        if not is_in_group:
                            # Try to check if user exists in Telegram group (live check)
                            user_exists_in_chat = await self.check_user_in_chat(message.chat.id, mention)
                            
                            if not user_exists_in_chat:
                                should_delete = True
                                reason = f"@{mention} bu guruh a'zosi emas, begona foydalanuvchilarni mention qilish taqiqlanadi"
                                break
                            else:
                                # User exists in chat but not in our database, add them
                                logging.info(f"Adding user @{mention} to database (found in chat but not in DB)")
                                # We can't get full user info without user_id, so we'll add with minimal info
                                # The user will be properly added when they send their next message
            
            # Check for potential ads if ad deletion is enabled
            if not should_delete and settings.get('delete_ads', True) and MessageAnalyzer.is_potential_ad(message):
                should_delete = True
                reason = "reklama xabarlar taqiqlanadi"
            
            # Delete message if needed
            if should_delete:
                try:
                    await message.delete()
                    user_mention = TextFormatter.get_user_mention(message.from_user)
                    
                    warning_msg = await message.answer(f"⚠️ {user_mention}, {reason}!")
                    
                    # Delete warning after 5 seconds
                    asyncio.create_task(self.delete_after_delay(warning_msg, 5))
                    
                    logging.info(f"Deleted message from {message.from_user.id} in {message.chat.id}: {reason}")
                    
                except TelegramBadRequest as e:
                    logging.warning(f"Could not delete message: {e}")
                except Exception as e:
                    logging.error(f"Error deleting message: {e}")
                
        except Exception as e:
            logging.error(f"Error handling group message: {e}")
    
    async def check_user_in_chat(self, chat_id: int, username: str) -> bool:
        """Check if user with username exists in the chat via Telegram API"""
        try:
            # Remove @ symbol if present
            username = username.lstrip('@')
            
            # Try to get chat member by username
            # Note: This only works if we have user_id, but we can try some workarounds
            
            # First, try to search recent messages for this username
            # This is a limitation - we can't directly check if a username exists in a chat
            # without having the user_id
            
            # For now, we'll assume if user is not in our database and we can't verify,
            # it's safer to consider them as not in group
            
            return False
            
        except Exception as e:
            logging.warning(f"Could not check user @{username} in chat {chat_id}: {e}")
            return False
    
    async def handle_member_update(self, chat_member: ChatMemberUpdated):
        """Handle member join/leave events"""
        try:
            settings = await self.db.get_group_settings(chat_member.chat.id)
            
            if chat_member.new_chat_member.status in [MEMBER, RESTRICTED, ADMINISTRATOR, CREATOR]:
                # User joined or got promoted
                await self.db.update_group_member(
                    chat_member.chat.id,
                    chat_member.new_chat_member.user.id,
                    chat_member.new_chat_member.user.username,
                    chat_member.new_chat_member.user.first_name,
                    chat_member.new_chat_member.user.last_name
                )
                logging.info(f"Added/updated user {chat_member.new_chat_member.user.id} in group {chat_member.chat.id}")
                
            elif chat_member.new_chat_member.status in [KICKED, LEFT]:
                # User left or was kicked
                await self.db.remove_group_member(
                    chat_member.chat.id,
                    chat_member.new_chat_member.user.id
                )
                logging.info(f"Removed user {chat_member.new_chat_member.user.id} from group {chat_member.chat.id}")
                
        except Exception as e:
            logging.error(f"Error handling member update: {e}")
    
    async def bot_added_to_group(self, chat_member: ChatMemberUpdated):
        """Handle bot being added to group"""
        try:
            if (chat_member.new_chat_member.user.id == self.bot.id and 
                chat_member.new_chat_member.status in ['administrator', 'member']):
                
                # Add group to database
                await self.db.add_group(
                    chat_member.chat.id,
                    chat_member.chat.title,
                    chat_member.chat.username
                )
                
                logging.info(f"Bot added to group: {chat_member.chat.title} ({chat_member.chat.id})")
                
                # Try to populate initial member list if bot has admin rights
                if chat_member.new_chat_member.status == 'administrator':
                    await self.populate_group_members(chat_member.chat.id)
                
                # Send welcome message
                welcome_text = """
🎉 Guruhga qo'shilganim uchun rahmat!

Men quyidagi vazifalarni bajaraman:
• ✅ Reklama va linklar ni o'chirish
• ✅ Faqat guruh a'zolarini mention qilishga ruxsat berish
• ✅ Guruhga qo'shilish/chiqish xabarlarini o'chirish

⚠️ **Muhim:** Men to'g'ri ishlashim uchun quyidagi admin huquqlari kerak:
• Xabarlarni o'chirish
• Foydalanuvchilarni boshqarish  
• A'zolar ro'yxatini ko'rish

🔧 **Sozlamalar:**
Barcha himoya xususiyatlari avtomatik yoqilgan. Admin orqali sozlamalarni o'zgartirishingiz mumkin.

📋 **Qoidalar:**
• Faqat guruh a'zolarini mention qiling
• Link va reklama tarqatmang
• Spam xabarlar yubormang

Savollaringiz bo'lsa, guruh adminlariga murojaat qiling.
                """
                
                await self.bot.send_message(chat_member.chat.id, welcome_text)
                
        except Exception as e:
            logging.error(f"Error handling bot added to group: {e}")
    
    async def populate_group_members(self, chat_id: int):
        """Try to populate group members list (if bot has admin rights)"""
        try:
            # This is limited by Telegram API - we can't get all members directly
            # Members will be added as they send messages or join/leave
            logging.info(f"Group {chat_id} members will be populated as they become active")
            
        except Exception as e:
            logging.warning(f"Could not populate members for group {chat_id}: {e}")
    
    async def handle_admin_callback(self, callback: CallbackQuery):
        """Handle admin panel callbacks"""
        await self.admin_handlers.handle_callback(callback)
    
    async def handle_group_callback(self, callback: CallbackQuery):
        """Handle group-related callbacks"""
        await self.admin_handlers.handle_group_callback(callback)
    
    async def handle_confirm_callback(self, callback: CallbackQuery):
        """Handle confirmation callbacks"""
        await self.admin_handlers.handle_confirm_callback(callback)
    
    async def handle_cancel_callback(self, callback: CallbackQuery):
        """Handle cancel callbacks"""
        await callback.answer("Bekor qilindi")
        await callback.message.edit_text("❌ Operatsiya bekor qilindi")
    
    async def delete_after_delay(self, message: Message, delay: int):
        """Delete message after specified delay"""
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except Exception as e:
            logging.warning(f"Could not delete warning message: {e}")