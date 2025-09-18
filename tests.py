#!/usr/bin/env python3
"""
Quick test script to verify user existence in Telegram group
Run this to test if the user verification method works
"""

import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

# Configure logging
logging.basicConfig(level=logging.INFO)

async def test_user_verification():
    """Test user verification for the specific case"""
    
    # Your bot token (use the same from .env)
    BOT_TOKEN = "8208519993:AAGOhKgmqGcPJp1ZFYgNX2tXbqjCLfFHh_c"  # Replace with your actual token
    
    # Test parameters
    CHAT_ID = -1002070409550  # The group ID from your logs
    USERNAME = "instagram_sattarovlifts"  # The username that's being blocked
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        print(f"🔍 Testing user verification for @{USERNAME} in chat {CHAT_ID}")
        
        # Method 1: Get chat info
        try:
            chat = await bot.get_chat(CHAT_ID)
            print(f"📊 Chat info: {chat.title} - {chat.member_count} members")
        except Exception as e:
            print(f"❌ Cannot get chat info: {e}")
        
        # Method 2: Direct user verification
        try:
            print(f"🔍 Attempting direct verification: bot.get_chat_member({CHAT_ID}, '@{USERNAME}')")
            member = await bot.get_chat_member(CHAT_ID, f"@{USERNAME}")
            
            if member:
                print(f"✅ SUCCESS: User found!")
                print(f"   User ID: {member.user.id}")
                print(f"   Username: @{member.user.username}")
                print(f"   First name: {member.user.first_name}")
                print(f"   Last name: {member.user.last_name}")
                print(f"   Status: {member.status}")
                print(f"   Is bot: {member.user.is_bot}")
                
                if member.status in ['kicked', 'left']:
                    print(f"⚠️  WARNING: User has inactive status ({member.status})")
                else:
                    print(f"✅ User is active in the group!")
                    
            else:
                print(f"❌ User object is None")
                
        except TelegramBadRequest as e:
            print(f"❌ TelegramBadRequest: {e}")
            if "user not found" in str(e).lower():
                print(f"💡 This means @{USERNAME} doesn't exist in this chat")
            elif "chat not found" in str(e).lower():
                print(f"💡 This means bot doesn't have access to chat {CHAT_ID}")
            else:
                print(f"💡 Other Telegram API error: {e}")
                
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        
        # Method 3: Check bot's permissions
        try:
            bot_member = await bot.get_chat_member(CHAT_ID, bot.id)
            print(f"🤖 Bot status in chat: {bot_member.status}")
            
            if bot_member.status == 'administrator':
                print("✅ Bot is admin - should have access to member info")
            elif bot_member.status == 'member':
                print("⚠️ Bot is regular member - limited access to member info")
            else:
                print(f"❌ Bot has unusual status: {bot_member.status}")
                
        except Exception as e:
            print(f"❌ Cannot check bot status: {e}")
        
        # Method 4: Try to get administrators
        try:
            admins = await bot.get_chat_administrators(CHAT_ID)
            print(f"👑 Found {len(admins)} administrators")
            
            # Check if our user is admin
            for admin in admins:
                if admin.user.username and admin.user.username.lower() == USERNAME.lower():
                    print(f"✅ @{USERNAME} is an administrator!")
                    break
            else:
                print(f"ℹ️ @{USERNAME} is not an administrator")
                
        except Exception as e:
            print(f"❌ Cannot get administrators: {e}")
            
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_user_verification())