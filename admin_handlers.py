from aiogram import Bot
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode
import logging
from datetime import datetime
import asyncio

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


from config import Config
from database import Database
from keyboards import Keyboards
from utils import TextFormatter

class AdminHandlers:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        self.broadcast_waiting = {}
        self.broadcast_message = None
    
    async def handle_broadcast_message(self, message: Message):
        """Handle broadcast message from admin"""
        try:
            if message.from_user.id not in self.broadcast_waiting:
                return
            
            # Remove from waiting list
            del self.broadcast_waiting[message.from_user.id]
            
            # Get all groups
            groups = await self.db.get_all_groups()
            
            if not groups:
                await message.answer("❌ Faol guruhlar topilmadi!")
                return
            
            # Confirm broadcast
            confirm_text = f"""
📢 **Broadcast Tasdiqlash**

📝 **Xabaringiz:**
{TextFormatter.escape_markdown(message.text[:500])}{'...' if len(message.text) > 500 else ''}

📊 **Jo'natiladi:**
• {len(groups)} ta faol guruhga
• Taxminan {len(groups) * 2} soniya ichida

⚠️ **Diqqat:** Bu amalni bekor qilib bo'lmaydi!

Davom etishni xohlaysizmi?
            """
            
            # Store the broadcast message
            self.broadcast_message = message
            
            await message.answer(
                confirm_text,
                reply_markup=Keyboards.get_confirmation_keyboard("broadcast"),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logging.error(f"Error handling broadcast message: {e}")
            await message.answer(f"❌ Xatolik: {str(e)}")
    
    # Replace the broadcast-related methods in your AdminHandlers class

async def handle_broadcast_message(self, message: Message):
    """Handle broadcast message from admin - FIXED VERSION"""
    try:
        logging.info(f"Admin broadcast handler called. User: {message.from_user.id}, Waiting: {message.from_user.id in self.broadcast_waiting}")
        
        if message.from_user.id not in self.broadcast_waiting:
            logging.warning(f"User {message.from_user.id} not in broadcast waiting list")
            return
        
        if not message.text:
            await message.answer("❌ Faqat matn xabarlarini broadcast qilish mumkin!")
            return
        
        # Remove from waiting list
        del self.broadcast_waiting[message.from_user.id]
        logging.info(f"Removed user {message.from_user.id} from broadcast waiting list")
        
        # Get all groups
        groups = await self.db.get_all_groups()
        
        if not groups:
            await message.answer("❌ Faol guruhlar topilmadi!")
            return
        
        logging.info(f"Found {len(groups)} groups for broadcast")
        
        # Confirm broadcast with escaped text
        confirm_text = f"""
📢 **Broadcast Tasdiqlash**

📝 **Xabaringiz:**
{TextFormatter.escape_markdown(message.text[:500])}{'...' if len(message.text) > 500 else ''}

📊 **Jo'natiladi:**
• {len(groups)} ta faol guruhga
• Taxminan {len(groups) * 2} soniya ichida

⚠️ **Diqqat:** Bu amalni bekor qilib bo'lmaydi!

Davom etishni xohlaysizmi?
        """
        
        # Store the broadcast message
        self.broadcast_message = message
        logging.info(f"Stored broadcast message with {len(message.text)} characters")
        
        await message.answer(
            confirm_text,
            reply_markup=Keyboards.get_confirmation_keyboard("broadcast"),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logging.error(f"Error handling broadcast message: {e}")
        await message.answer(f"❌ Xatolik: {str(e)}")
        # Reset waiting state on error
        if message.from_user.id in self.broadcast_waiting:
            del self.broadcast_waiting[message.from_user.id]

async def send_broadcast_confirmed(self, callback: CallbackQuery):
    """Send broadcast message to all groups - IMPROVED VERSION"""
    try:
        logging.info("Starting confirmed broadcast...")
        
        if not self.broadcast_message:
            await callback.answer("❌ Broadcast xabar topilmadi!", show_alert=True)
            logging.error("No broadcast message found")
            return
        
        groups = await self.db.get_all_groups()
        
        if not groups:
            await callback.message.edit_text("❌ Faol guruhlar topilmadi!")
            return
        
        logging.info(f"Broadcasting to {len(groups)} groups")
        
        # Start broadcasting
        status_text = f"""
📢 **Broadcast Boshlandi**

📊 **Holat:**
• Jami guruhlar: {len(groups)}
• Jo'natildi: 0
• Xatoliklar: 0
• Jarayon: 0%

⏳ Iltimos kuting...
        """
        
        status_msg = await callback.message.edit_text(
            status_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        sent_count = 0
        error_count = 0
        
        # Process each group
        for i, group in enumerate(groups, 1):
            try:
                logging.info(f"Sending broadcast to group {group['id']} ({group.get('title', 'Unknown')})")
                
                # Send the message
                await self.bot.send_message(
                    group['id'],
                    self.broadcast_message.text,
                    parse_mode=None  # Send as plain text to avoid parsing issues
                )
                sent_count += 1
                logging.info(f"Successfully sent to group {group['id']}")
                
                # Delay to avoid rate limits
                await asyncio.sleep(1)  # Increased delay for stability
                
            except Exception as e:
                error_count += 1
                logging.warning(f"Failed to send broadcast to group {group['id']}: {e}")
            
            # Update status every 3 groups or at the end
            if i % 3 == 0 or i == len(groups):
                progress = int((i / len(groups)) * 100)
                
                status_text = f"""
📢 **Broadcast Jarayoni**

📊 **Holat:**
• Jami guruhlar: {len(groups)}
• Jo'natildi: {sent_count}
• Xatoliklar: {error_count}  
• Jarayon: {progress}%

{'✅ Yakunlandi!' if i == len(groups) else '⏳ Davom etmoqda...'}
                """
                
                try:
                    await status_msg.edit_text(
                        status_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as edit_error:
                    logging.warning(f"Failed to update status message: {edit_error}")
        
        # Final summary
        success_rate = int((sent_count/len(groups))*100) if groups else 0
        final_text = f"""
✅ **Broadcast Yakunlandi!**

📊 **Natijalar:**
• Muvaffaqiyatli jo'natildi: {sent_count}
• Xatoliklar: {error_count}
• Jami guruhlar: {len(groups)}
• Muvaffaqiyat darajasi: {success_rate}%

⏰ **Vaqt:** {datetime.now().strftime('%d.%m.%Y %H:%M')}

{'🎉 Barcha guruhlarga muvaffaqiyatli jo\'natildi!' if error_count == 0 else f'⚠️ {error_count} ta guruhga jo\'natishda xatolik yuz berdi.'}
        """
        
        await status_msg.edit_text(
            final_text,
            reply_markup=Keyboards.get_admin_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Clear broadcast message
        self.broadcast_message = None
        logging.info(f"Broadcast completed: {sent_count} sent, {error_count} errors")
        
    except Exception as e:
        logging.error(f"Error sending broadcast: {e}")
        try:
            await callback.message.edit_text(
                f"❌ Broadcast yuborishda xatolik:\n{TextFormatter.escape_markdown(str(e)[:200])}...",
                reply_markup=Keyboards.get_admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            await callback.answer("❌ Broadcast xatolik!", show_alert=True)
        finally:
            # Clear broadcast message on error
            self.broadcast_message = None

async def request_broadcast_message(self, callback: CallbackQuery):
    """Request broadcast message from admin - IMPROVED VERSION"""
    try:
        # Set waiting state
        self.broadcast_waiting[callback.from_user.id] = True
        logging.info(f"Added user {callback.from_user.id} to broadcast waiting list")
        
        await callback.message.edit_text(
            """
📝 **Broadcast Xabar**

Yubormoqchi bo'lgan xabaringizni yozing:

📋 **Qo'llab-quvvatlanadigan formatlar:**
• Oddiy matn (tavsiya etiladi)
• Emoji va belgilar
• Ko'p qatorli xabarlar

⚠️ **Eslatma:** 
• Xabar barcha faol guruhlarga yuboriladi
• Formatlash (bold, italic) qo'llab-quvvatlanmaydi
• Maksimal uzunlik: 4096 belgi

💡 **Keyingi qadam:** Xabaringizni yozing va yuboring
            """,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logging.error(f"Error requesting broadcast message: {e}")
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
        # Clean up on error
        if callback.from_user.id in self.broadcast_waiting:
            del self.broadcast_waiting[callback.from_user.id]

# Add this debug method to help troubleshoot
async def debug_broadcast_status(self, message: Message):
    """Debug method to check broadcast status - for superadmin only"""
    if message.from_user.id != Config.SUPERADMIN_ID:
        return
    
    debug_info = f"""
🔍 **Broadcast Debug Info**

👤 **User:** {message.from_user.id}
📋 **Waiting List:** {list(self.broadcast_waiting.keys())}
📨 **Stored Message:** {'✅ Yes' if self.broadcast_message else '❌ No'}
🏠 **Groups Count:** {len(await self.db.get_all_groups())}

**Status:** {'🟢 Ready for broadcast' if message.from_user.id in self.broadcast_waiting else '🔴 Not waiting'}
    """
    
    await message.answer(debug_info, parse_mode=ParseMode.MARKDOWN)
    async def remove_group_confirmed(self, callback: CallbackQuery, group_id: int):
        """Remove group after confirmation"""
        try:
            success = await self.db.remove_group(group_id)
            
            if success:
                await callback.message.edit_text(
                    f"✅ **Guruh muvaffaqiyatli o'chirildi!**\n\nGuruh ID: `{group_id}`\nBarcha ma'lumotlar database'dan o'chirildi.",
                    reply_markup=Keyboards.get_admin_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                logging.info(f"Group {group_id} removed by admin {callback.from_user.id}")
            else:
                await callback.message.edit_text(
                    f"❌ **Xatolik!**\n\nGuruhni o'chirishda xatolik yuz berdi.\nGuruh ID: `{group_id}`",
                    reply_markup=Keyboards.get_admin_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                
        except Exception as e:
            logging.error(f"Error removing group {group_id}: {e}")
            await callback.message.edit_text(
                f"❌ **Xatolik!**\n\n`{TextFormatter.escape_markdown(str(e)[:200])}...`",
                reply_markup=Keyboards.get_admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def show_admin_panel(self, message: Message):
        """Show admin panel"""
        try:
            groups = await self.db.get_all_groups()
            
            admin_text = f"""
🔧 **Admin Panel**

📊 **Statistika:**
• Faol guruhlar: {len(groups)}
• Bot ID: `{self.bot.id}`
• Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}

Kerakli bo'limni tanlang:
            """
            
            await message.answer(
                admin_text,
                reply_markup=Keyboards.get_admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logging.error(f"Error showing admin panel: {e}")
            await message.answer("❌ Admin panel yuklashda xatolik yuz berdi!")
    
    async def handle_callback(self, callback: CallbackQuery):
        """Handle admin callback queries"""
        if callback.from_user.id != Config.SUPERADMIN_ID:
            await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
            return
        
        data = callback.data
        
        try:
            if data == "admin_groups":
                await self.show_groups_list(callback)
            elif data == "admin_broadcast":
                await self.show_broadcast_menu(callback)
            elif data == "admin_stats":
                await self.show_bot_stats(callback)
            elif data == "admin_settings":
                await self.show_bot_settings(callback)
            elif data == "admin_back":
                await self.show_admin_panel_callback(callback)
            elif data == "send_broadcast":
                await self.request_broadcast_message(callback)
        except Exception as e:
            logging.error(f"Error in admin callback: {e}")
            await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
    
    async def show_admin_panel_callback(self, callback: CallbackQuery):
        """Show admin panel from callback"""
        try:
            groups = await self.db.get_all_groups()
            
            admin_text = f"""
🔧 **Admin Panel**

📊 **Statistika:**
• Faol guruhlar: {len(groups)}
• Bot ID: `{self.bot.id}`
• Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}

Kerakli bo'limni tanlang:
            """
            
            await callback.message.edit_text(
                admin_text,
                reply_markup=Keyboards.get_admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logging.error(f"Error showing admin panel callback: {e}")
            await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
    
    async def show_groups_list(self, callback: CallbackQuery):
        """Show list of groups"""
        try:
            groups = await self.db.get_all_groups()
            
            if not groups:
                await callback.message.edit_text(
                    "📋 **Faol guruhlar**\n\n❌ Hozircha faol guruhlar yo'q",
                    reply_markup=Keyboards.get_admin_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            text = f"📋 **Faol guruhlar** ({len(groups)} ta)\n\nGuruhni tanlang:"
            
            await callback.message.edit_text(
                text,
                reply_markup=Keyboards.get_groups_keyboard(groups),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logging.error(f"Error showing groups list: {e}")
            await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
    
    async def show_broadcast_menu(self, callback: CallbackQuery):
        """Show broadcast menu"""
        try:
            text = """
📢 **Broadcast Menu**

Bu bo'limda barcha faol guruhlarga xabar yuborishingiz mumkin.

⚠️ **Diqqat:** 
• Xabar barcha faol guruhlarga yuboriladi
• Bekor qilib bo'lmaydi
• Spam xabarlar yubormaslik tavsiya etiladi

Davom etishni xohlaysizmi?
            """
            
            await callback.message.edit_text(
                text,
                reply_markup=Keyboards.get_broadcast_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logging.error(f"Error showing broadcast menu: {e}")
            await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
    
    async def show_bot_stats(self, callback: CallbackQuery):
        """Show bot statistics with improved error handling"""
        try:
            groups = await self.db.get_all_groups()
            
            # Calculate total members (approximate)
            total_members = 0
            active_groups = 0
            failed_groups = 0
            
            status_msg = await callback.message.edit_text(
                "📊 **Statistika yuklanmoqda...**\n\n⏳ Iltimos kutib turing...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            for i, group in enumerate(groups, 1):
                try:
                    chat = await self.bot.get_chat(group['id'])
                    if hasattr(chat, 'member_count') and chat.member_count:
                        total_members += chat.member_count
                    active_groups += 1
                    
                    # Update progress every 5 groups
                    if i % 5 == 0:
                        await status_msg.edit_text(
                            f"📊 **Statistika yuklanmoqda...**\n\n⏳ Tekshirildi: {i}/{len(groups)}\n✅ Faol: {active_groups}",
                            parse_mode=ParseMode.MARKDOWN
                        )
                except Exception as e:
                    failed_groups += 1
                    logging.warning(f"Cannot get info for group {group['id']}: {e}")
            
            # Get bot username safely
            bot_username = getattr(Config, 'BOT_USERNAME', 'Unknown')
            if bot_username and not bot_username.startswith('@'):
                bot_username = f"@{bot_username}"
            
            # Create stats text with proper escaping
            stats_text = f"""
📊 **Bot Statistikasi**

👥 **Guruhlar:**
• Jami guruhlar: {len(groups)}
• Faol guruhlar: {active_groups}
• Nofaol guruhlar: {failed_groups}
• Taxminiy a'zolar: {total_members:,}

🤖 **Bot ma'lumotlari:**
• Bot ID: `{self.bot.id}`
• Bot username: {TextFormatter.escape_markdown(bot_username or 'Unknown')}
• Ishga tushirildi: {datetime.now().strftime('%d.%m.%Y')}

⚙️ **Xususiyatlar:**
• Link tozalash: ✅
• Mention tekshirish: ✅
• Reklama aniqlash: ✅
• Join/Leave tozalash: ✅
• Tahrirlangan xabar tekshirish: ✅

🔄 **So'nggi yangilanish:** {datetime.now().strftime('%H:%M:%S')}
            """
            
            await status_msg.edit_text(
                stats_text,
                reply_markup=Keyboards.get_admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logging.error(f"Error showing bot stats: {e}")
            # Fallback to simple message without markdown
            try:
                await callback.message.edit_text(
                    f"❌ Statistika yuklashda xatolik:\n{str(e)[:100]}...",
                    reply_markup=Keyboards.get_admin_keyboard()
                )
            except:
                await callback.answer("❌ Statistika yuklashda xatolik!", show_alert=True)
    
    async def show_bot_settings(self, callback: CallbackQuery):
        """Show bot settings with improved error handling"""
        try:
            # Get database stats safely
            total_members = 0
            link_enabled = ads_enabled = join_leave_enabled = 0
            
            try:
                import aiosqlite
                async with aiosqlite.connect(self.db.db_path) as db:
                    # Count total members
                    cursor = await db.execute('SELECT COUNT(*) FROM group_members')
                    result = await cursor.fetchone()
                    total_members = result[0] if result else 0
                    
                    # Count groups with different settings
                    cursor = await db.execute('SELECT COUNT(*) FROM group_settings WHERE delete_links = 1')
                    result = await cursor.fetchone()
                    link_enabled = result[0] if result else 0
                    
                    cursor = await db.execute('SELECT COUNT(*) FROM group_settings WHERE delete_ads = 1')
                    result = await cursor.fetchone()
                    ads_enabled = result[0] if result else 0
                    
                    cursor = await db.execute('SELECT COUNT(*) FROM group_settings WHERE delete_join_leave = 1')
                    result = await cursor.fetchone()
                    join_leave_enabled = result[0] if result else 0
            except Exception as e:
                logging.warning(f"Error getting database stats: {e}")
            
            settings_text = f"""
⚙️ **Bot Sozlamalari**

🔧 **Joriy sozlamalar:**
• Avtomatik link tozalash: {link_enabled} guruhda yoqilgan
• Mention tekshirish: Barcha guruhlarda
• Reklama aniqlash: {ads_enabled} guruhda yoqilgan
• Join/Leave tozalash: {join_leave_enabled} guruhda yoqilgan

📊 **Database ma'lumotlari:**
• Jami kuzatilayotgan foydalanuvchilar: {total_members:,}
• Database hajmi: SQLite3
• So'nggi backup: Avtomatik

📝 **Qo'shimcha:**
• Ogohlantirish xabarlari: 5 soniya
• Admin huquqlari: Avtomatik tekshiriladi
• Xabar tahlili: Real-time
• Tahrirlangan xabarlar: Tekshiriladi ✅

🔒 **Xavfsizlik:**
• Superadmin ID: {Config.SUPERADMIN_ID}
• API limitleri: Faol
• Error logging: Yoqilgan

ℹ️ **Eslatma:** Ba'zi sozlamalarni o'zgartirish uchun kodda tahrirlash kerak.
            """
            
            await callback.message.edit_text(
                settings_text,
                reply_markup=Keyboards.get_admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logging.error(f"Error showing bot settings: {e}")
            try:
                await callback.message.edit_text(
                    f"❌ Sozlamalar yuklashda xatolik:\n{str(e)[:100]}...",
                    reply_markup=Keyboards.get_admin_keyboard()
                )
            except:
                await callback.answer("❌ Sozlamalar yuklashda xatolik!", show_alert=True)
    
    async def request_broadcast_message(self, callback: CallbackQuery):
        """Request broadcast message from admin"""
        try:
            self.broadcast_waiting[callback.from_user.id] = True
            
            await callback.message.edit_text(
                """
📝 **Broadcast Xabar**

Yubormoqchi bo'lgan xabaringizni yozing:

📋 **Qo'llab-quvvatlanadigan formatlar:**
• Oddiy matn
• **Bold matn**
• *Italic matn*
• `Kod`
• [Linklar](URL)

⚠️ **Eslatma:** Xabar barcha faol guruhlarga yuboriladi!
                """,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logging.error(f"Error requesting broadcast message: {e}")
            await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
    
    async def handle_group_callback(self, callback: CallbackQuery):
        """Handle group-specific callbacks"""
        if callback.from_user.id != Config.SUPERADMIN_ID:
            await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
            return
        
        data = callback.data
        
        try:
            if data.startswith("group_info_"):
                group_id = int(data.split("_")[-1])
                await self.show_group_info(callback, group_id)
            elif data.startswith("group_settings_"):
                group_id = int(data.split("_")[-1])
                await self.show_group_settings(callback, group_id)
            elif data.startswith("group_stats_"):
                group_id = int(data.split("_")[-1])
                await self.show_group_stats(callback, group_id)
            elif data.startswith("remove_group_"):
                group_id = int(data.split("_")[-1])
                await self.confirm_group_removal(callback, group_id)
            elif data.startswith("toggle_"):
                await self.handle_toggle_setting(callback, data)
        except Exception as e:
            logging.error(f"Error handling group callback: {e}")
            await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
    
    async def show_group_info(self, callback: CallbackQuery, group_id: int):
        """Show individual group information with improved error handling"""
        try:
            # Show loading message
            loading_msg = await callback.message.edit_text(
                "📋 **Ma'lumotlar yuklanmoqda...**\n\n⏳ Iltimos kutib turing...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            chat = await self.bot.get_chat(group_id)
            settings = await self.db.get_group_settings(group_id)
            
            # Get member count from database
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                cursor = await db.execute(
                    'SELECT COUNT(*) FROM group_members WHERE group_id = ?',
                    (group_id,)
                )
                db_members = (await cursor.fetchone())[0]
                
                # Get group join date
                cursor = await db.execute(
                    'SELECT added_at FROM groups WHERE id = ?',
                    (group_id,)
                )
                added_result = await cursor.fetchone()
                added_date = added_result[0] if added_result else 'Noma\'lum'
            
            # Format member count safely
            member_count = getattr(chat, 'member_count', 'Noma\'lum')
            if isinstance(member_count, int):
                member_count = f"{member_count:,}"
            
            # Escape all user-generated content
            group_title = TextFormatter.escape_markdown(chat.title or "Noma'lum")
            group_username = chat.username if chat.username else "Yo'q"
            
            info_text = f"""
📋 **Guruh Ma'lumotlari**

🏷️ **Asosiy:**
• Nomi: {group_title}
• ID: `{group_id}`
• Username: @{group_username}
• Turi: {chat.type.replace('_', ' ').title()}

👥 **A'zolar:**
• Telegram ma'lumoti: {member_count}
• Database'da: {db_members:,}
• Qo'shilgan sana: {added_date[:10] if added_date != 'Noma\'lum' else added_date}

⚙️ **Sozlamalar:**
• Link tozalash: {'✅ Yoqilgan' if settings.get('delete_links') else '❌ O\'chirilgan'}
• Reklama tozalash: {'✅ Yoqilgan' if settings.get('delete_ads') else '❌ O\'chirilgan'}
• Join/Leave tozalash: {'✅ Yoqilgan' if settings.get('delete_join_leave') else '❌ O\'chirilgan'}

🛡️ **Himoya holati:**
• Bot admin huquqi: {'✅' if await self.check_bot_admin(group_id) else '❌'}
• Faollik: {'✅ Faol' if settings else '❌ Nofaol'}

🔄 **So'nggi yangilanish:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
            """
            
            await loading_msg.edit_text(
                info_text,
                reply_markup=Keyboards.get_group_info_keyboard(group_id),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logging.error(f"Error showing group info: {e}")
            try:
                await callback.message.edit_text(
                    f"❌ **Xatolik!**\n\nGuruh ma'lumotlarini olishda xatolik:\n`{TextFormatter.escape_markdown(str(e)[:100])}...`",
                    reply_markup=Keyboards.get_admin_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                await callback.answer("❌ Ma'lumot yuklashda xatolik!", show_alert=True)
    
    async def show_group_settings(self, callback: CallbackQuery, group_id: int):
        """Show group settings with toggle options"""
        try:
            chat = await self.bot.get_chat(group_id)
            settings = await self.db.get_group_settings(group_id)
            
            # Create settings keyboard with toggles
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            
            # Settings toggles
            link_status = "✅" if settings.get('delete_links') else "❌"
            ads_status = "✅" if settings.get('delete_ads') else "❌"
            join_status = "✅" if settings.get('delete_join_leave') else "❌"
            
            builder.row(
                InlineKeyboardButton(
                    text=f"{link_status} Link tozalash",
                    callback_data=f"toggle_links_{group_id}"
                )
            )
            builder.row(
                InlineKeyboardButton(
                    text=f"{ads_status} Reklama tozalash", 
                    callback_data=f"toggle_ads_{group_id}"
                )
            )
            builder.row(
                InlineKeyboardButton(
                    text=f"{join_status} Join/Leave tozalash",
                    callback_data=f"toggle_join_{group_id}"
                )
            )
            builder.row(
                InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"group_info_{group_id}")
            )
            
            # Escape group title safely
            group_title = TextFormatter.escape_markdown(chat.title or "Noma'lum")
            
            settings_text = f"""
⚙️ **Guruh Sozlamalari**

🏷️ **Guruh:** {group_title}

📋 **Joriy sozlamalar:**

🔗 **Link tozalash:** {'✅ Yoqilgan' if settings.get('delete_links') else '❌ O\'chirilgan'}
   • URL va linklar avtomatik o'chiriladi
   • Xabar muallifi ogohlantiriladi

📢 **Reklama tozalash:** {'✅ Yoqilgan' if settings.get('delete_ads') else '❌ O\'chirilgan'}
   • Reklama kalit so'zlari aniqlanadi
   • Potentsial spam o'chiriladi

👋 **Join/Leave tozalash:** {'✅ Yoqilgan' if settings.get('delete_join_leave') else '❌ O\'chirilgan'}
   • Qo'shilish/chiqish xabarlari o'chiriladi
   • Guruh tozaligi saqlanadi

🎯 **Mention tekshirish:** ✅ Har doim yoqilgan
   • Faqat guruh a'zolarini mention qilish mumkin
   • Begona userlar mention qilish taqiqlanadi

💡 **Maslahat:** Sozlamalarni o'zgartirish uchun tegishli tugmani bosing.
            """
            
            await callback.message.edit_text(
                settings_text,
                reply_markup=builder.as_markup(),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logging.error(f"Error showing group settings: {e}")
            try:
                await callback.message.edit_text(
                    f"❌ Sozlamalarni olishda xatolik: {TextFormatter.escape_markdown(str(e)[:100])}",
                    reply_markup=Keyboards.get_group_info_keyboard(group_id),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                await callback.answer("❌ Sozlamalar yuklashda xatolik!", show_alert=True)
    
    async def handle_toggle_setting(self, callback: CallbackQuery, data: str):
        """Handle setting toggles"""
        try:
            parts = data.split('_')
            setting_type = parts[1]  # links, ads, join
            group_id = int(parts[2])
            
            # Update database
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                if setting_type == 'links':
                    await db.execute(
                        'UPDATE group_settings SET delete_links = NOT delete_links WHERE group_id = ?',
                        (group_id,)
                    )
                elif setting_type == 'ads':
                    await db.execute(
                        'UPDATE group_settings SET delete_ads = NOT delete_ads WHERE group_id = ?',
                        (group_id,)
                    )
                elif setting_type == 'join':
                    await db.execute(
                        'UPDATE group_settings SET delete_join_leave = NOT delete_join_leave WHERE group_id = ?',
                        (group_id,)
                    )
                await db.commit()
            
            await callback.answer("✅ Sozlama o'zgartirildi!")
            await self.show_group_settings(callback, group_id)
            
        except Exception as e:
            logging.error(f"Error toggling setting: {e}")
            await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
    
    async def show_group_stats(self, callback: CallbackQuery, group_id: int):
        """Show detailed group statistics with improved error handling"""
        try:
            loading_msg = await callback.message.edit_text(
                "📊 **Statistika yuklanmoqda...**\n\n⏳ Iltimos kutib turing...",
                parse_mode=ParseMode.MARKDOWN
            )
            
            chat = await self.bot.get_chat(group_id)
            
            # Get comprehensive stats from database
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                # Member count
                cursor = await db.execute(
                    'SELECT COUNT(*) FROM group_members WHERE group_id = ?',
                    (group_id,)
                )
                db_members = (await cursor.fetchone())[0]
                
                # Get recent activity (members added in last 7 days)
                cursor = await db.execute(
                    '''SELECT COUNT(*) FROM group_members 
                       WHERE group_id = ? AND updated_at > datetime('now', '-7 days')''',
                    (group_id,)
                )
                recent_activity = (await cursor.fetchone())[0]
                
                # Get group info
                cursor = await db.execute(
                    'SELECT added_at, title FROM groups WHERE id = ?',
                    (group_id,)
                )
                group_info = await cursor.fetchone()
                added_date = group_info[0] if group_info else 'Noma\'lum'
                
                # Get top active users (most recent updates)
                cursor = await db.execute(
                    '''SELECT username, first_name, last_name, updated_at 
                       FROM group_members WHERE group_id = ? 
                       ORDER BY updated_at DESC LIMIT 5''',
                    (group_id,)
                )
                top_users = await cursor.fetchall()
            
            # Calculate days since added
            days_active = "Noma'lum"
            if added_date and added_date != "Noma'lum":
                try:
                    from datetime import datetime
                    added_dt = datetime.fromisoformat(added_date.replace('Z', '+00:00'))
                    days_diff = (datetime.now() - added_dt).days
                    days_active = f"{days_diff} kun"
                except:
                    pass
            
            # Get chat member count safely
            member_count = getattr(chat, 'member_count', 0)
            
            # Escape group title
            group_title = TextFormatter.escape_markdown(chat.title or "Noma'lum")
            
            stats_text = f"""
📊 **Guruh Statistikasi**

🏷️ **Guruh:** {group_title}
🆔 **ID:** `{group_id}`

👥 **A'zolar ma'lumoti:**
• Telegram a'zolari: {member_count:,} kishi
• Database'da kuzatilayotgan: {db_members:,} kishi
• So'nggi 7 kundagi faollik: {recent_activity:,} kishi

📅 **Vaqt ma'lumotlari:**
• Botga qo'shilgan: {added_date[:10] if added_date != 'Noma\'lum' else 'Noma\'lum'}
• Faol bo'lgan vaqt: {days_active}
• So'nggi tekshiruv: {datetime.now().strftime('%d.%m.%Y %H:%M')}

🎯 **Faollik:**
• Guruh holati: {'🟢 Faol' if member_count > 0 else '🔴 Nofaol'}
• Bot admin huquqi: {'✅' if await self.check_bot_admin(group_id) else '❌'}

👑 **So'nggi faol foydalanuvchilar:**
            """
            
            # Add top users with proper escaping
            if top_users:
                for i, user in enumerate(top_users, 1):
                    username = TextFormatter.escape_markdown(user[0] or "Username yo'q")
                    name = TextFormatter.escape_markdown(user[1] or "Nom yo'q")
                    if user[2]:
                        name += f" {TextFormatter.escape_markdown(user[2])}"
                    last_seen = user[3][:10] if user[3] else "Noma'lum"
                    
                    stats_text += f"\n{i}\\. @{username} ({name}) \\- {last_seen}"
            else:
                stats_text += "\nHozircha ma'lumot yo'q"
            
            stats_text += f"\n\n🔄 **Yangilanish vaqti:** {datetime.now().strftime('%H:%M:%S')}"
            
            await loading_msg.edit_text(
                stats_text,
                reply_markup=Keyboards.get_group_info_keyboard(group_id),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logging.error(f"Error showing group stats: {e}")
            try:
                await callback.message.edit_text(
                    f"❌ **Statistikani olishda xatolik:**\n\n`{TextFormatter.escape_markdown(str(e)[:200])}...`",
                    reply_markup=Keyboards.get_group_info_keyboard(group_id),
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                await callback.answer("❌ Statistika yuklashda xatolik!", show_alert=True)
    
    async def check_bot_admin(self, group_id: int) -> bool:
        """Check if bot has admin rights in group"""
        try:
            member = await self.bot.get_chat_member(group_id, self.bot.id)
            return member.status in ['administrator', 'creator']
        except:
            return False
    
    async def confirm_group_removal(self, callback: CallbackQuery, group_id: int):
        """Confirm group removal with proper escaping"""
        try:
            chat = await self.bot.get_chat(group_id)
            
            # Get group stats for confirmation
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                cursor = await db.execute(
                    'SELECT COUNT(*) FROM group_members WHERE group_id = ?',
                    (group_id,)
                )
                member_count = (await cursor.fetchone())[0]
            
            # Escape group title
            group_title = TextFormatter.escape_markdown(chat.title or "Noma'lum")
            
            confirm_text = f"""
❌ **Guruhni O'chirish**

🏷️ **Guruh:** {group_title}
🆔 **ID:** `{group_id}`
👥 **A'zolar:** {member_count:,} kishi

⚠️ **DIQQAT! Bu amal:**
• Guruhni bot database'sidan to'liq o'chiradi
• Barcha a'zo ma'lumotlarini o'chiradi
• Guruh sozlamalarini o'chiradi
• Bekor qilib bo'lmaydi

🚨 **Muhim:**
• Bot guruhdan chiqmaydi
• Faqat botning database'si tozalanadi
• Guruh faoliyati to'xtaydi

Haqiqatan ham davom etishni xohlaysizmi?
            """
            
            await callback.message.edit_text(
                confirm_text,
                reply_markup=Keyboards.get_confirmation_keyboard("remove_group", group_id),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logging.error(f"Error in group removal confirmation: {e}")
            await callback.answer(f"Xatolik: {str(e)[:50]}...", show_alert=True)
    
    async def handle_confirm_callback(self, callback: CallbackQuery):
        """Handle confirmation callbacks"""
        if callback.from_user.id != Config.SUPERADMIN_ID:
            await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
            return
        
        data = callback.data.replace("confirm_", "")
        
        try:
            if data.startswith("remove_group_"):
                group_id = int(data.split("_")[-1])
                await self.remove_group_confirmed(callback, group_id)
            elif data == "broadcast":
                await self.send_broadcast_confirmed(callback)
        except Exception as e:
            logging.error(f"Error in confirm callback: {e}")
            await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)