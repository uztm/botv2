import aiosqlite
from typing import List, Dict, Optional
from config import Config

class Database:
    def __init__(self):
        self.db_path = Config.DATABASE_NAME
    
    async def init_database(self):
        """Initialize database with required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Groups table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    username TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # Group members table for mention validation
            await db.execute('''
                CREATE TABLE IF NOT EXISTS group_members (
                    group_id INTEGER,
                    user_id INTEGER,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (group_id, user_id),
                    FOREIGN KEY (group_id) REFERENCES groups (id)
                )
            ''')
            
            # Settings table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS group_settings (
                    group_id INTEGER PRIMARY KEY,
                    delete_join_leave BOOLEAN DEFAULT TRUE,
                    delete_links BOOLEAN DEFAULT TRUE,
                    delete_ads BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (group_id) REFERENCES groups (id)
                )
            ''')
            
            await db.commit()
    
    async def add_group(self, group_id: int, title: str, username: str = None) -> bool:
        """Add a new group to database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT OR REPLACE INTO groups (id, title, username) VALUES (?, ?, ?)',
                    (group_id, title, username)
                )
                await db.execute(
                    'INSERT OR IGNORE INTO group_settings (group_id) VALUES (?)',
                    (group_id,)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"Error adding group: {e}")
            return False
    
    async def remove_group(self, group_id: int) -> bool:
        """Remove group from database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('DELETE FROM group_members WHERE group_id = ?', (group_id,))
                await db.execute('DELETE FROM group_settings WHERE group_id = ?', (group_id,))
                await db.execute('DELETE FROM groups WHERE id = ?', (group_id,))
                await db.commit()
                return True
        except Exception as e:
            print(f"Error removing group: {e}")
            return False
    
    async def get_all_groups(self) -> List[Dict]:
        """Get all active groups"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM groups WHERE is_active = TRUE')
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def update_group_member(self, group_id: int, user_id: int, username: str = None, 
                                first_name: str = None, last_name: str = None):
        """Update or add group member"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO group_members 
                (group_id, user_id, username, first_name, last_name, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (group_id, user_id, username, first_name, last_name))
            await db.commit()
    
    async def remove_group_member(self, group_id: int, user_id: int):
        """Remove member from group"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'DELETE FROM group_members WHERE group_id = ? AND user_id = ?',
                (group_id, user_id)
            )
            await db.commit()
    
    async def is_user_in_group(self, group_id: int, username: str) -> bool:
        """Check if user with username exists in group"""
        if not username:
            return False
        
        username = username.lstrip('@').lower()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT 1 FROM group_members WHERE group_id = ? AND LOWER(username) = ?',
                (group_id, username)
            )
            result = await cursor.fetchone()
            return result is not None
    
    async def get_group_settings(self, group_id: int) -> Dict:
        """Get group settings"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM group_settings WHERE group_id = ?',
                (group_id,)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return {
                'group_id': group_id,
                'delete_join_leave': True,
                'delete_links': True,
                'delete_ads': True
            }