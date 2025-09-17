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
{message.text[:500]}{'...' if len(message.text) > 500 else ''}

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
    
    async def send_broadcast_confirmed(self, callback: CallbackQuery):
        """Send broadcast message to all groups"""
        try:
            if not self.broadcast_message:
                await callback.answer("❌ Broadcast xabar topilmadi!", show_alert=True)
                return
            
            groups = await self.db.get_all_groups()
            
            if not groups:
                await callback.message.edit_text("❌ Faol guruhlar topilmadi!")
                return
            
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
            
            for i, group in enumerate(groups, 1):
                try:
                    await self.bot.send_message(
                        group['id'],
                        self.broadcast_message.text
                    )
                    sent_count += 1
                    
                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    error_count += 1
                    logging.warning(f"Failed to send broadcast to group {group['id']}: {e}")
                
                # Update status every 5 groups or at the end
                if i % 5 == 0 or i == len(groups):
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
                    except:
                        pass  # Ignore edit errors
            
            # Final summary
            final_text = f"""
✅ **Broadcast Yakunlandi!**

📊 **Natijalar:**
• Muvaffaqiyatli jo'natildi: {sent_count}
• Xatoliklar: {error_count}
• Jami guruhlar: {len(groups)}
• Muvaffaqiyat darajasi: {int((sent_count/len(groups))*100)}%

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
            
        except Exception as e:
            logging.error(f"Error sending broadcast: {e}")
            await callback.message.edit_text(
                f"❌ Broadcast yuborishda xatolik:\n{str(e)[:200]}...",
                reply_markup=Keyboards.get_admin_keyboard()
            )
    
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
                f"❌ **Xatolik!**\n\n`{str(e)[:200]}...`",
                reply_markup=Keyboards.get_admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def show_admin_panel(self, message: Message):
        """Show admin panel"""
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
    
    async def handle_callback(self, callback: CallbackQuery):
        """Handle admin callback queries"""
        if callback.from_user.id != Config.SUPERADMIN_ID:
            await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
            return
        
        data = callback.data
        
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
    
    async def show_admin_panel_callback(self, callback: CallbackQuery):
        """Show admin panel from callback"""
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
    
    async def show_groups_list(self, callback: CallbackQuery):
        """Show list of groups"""
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
    
    async def show_broadcast_menu(self, callback: CallbackQuery):
        """Show broadcast menu"""
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
    
    async def show_bot_stats(self, callback: CallbackQuery):
        """Show bot statistics"""
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
        
        stats_text = f"""
📊 **Bot Statistikasi**

👥 **Guruhlar:**
• Jami guruhlar: {len(groups)}
• Faol guruhlar: {active_groups}
• Nofaol guruhlar: {failed_groups}
• Taxminiy a'zolar: {total_members:,}

🤖 **Bot ma'lumotlari:**
• Bot ID: `{self.bot.id}`
• Bot username: @{Config.BOT_USERNAME or 'Unknown'}
• Ishga tushirildi: {datetime.now().strftime('%d.%m.%Y')}

⚙️ **Xususiyatlar:**
• Link tozalash: ✅
• Mention tekshirish: ✅
• Reklama aniqlash: ✅
• Join/Leave tozalash: ✅

🔄 **So'nggi yangilanish:** {datetime.now().strftime('%H:%M:%S')}
        """
        
        await status_msg.edit_text(
            stats_text,
            reply_markup=Keyboards.get_admin_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_bot_settings(self, callback: CallbackQuery):
        """Show bot settings"""
        # Get database stats
        try:
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                # Count total members
                cursor = await db.execute('SELECT COUNT(*) FROM group_members')
                total_members = (await cursor.fetchone())[0]
                
                # Count groups with different settings
                cursor = await db.execute('SELECT COUNT(*) FROM group_settings WHERE delete_links = 1')
                link_enabled = (await cursor.fetchone())[0]
                
                cursor = await db.execute('SELECT COUNT(*) FROM group_settings WHERE delete_ads = 1')
                ads_enabled = (await cursor.fetchone())[0]
                
                cursor = await db.execute('SELECT COUNT(*) FROM group_settings WHERE delete_join_leave = 1')
                join_leave_enabled = (await cursor.fetchone())[0]
        except:
            total_members = 0
            link_enabled = ads_enabled = join_leave_enabled = 0
        
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
    
    async def request_broadcast_message(self, callback: CallbackQuery):
        """Request broadcast message from admin"""
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
    
    async def handle_group_callback(self, callback: CallbackQuery):
        """Handle group-specific callbacks"""
        if callback.from_user.id != Config.SUPERADMIN_ID:
            await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
            return
        
        data = callback.data
        
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
    
    async def show_group_info(self, callback: CallbackQuery, group_id: int):
        """Show individual group information"""
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
            
            # Format member count
            member_count = getattr(chat, 'member_count', 'Noma\'lum')
            if isinstance(member_count, int):
                member_count = f"{member_count:,}"
            
            info_text = f"""
📋 **Guruh Ma'lumotlari**

🏷️ **Asosiy:**
• Nomi: {TextFormatter.escape_markdown(chat.title)}
• ID: `{group_id}`
• Username: @{chat.username if chat.username else 'Yo\'q'}
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
            await callback.message.edit_text(
                f"❌ **Xatolik!**\n\nGuruh ma'lumotlarini olishda xatolik:\n`{str(e)[:100]}...`",
                reply_markup=Keyboards.get_admin_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
    
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
            
            settings_text = f"""
⚙️ **Guruh Sozlamalari**

🏷️ **Guruh:** {TextFormatter.escape_markdown(chat.title)}

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
            await callback.message.edit_text(
                f"❌ Sozlamalarni olishda xatolik: {str(e)}",
                reply_markup=Keyboards.get_group_info_keyboard(group_id)
            )
    
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
        """Show detailed group statistics"""
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
            
            # Get chat member count
            member_count = getattr(chat, 'member_count', 0)
            
            stats_text = f"""
📊 **Guruh Statistikasi**

🏷️ **Guruh:** {TextFormatter.escape_markdown(chat.title)}
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
            
            # Add top users
            if top_users:
                for i, user in enumerate(top_users, 1):
                    username = user[0] or "Username yo'q"
                    name = user[1] or "Nom yo'q"
                    if user[2]:
                        name += f" {user[2]}"
                    last_seen = user[3][:10] if user[3] else "Noma'lum"
                    
                    stats_text += f"\n{i}. @{username} ({name}) - {last_seen}"
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
            await callback.message.edit_text(
                f"❌ **Statistikani olishda xatolik:**\n\n`{str(e)[:200]}...`",
                reply_markup=Keyboards.get_group_info_keyboard(group_id),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def check_bot_admin(self, group_id: int) -> bool:
        """Check if bot has admin rights in group"""
        try:
            member = await self.bot.get_chat_member(group_id, self.bot.id)
            return member.status in ['administrator', 'creator']
        except:
            return False
    
    async def confirm_group_removal(self, callback: CallbackQuery, group_id: int):
        """Confirm group removal"""
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
            
            confirm_text = f"""
❌ **Guruhni O'chirish**

🏷️ **Guruh:** {TextFormatter.escape_markdown(chat.title)}
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
        
        if data.startswith("remove_group_"):
            group_id = int(data.split("_")[-1])
            await self.remove_group_confirmed(callback, group_id)
        elif data == "broadcast":
            await self.send_broadcast_confirmed(callback)