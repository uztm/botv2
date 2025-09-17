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
        self.router.message.register(self.debug_group_command, Command("debug_group"), F.chat.type == ChatType.PRIVATE)
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
    
    async def debug_group_command(self, message: Message):
        """Debug command to show group members - for admin only"""
        if message.from_user.id != Config.SUPERADMIN_ID:
            await message.answer("❌ Sizda bu buyruqni ishlatish huquqi yo'q!")
            return
        
        # Ask for group ID
        if len(message.text.split()) < 2:
            groups = await self.db.get_all_groups()
            if not groups:
                await message.answer("❌ Faol guruhlar topilmadi!")
                return
                
            group_list = "\n".join([f"• {group['title']}: `{group['id']}`" for group in groups[:10]])
            await message.answer(
                f"📋 **Guruh a'zolarini ko'rish**\n\n"
                f"Faol guruhlar:\n{group_list}\n\n"
                f"Foydalanish: `/debug_group GROUP_ID`",
                parse_mode="Markdown"
            )
            return
        
        try:
            group_id = int(message.text.split()[1])
            
            # Get members from database
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                cursor = await db.execute(
                    '''SELECT user_id, username, first_name, last_name, updated_at 
                       FROM group_members WHERE group_id = ? 
                       ORDER BY updated_at DESC LIMIT 20''',
                    (group_id,)
                )
                members = await cursor.fetchall()
            
            if not members:
                await message.answer(f"❌ Guruh {group_id} uchun a'zolar topilmadi!")
                return
            
            debug_text = f"📋 **Guruh {group_id} a'zolari** ({len(members)} ta)\n\n"
            
            for i, member in enumerate(members, 1):
                user_id, username, first_name, last_name, updated_at = member
                
                name = first_name or "No name"
                if last_name:
                    name += f" {last_name}"
                
                username_str = f"@{username}" if username else "No username"
                date_str = updated_at[:10] if updated_at else "Unknown"
                
                debug_text += f"{i}. {name} ({username_str}) - ID: `{user_id}` - {date_str}\n"
            
            await message.answer(debug_text, parse_mode="Markdown")
            
        except ValueError:
            await message.answer("❌ Noto'g'ri guruh ID formati!")
        except Exception as e:
            await message.answer(f"❌ Xatolik: {str(e)}")
    
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
                        # Skip very short mentions that are likely invalid
                        if len(mention) < 3:
                            continue
                            
                        # Check if mentioned user exists in the group database
                        is_in_group = await self.db.is_user_in_group(message.chat.id, mention)
                        logging.info(f"Checking mention @{mention}: in_group={is_in_group}")
                        
                        if not is_in_group:
                            # Try to check if user exists in Telegram group (live check)
                            user_exists_in_chat = await self.check_user_in_chat_by_username(message.chat.id, mention)
                            
                            if not user_exists_in_chat:
                                # Additional validation - check if username follows Telegram rules
                                if self.is_valid_telegram_username(mention):
                                    should_delete = True
                                    reason = f"@{mention} bu guruh a'zosi emas, begona foydalanuvchilarni mention qilish taqiqlanadi"
                                    break
                                else:
                                    # Invalid username format, skip (might be false positive)
                                    logging.info(f"Skipping invalid username format: @{mention}")
                                    continue
                            else:
                                # User exists in chat but not in our database, add them
                                logging.info(f"User @{mention} verified in chat, adding to database")
                                await self.add_username_to_db(message.chat.id, mention)
            
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
                    
                    # Don't delete warning message - let it stay permanently
                    logging.info(f"Deleted message from {message.from_user.id} in {message.chat.id}: {reason}")
                    
                except TelegramBadRequest as e:
                    logging.warning(f"Could not delete message: {e}")
                except Exception as e:
                    logging.error(f"Error deleting message: {e}")
                
        except Exception as e:
            logging.error(f"Error handling group message: {e}")
    
    def is_valid_telegram_username(self, username: str) -> bool:
        """Check if username follows Telegram username rules"""
        if not username:
            return False
            
        username = username.lstrip('@')
        
        # Telegram username rules:
        # - 5-32 characters long
        # - Can contain a-z, 0-9 and underscores
        # - Must start with a letter
        # - Must end with a letter or number
        # - Cannot have two consecutive underscores
        
        if len(username) < 5 or len(username) > 32:
            return False
        
        # Must start with letter
        if not username[0].isalpha():
            return False
            
        # Must end with letter or number
        if not username[-1].isalnum():
            return False
        
        # Can only contain letters, numbers, and underscores
        if not all(c.isalnum() or c == '_' for c in username):
            return False
            
        # Cannot have consecutive underscores
        if '__' in username:
            return False
            
        return True
    
    async def check_user_in_chat_by_username(self, chat_id: int, username: str) -> bool:
        """Check if user with username exists in the chat using multiple methods"""
        try:
            # Remove @ symbol if present
            username = username.lstrip('@').lower()
            
            # Method 1: Check if user is among chat administrators
            try:
                administrators = await self.bot.get_chat_administrators(chat_id)
                for admin in administrators:
                    if (admin.user.username and 
                        admin.user.username.lower() == username):
                        # Found user in administrators, add to database
                        await self.db.update_group_member(
                            chat_id,
                            admin.user.id,
                            admin.user.username,
                            admin.user.first_name,
                            admin.user.last_name
                        )
                        logging.info(f"Found @{username} in administrators and added to database")
                        return True
            except Exception as e:
                logging.warning(f"Could not get administrators for chat {chat_id}: {e}")
            
            # Method 2: Try to resolve username using Telegram's resolve method
            try:
                # This is a more restrictive approach - if we can't verify the user exists,
                # we'll block the mention to prevent spam
                chat_info = await self.bot.get_chat(chat_id)
                
                # Try to get chat member count to see if bot has enough permissions
                try:
                    member_count = await self.bot.get_chat_member_count(chat_id)
                    logging.info(f"Chat {chat_id} has {member_count} members")
                except Exception:
                    pass
                
                # If username is very short or has special characters, it's likely invalid
                if len(username) < 5 or not username.replace('_', '').isalnum():
                    logging.info(f"Username @{username} appears invalid (too short or special chars)")
                    return False
                
                # For now, if we can't verify through admin list and the username
                # is not in our database, we'll assume it doesn't exist in the group
                # This is more restrictive but prevents spam
                
                logging.info(f"Username @{username} could not be verified in group - blocking mention")
                return False
                
            except Exception as e:
                logging.warning(f"Could not verify user @{username}: {e}")
                return False
            
        except Exception as e:
            logging.warning(f"Could not check user @{username} in chat {chat_id}: {e}")
            # In case of error, be restrictive to prevent spam
            return False
    
    async def add_username_to_db(self, chat_id: int, username: str):
        """Add verified username to database with minimal info"""
        try:
            # For usernames that we've verified exist in the group but don't have user_id for,
            # we'll use a negative number as a placeholder to distinguish from real user_ids
            import hashlib
            username_clean = username.lstrip('@').lower()
            
            # Create a consistent negative ID based on username hash
            # This ensures the same username always gets the same ID
            username_hash = hashlib.md5(f"{chat_id}_{username_clean}".encode()).hexdigest()
            temp_user_id = -int(username_hash[:8], 16)  # Negative to distinguish from real IDs
            
            await self.db.update_group_member(
                chat_id,
                temp_user_id,
                username_clean,
                f"Verified_{username_clean}",  # Placeholder first name
                None
            )
            logging.info(f"Added verified username @{username_clean} to database with temp ID {temp_user_id}")
        except Exception as e:
            logging.warning(f"Could not add username @{username} to database: {e}")
    
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
                
                # Send join message deletion if enabled
                if settings.get('delete_join_leave', True) and chat_member.from_user.id != self.bot.id:
                    try:
                        # This will be handled automatically by checking message content type
                        pass
                    except Exception as e:
                        logging.warning(f"Could not handle join message: {e}")
                
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
        """Try to populate group members list from administrators"""
        try:
            # Get administrators first
            administrators = await self.bot.get_chat_administrators(chat_id)
            
            for admin in administrators:
                if admin.user.id != self.bot.id:  # Skip bot itself
                    await self.db.update_group_member(
                        chat_id,
                        admin.user.id,
                        admin.user.username,
                        admin.user.first_name,
                        admin.user.last_name
                    )
                    logging.info(f"Added administrator {admin.user.id} to group {chat_id} database")
            
            logging.info(f"Populated {len(administrators)-1} administrators for group {chat_id}")
            
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