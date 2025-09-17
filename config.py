import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    SUPERADMIN_ID = int(os.getenv('SUPERADMIN_ID', 0))
    DATABASE_NAME = 'bot_database.db'
    
    # Bot settings
    BOT_USERNAME = None  # Will be set dynamically
    
    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required in .env file")
        if not cls.SUPERADMIN_ID:
            raise ValueError("SUPERADMIN_ID is required in .env file")