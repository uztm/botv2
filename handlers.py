from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from aiogram.filters import Command, ChatMemberUpdatedFilter, KICKED, LEFT, MEMBER, RESTRICTED, ADMINISTRATOR, CREATOR
from aiogram.enums import ChatType, ContentType
from aiogram.exceptions import TelegramBadRequest
import logging

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
    
    async def handle_group_message(self, message: Message):
        """Handle all group messages"""
        try:
            if not message.from_user:
                return
            
            # Skip if user is admin
            try:
                member = await self.bot.get_chat_member(message.chat.id, message.from_user.id)
                if member.status in ['administrator', 'creator']:
                    return
            except:
                pass
            
            # Update member info
            await self.db.update_group_member(
                message.chat.id,
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )
            
            should_delete = False
            reason = ""
            
            # Check for links
            if MessageAnalyzer.has_links(message):
                should_delete = True
                reason = "link tarqatmang"
            
            # Check for mentions of users not in group
            elif message.text or message.caption:
                mentions = MessageAnalyzer.extract_mentions(message)
                for mention in mentions:
                    is_in_group = await self.db.is_user_in_group(message.chat.id, mention)
                    if not is_in_group:
                        should_delete = True
                        reason = "begona foydalanuvchi mention qilish mumkin emas"
                        break
            
            # Check for potential ads
            elif MessageAnalyzer.is_potential_ad(message):
                should_delete = True
                reason = "reklama tarqatmang"
            
            if should_delete:
                try:
                    await message.delete()
                    user_mention = TextFormatter.get_user_mention(message.from_user)
                    
                    warning_msg = await message.answer(f"⚠️ {user_mention}, {reason}!")
                    
                    # Delete warning after 5 seconds
                    import asyncio
                    asyncio.create_task(self.delete_after_delay(warning_msg, 5))
                    
                except TelegramBadRequest:
                    pass  # Bot doesn't have permission to delete
                
        except Exception as e:
            logging.error(f"Error handling group message: {e}")
    
    async def handle_member_update(self, chat_member: ChatMemberUpdated):
        """Handle member join/leave events"""
        try:
            settings = await self.db.get_group_settings(chat_member.chat.id)
            if not settings.get('delete_join_leave', True):
                return
            
            if chat_member.new_chat_member.status in [MEMBER, RESTRICTED, ADMINISTRATOR, CREATOR]:
                # User joined
                await self.db.update_group_member(
                    chat_member.chat.id,
                    chat_member.new_chat_member.user.id,
                    chat_member.new_chat_member.user.username,
                    chat_member.new_chat_member.user.first_name,
                    chat_member.new_chat_member.user.last_name
                )
            elif chat_member.new_chat_member.status in [KICKED, LEFT]:
                # User left
                await self.db.remove_group_member(
                    chat_member.chat.id,
                    chat_member.new_chat_member.user.id
                )
                
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
                
                # Send welcome message
                welcome_text = """
🎉 Guruhga qo'shilganim uchun rahmat!

Men quyidagi vazifalarni bajaraman:
• Reklama va linklar ni o'chirish
• Begona mention larni aniqlash va o'chirish  
• Guruhga qo'shilish/chiqish xabarlarini o'chirish

⚠️ **Muhim:** Men to'g'ri ishlashim uchun quyidagi admin huquqlari kerak:
• Xabarlarni o'chirish
• Foydalanuvchilarni boshqarish
• Xabarlarni pinlash

Agar huquqlar to'liq berilmagan bo'lsa, iltimos admin panelidan to'g'ri huquqlar bering.
                """
                
                await self.bot.send_message(chat_member.chat.id, welcome_text)
                
        except Exception as e:
            logging.error(f"Error handling bot added to group: {e}")
    
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
        import asyncio
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except:
            pass