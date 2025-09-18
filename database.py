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
                    is_verified BOOLEAN DEFAULT FALSE,
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
            
            # Create index for faster username lookups
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_group_members_username 
                ON group_members (group_id, username)
            ''')
            
            # Create index for verified members
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_group_members_verified 
                ON group_members (group_id, is_verified)
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
                                first_name: str = None, last_name: str = None, is_verified: bool = True):
        """Update or add group member with verification status"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO group_members 
                (group_id, user_id, username, first_name, last_name, is_verified, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (group_id, user_id, username, first_name, last_name, is_verified))
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
        """Check if user with username exists in group - ONLY VERIFIED USERS"""
        if not username:
            return False
        
        # Clean username (remove @ and convert to lowercase)
        username = username.lstrip('@').lower()
        
        # Skip very short usernames (likely invalid)
        if len(username) < 3:
            return False
        
        async with aiosqlite.connect(self.db_path) as db:
            # Check for exact username match (case insensitive) - ONLY verified users
            cursor = await db.execute(
                '''SELECT 1 FROM group_members 
                   WHERE group_id = ? AND LOWER(username) = ? 
                   AND username IS NOT NULL AND is_verified = TRUE''',
                (group_id, username)
            )
            result = await cursor.fetchone()
            
            return result is not None
    
    async def get_verified_members_count(self, group_id: int) -> int:
        """Get count of verified members in group"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT COUNT(*) FROM group_members WHERE group_id = ? AND is_verified = TRUE',
                (group_id,)
            )
            result = await cursor.fetchone()
            return result[0] if result else 0
    
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
    
    async def get_group_member_count(self, group_id: int) -> int:
        """Get count of all members in group"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT COUNT(*) FROM group_members WHERE group_id = ?',
                (group_id,)
            )
            result = await cursor.fetchone()
            return result[0] if result else 0
    
    async def search_user_by_username(self, group_id: int, username: str) -> Optional[Dict]:
        """Search for verified user by username in specific group"""
        if not username:
            return None
        
        username = username.lstrip('@').lower()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                '''SELECT * FROM group_members 
                   WHERE group_id = ? AND LOWER(username) = ? 
                   AND username IS NOT NULL AND is_verified = TRUE
                   ORDER BY updated_at DESC LIMIT 1''',
                (group_id, username)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def mark_user_as_verified(self, group_id: int, username: str):
        """Mark a user as verified (they actually exist in the group)"""
        if not username:
            return
        
        username = username.lstrip('@')
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                '''UPDATE group_members 
                   SET is_verified = TRUE, updated_at = CURRENT_TIMESTAMP 
                   WHERE group_id = ? AND LOWER(username) = LOWER(?)''',
                (group_id, username)
            )
            await db.commit()
    
    async def cleanup_unverified_users(self, group_id: int, days_old: int = 7):
        """Remove unverified users older than specified days"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                '''DELETE FROM group_members 
                   WHERE group_id = ? AND is_verified = FALSE 
                   AND updated_at < datetime('now', '-{} days')'''.format(days_old),
                (group_id,)
            )
            await db.commit()