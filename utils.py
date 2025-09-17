import re
from typing import List, Optional
from aiogram.types import Message, MessageEntity

class MessageAnalyzer:
    @staticmethod
    def has_links(message: Message) -> bool:
        """Check if message contains links"""
        if not message.text and not message.caption:
            return False
        
        text = message.text or message.caption
        
        # Check for entities
        if message.entities:
            for entity in message.entities:
                if entity.type in ['url', 'text_link', 'mention']:
                    return True
        
        if message.caption_entities:
            for entity in message.caption_entities:
                if entity.type in ['url', 'text_link', 'mention']:
                    return True
        
        # Check for URL patterns
        url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        )
        if url_pattern.search(text):
            return True
        
        # Check for domain patterns
        domain_pattern = re.compile(r'\b[a-zA-Z0-9-]+\.[a-zA-Z]{2,}\b')
        if domain_pattern.search(text):
            return True
        
        return False
    
    @staticmethod
    def extract_mentions(message: Message) -> List[str]:
        """Extract all mentions from message"""
        mentions = []
        text = message.text or message.caption or ""
        
        # Extract from entities
        if message.entities:
            for entity in message.entities:
                if entity.type == 'mention':
                    mention = text[entity.offset:entity.offset + entity.length]
                    mentions.append(mention.lstrip('@'))
        
        if message.caption_entities:
            for entity in message.caption_entities:
                if entity.type == 'mention':
                    mention = text[entity.offset:entity.offset + entity.length]
                    mentions.append(mention.lstrip('@'))
        
        # Extract with regex as fallback
        mention_pattern = re.compile(r'@([a-zA-Z0-9_]+)')
        regex_mentions = mention_pattern.findall(text)
        mentions.extend(regex_mentions)
        
        return list(set(mentions))  # Remove duplicates
    
    @staticmethod
    def is_potential_ad(message: Message) -> bool:
        """Check if message might be an advertisement"""
        if not message.text and not message.caption:
            return False
        
        text = (message.text or message.caption or "").lower()
        
        # Ad keywords
        ad_keywords = [
            'продам', 'куплю', 'скидка', 'акция', 'реклама', 'заработок',
            'buy', 'sell', 'discount', 'sale', 'promo', 'offer', 'deal',
            'cheap', 'free', 'win', 'prize', 'earn money', 'work from home',
            'sotib olaman', 'sotaman', 'chegirma', 'aksiya', 'reklama'
        ]
        
        for keyword in ad_keywords:
            if keyword in text:
                return True
        
        # Check for excessive emoji usage (potential spam)
        emoji_count = sum(1 for char in text if ord(char) > 127)
        if len(text) > 0 and emoji_count / len(text) > 0.3:
            return True
        
        return False

class TextFormatter:
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape markdown special characters"""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    @staticmethod
    def get_user_mention(user) -> str:
        """Get user mention string"""
        if hasattr(user, 'username') and user.username:
            return f"@{user.username}"
        elif hasattr(user, 'first_name'):
            name = user.first_name
            if hasattr(user, 'last_name') and user.last_name:
                name += f" {user.last_name}"
            return name
        else:
            return "User"