from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict

class Keyboards:
    @staticmethod
    def get_start_keyboard() -> InlineKeyboardMarkup:
        """Get start command keyboard"""
        builder = InlineKeyboardBuilder()
        builder.add(
            InlineKeyboardButton(
                text="➕ Add to Group as Admin",
                url="https://t.me/YourBotUsername?startgroup=true&admin=delete_messages+ban_users+restrict_members+pin_messages"
            )
        )
        return builder.as_markup()
    
    @staticmethod
    def get_admin_keyboard() -> InlineKeyboardMarkup:
        """Get admin panel keyboard"""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📊 Active Groups", callback_data="admin_groups"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")
        )
        builder.row(
            InlineKeyboardButton(text="⚙️ Bot Stats", callback_data="admin_stats"),
            InlineKeyboardButton(text="🔧 Settings", callback_data="admin_settings")
        )
        return builder.as_markup()
    
    @staticmethod
    def get_groups_keyboard(groups: List[Dict]) -> InlineKeyboardMarkup:
        """Get groups management keyboard"""
        builder = InlineKeyboardBuilder()
        
        for group in groups[:20]:  # Limit to 20 groups
            title = group['title'][:30] + "..." if len(group['title']) > 30 else group['title']
            builder.row(
                InlineKeyboardButton(
                    text=f"📋 {title}",
                    callback_data=f"group_info_{group['id']}"
                )
            )
        
        builder.row(
            InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")
        )
        return builder.as_markup()
    
    @staticmethod
    def get_broadcast_keyboard() -> InlineKeyboardMarkup:
        """Get broadcast keyboard"""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📝 Send Broadcast", callback_data="send_broadcast"),
            InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")
        )
        return builder.as_markup()
    
    @staticmethod
    def get_group_info_keyboard(group_id: int) -> InlineKeyboardMarkup:
        """Get individual group info keyboard"""
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="⚙️ Settings", callback_data=f"group_settings_{group_id}"),
            InlineKeyboardButton(text="📊 Stats", callback_data=f"group_stats_{group_id}")
        )
        builder.row(
            InlineKeyboardButton(text="❌ Remove Group", callback_data=f"remove_group_{group_id}"),
            InlineKeyboardButton(text="🔙 Back", callback_data="admin_groups")
        )
        return builder.as_markup()
    
    @staticmethod
    def get_confirmation_keyboard(action: str, group_id: int = None) -> InlineKeyboardMarkup:
        """Get confirmation keyboard"""
        builder = InlineKeyboardBuilder()
        if group_id:
            builder.row(
                InlineKeyboardButton(text="✅ Yes", callback_data=f"confirm_{action}_{group_id}"),
                InlineKeyboardButton(text="❌ No", callback_data=f"cancel_{action}")
            )
        else:
            builder.row(
                InlineKeyboardButton(text="✅ Yes", callback_data=f"confirm_{action}"),
                InlineKeyboardButton(text="❌ No", callback_data=f"cancel_{action}")
            )
        return builder.as_markup()