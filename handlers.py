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
        """Debug command to show group members or verify specific user - for admin only"""
        if message.from_user.id != Config.SUPERADMIN_ID:
            await message.answer("❌ Sizda bu buyruqni ishlatish huquqi yo'q!")
            return
        
        parts = message.text.split()
        
        if len(parts) < 2:
            groups = await self.db.get_all_groups()
            if not groups:
                await message.answer("❌ Faol guruhlar topilmadi!")
                return
                
            group_list = "\n".join([f"• {group['title']}: `{group['id']}`" for group in groups[:10]])
            await message.answer(
                f"📋 **Debug Commands**\n\n"
                f"**Faol guruhlar:**\n{group_list}\n\n"
                f"**Foydalanish:**\n"
                f"`/debug_group GROUP_ID` - guruh a'zolarini ko'rish\n"
                f"`/debug_group GROUP_ID @username` - foydalanuvchini tekshirish",
                parse_mode="Markdown"
            )
            return
        
        try:
            group_id = int(parts[1])
            
            # Check if we need to verify a specific user
            if len(parts) == 3 and parts[2].startswith('@'):
                username = parts[2].lstrip('@')
                await message.answer(f"🔍 **Foydalanuvchi tekshiruvi boshlandi...**\n\nUsername: @{username}\nGuruh: {group_id}")
                
                # Check in database first
                is_in_db = await self.db.is_user_in_group(group_id, username)
                
                # Check in Telegram chat
                try:
                    member = await self.bot.get_chat_member(group_id, f"@{username}")
                    if member and member.status not in ['kicked', 'left']:
                        # User found in chat
                        if not is_in_db:
                            # Add to database as verified
                            await self.db.update_group_member(
                                group_id,
                                member.user.id,
                                member.user.username,
                                member.user.first_name,
                                member.user.last_name,
                                True  # is_verified = True
                            )
                        
                        await message.answer(
                            f"✅ **Foydalanuvchi topildi!**\n\n"
                            f"👤 **Ma'lumotlar:**\n"
                            f"• Username: @{member.user.username or username}\n"
                            f"• Ism: {member.user.first_name or 'Noma\'lum'}\n"
                            f"• Familiya: {member.user.last_name or 'Yo\'q'}\n"
                            f"• ID: `{member.user.id}`\n"
                            f"• Status: {member.status}\n"
                            f"• Database'da: {'✅ Ha' if is_in_db else '❌ Yo\'q (endi qo\'shildi)'}\n\n"
                            f"🎯 **Natija:** @{username} guruhda mavjud va verifikatsiya qilindi!",
                            parse_mode="Markdown"
                        )
                    else:
                        await message.answer(
                            f"❌ **Foydalanuvchi topilmadi!**\n\n"
                            f"• Username: @{username}\n"
                            f"• Status: {member.status if member else 'Mavjud emas'}\n"
                            f"• Database'da: {'✅ Ha' if is_in_db else '❌ Yo\'q'}\n\n"
                            f"🎯 **Natija:** @{username} guruhda mavjud emas yoki chiqib ketgan.",
                            parse_mode="Markdown"
                        )
                except Exception as e:
                    await message.answer(
                        f"❌ **Xatolik yuz berdi!**\n\n"
                        f"• Username: @{username}\n"
                        f"• Xatolik: `{str(e)[:100]}...`\n"
                        f"• Database'da: {'✅ Ha' if is_in_db else '❌ Yo\'q'}\n\n"
                        f"💡 **Sabab:** Username mavjud emas yoki bot huquqlari yetarli emas.",
                        parse_mode="Markdown"
                    )
                return
            
            # Show group members (original functionality)
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                cursor = await db.execute(
                    '''SELECT user_id, username, first_name, last_name, is_verified, updated_at 
                       FROM group_members WHERE group_id = ? 
                       ORDER BY updated_at DESC LIMIT 20''',
                    (group_id,)
                )
                members = await cursor.fetchall()
            
            if not members:
                await message.answer(f"❌ Guruh {group_id} uchun a'zolar topilmadi!")
                return
            
            verified_count = sum(1 for m in members if m[4])  # is_verified column
            debug_text = f"📋 **Guruh {group_id} a'zolari** ({len(members)} ta, {verified_count} verifikatsiya qilingan)\n\n"
            
            for i, member in enumerate(members, 1):
                user_id, username, first_name, last_name, is_verified, updated_at = member
                
                name = first_name or "No name"
                if last_name:
                    name += f" {last_name}"
                
                username_str = f"@{username}" if username else "No username"
                date_str = updated_at[:10] if updated_at else "Unknown"
                verified_icon = "✅" if is_verified else "⚠️"
                
                debug_text += f"{i}. {verified_icon} {name} ({username_str}) - ID: `{user_id}` - {date_str}\n"
            
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
                    # Even for admins, update their info in database as verified
                    await self.db.update_group_member(
                        message.chat.id,
                        message.from_user.id,
                        message.from_user.username,
                        message.from_user.first_name,
                        message.from_user.last_name,
                        True  # is_verified = True for admins
                    )
                    return
            except Exception as e:
                logging.warning(f"Could not check admin status for user {message.from_user.id}: {e}")
            
            # Update member info in database (verified since they sent a message)
            await self.db.update_group_member(
                message.chat.id,
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name,
                True  # is_verified = True for active members
            )
            
            # Get group settings
            settings = await self.db.get_group_settings(message.chat.id)
            should_delete = False
            reason = ""
            
            # Check for links if link deletion is enabled
            if settings.get('delete_links', True) and MessageAnalyzer.has_links(message):
                should_delete = True
                reason = "guruhda link tarqatish taqiqlanadi"
            
            # Check for mentions of users not in group (FIXED LOGIC)
            elif message.text or message.caption:
                mentions = MessageAnalyzer.extract_mentions(message)
                if mentions:
                    logging.info(f"Found mentions in message: {mentions}")
                    
                    # Check each mention
                    invalid_mentions = []
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
                            
                            if user_exists_in_chat:
                                # User exists in chat and verified - mark as verified in DB
                                logging.info(f"User @{mention} verified in chat, updating database")
                                await self.db.mark_user_as_verified(message.chat.id, mention)
                                # Don't add to invalid mentions since user was found and verified
                            else:
                                # User doesn't exist in chat - this is an invalid mention
                                if self.is_valid_telegram_username(mention):
                                    invalid_mentions.append(mention)
                                    logging.info(f"Username @{mention} is invalid - user not found in group")
                                else:
                                    # Invalid username format, skip (might be false positive)
                                    logging.info(f"Skipping invalid username format: @{mention}")
                                    continue
                    
                    # Only delete if there are actually invalid mentions
                    if invalid_mentions:
                        should_delete = True
                        if len(invalid_mentions) == 1:
                            reason = f"@{invalid_mentions[0]} bu guruh a'zosi emas, begona foydalanuvchilarni mention qilish taqiqlanadi"
                        else:
                            mentioned_users = ", ".join([f"@{user}" for user in invalid_mentions])
                            reason = f"{mentioned_users} bu guruh a'zolari emas, begona foydalanuvchilarni mention qilish taqiqlanadi"
            
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
                    
                    # Auto-delete warning after 30 seconds
                    asyncio.create_task(self.delete_after_delay(warning_msg, 10))
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
        """Check if user with username exists in the chat using multiple methods - RESTRICTIVE APPROACH"""
        try:
            # Remove @ symbol if present
            username = username.lstrip('@').lower()
            
            # Method 1: Check if user is among chat administrators (most reliable)
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
                            admin.user.last_name,
                            True  # is_verified = True for admins
                        )
                        logging.info(f"Found @{username} in administrators and added to database")
                        return True
            except Exception as e:
                logging.warning(f"Could not get administrators for chat {chat_id}: {e}")
            
            # Method 2: Try to get chat member count to assess our verification capabilities
            try:
                member_count = await self.bot.get_chat_member_count(chat_id)
                logging.info(f"Chat {chat_id} has {member_count} members")
                
                # For small groups, we can be more restrictive since we should know most members
                # For large groups, we might not have full member data
                if member_count <= 50:
                    # Small group - if we can't verify the user, they're probably not there
                    logging.info(f"Username @{username} could not be verified in small group - blocking mention")
                    return False
                else:
                    # Large group - harder to verify all members
                    # Still be restrictive but allow some edge cases
                    # Only allow if username follows Telegram rules exactly
                    if self.is_valid_telegram_username(username) and len(username) >= 5:
                        logging.info(f"Username @{username} in large group - cautiously allowing but monitoring")
                        return False  # Still block to be safe - change to True if you want to be more lenient
                    else:
                        logging.info(f"Username @{username} appears invalid - blocking")
                        return False
                        
            except Exception:
                # If we can't get member count, be restrictive
                pass
            
            # Method 3: If all verification methods fail, block the mention
            logging.info(f"Username @{username} could not be verified in group - blocking mention")
            return False
            
        except Exception as e:
            logging.warning(f"Could not check user @{username} in chat {chat_id}: {e}")
            # In case of error, be restrictive to prevent spam
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