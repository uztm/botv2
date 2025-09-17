import re
from typing import List, Optional
from aiogram.types import Message, MessageEntity

class MessageAnalyzer:
    @staticmethod
    def has_links(message: Message) -> bool:
        """Check if message contains links with improved detection"""
        if not message.text and not message.caption:
            return False
        
        text = message.text or message.caption
        
        # Check for entities first (most reliable)
        if message.entities:
            for entity in message.entities:
                if entity.type in ['url', 'text_link']:
                    return True
        
        if message.caption_entities:
            for entity in message.caption_entities:
                if entity.type in ['url', 'text_link']:
                    return True
        
        # Check for URL patterns (various formats)
        url_patterns = [
            # Standard HTTP/HTTPS URLs
            r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            # Domain patterns (with common TLDs)
            r'\b[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]*\.(?:com|org|net|edu|gov|mil|int|co|uz|ru|de|fr|uk|it|es|au|jp|cn|in|br)\b',
            # Telegram links
            r't\.me/[a-zA-Z0-9_]+',
            r'telegram\.me/[a-zA-Z0-9_]+',
            # Social media patterns
            r'(?:instagram\.com|facebook\.com|twitter\.com|youtube\.com|tiktok\.com)/[a-zA-Z0-9_.]+',
            # Short URLs
            r'\b(?:bit\.ly|tinyurl\.com|short\.link|s\.id)/[a-zA-Z0-9]+',
        ]
        
        for pattern in url_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # Check for domains with dots but exclude common false positives
        domain_pattern = r'\b[a-zA-Z0-9-]+\.[a-zA-Z]{2,}\b'
        potential_domains = re.findall(domain_pattern, text)
        
        # Filter out common false positives
        false_positives = {
            'vs.', 'etc.', 'inc.', 'ltd.', 'co.', 'mr.', 'mrs.', 'dr.', 'prof.',
            'jan.', 'feb.', 'mar.', 'apr.', 'may.', 'jun.', 'jul.', 'aug.', 'sep.', 'oct.', 'nov.', 'dec.',
            'mon.', 'tue.', 'wed.', 'thu.', 'fri.', 'sat.', 'sun.',
        }
        
        for domain in potential_domains:
            if domain.lower() not in false_positives:
                return True
        
        return False
    
    @staticmethod
    def extract_mentions(message: Message) -> List[str]:
        """Extract all mentions from message with improved accuracy"""
        mentions = []
        text = message.text or message.caption or ""
        
        # Extract from entities (most reliable)
        entities_to_check = []
        if message.entities:
            entities_to_check.extend(message.entities)
        if message.caption_entities:
            entities_to_check.extend(message.caption_entities)
        
        for entity in entities_to_check:
            if entity.type == 'mention':
                mention = text[entity.offset:entity.offset + entity.length]
                username = mention.lstrip('@').lower()
                if username and len(username) >= 3:  # Minimum username length
                    mentions.append(username)
        
        # Extract with regex as fallback (but be more careful)
        # Only look for mentions that look like valid usernames
        mention_pattern = r'@([a-zA-Z][a-zA-Z0-9_]{2,31})'  # Valid Telegram username pattern
        regex_mentions = re.findall(mention_pattern, text)
        
        for mention in regex_mentions:
            mention_lower = mention.lower()
            if mention_lower not in mentions:
                mentions.append(mention_lower)
        
        return mentions
    
    @staticmethod
    def is_potential_ad(message: Message) -> bool:
        """Check if message might be an advertisement with improved detection"""
        if not message.text and not message.caption:
            return False
        
        text = (message.text or message.caption or "").lower()
        
        # Enhanced ad keywords for multiple languages
        ad_keywords = [
            # English
            'buy', 'sell', 'discount', 'sale', 'promo', 'offer', 'deal', 'cheap', 'free', 
            'win', 'prize', 'earn money', 'work from home', 'make money', 'business opportunity',
            'investment', 'profit', 'income', 'cash', 'dollars', 'payment',
            
            # Russian
            'продам', 'куплю', 'скидка', 'акция', 'реклама', 'заработок', 'деньги',
            'бизнес', 'доход', 'прибыль', 'инвестиции', 'работа', 'вакансия',
            
            # Uzbek
            'sotib olaman', 'sotaman', 'chegirma', 'aksiya', 'reklama', 'daromad',
            'pul', 'biznes', 'ish', 'vakansiya', 'foyda',
            
            # Common spam phrases
            'click here', 'limited time', 'act now', 'special offer', 'guarantee',
            'no risk', 'free trial', 'instant', 'urgent', 'exclusive',
        ]
        
        # Check for ad keywords
        keyword_count = 0
        for keyword in ad_keywords:
            if keyword in text:
                keyword_count += 1
                if keyword_count >= 2:  # Multiple ad keywords = more likely spam
                    return True
        
        # Check for excessive emoji usage (potential spam indicator)
        if len(text) > 10:
            emoji_count = sum(1 for char in text if ord(char) > 127)
            emoji_ratio = emoji_count / len(text)
            if emoji_ratio > 0.4:  # More than 40% emojis
                return True
        
        # Check for excessive caps (shouting = potential spam)
        if len(text) > 20:
            caps_count = sum(1 for char in text if char.isupper())
            caps_ratio = caps_count / len([c for c in text if c.isalpha()])
            if caps_ratio > 0.7:  # More than 70% uppercase letters
                return True
        
        # Check for repetitive patterns (spam characteristic)
        if len(text) > 50:
            # Check for repeated phrases
            words = text.split()
            if len(words) >= 4:
                # Look for repeated sequences of 2+ words
                for i in range(len(words) - 3):
                    phrase = ' '.join(words[i:i+2])
                    remaining_text = ' '.join(words[i+2:])
                    if phrase in remaining_text:
                        return True
        
        # Check for phone number patterns (often used in ads)
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
            r'\d{3,4}[-.\s]?\d{2,3}[-.\s]?\d{2,3}[-.\s]?\d{2,3}',
        ]
        
        for pattern in phone_patterns:
            if re.search(pattern, text):
                # If message contains phone number and ad keywords, likely spam
                if keyword_count > 0:
                    return True
        
        return False
    
    @staticmethod
    def is_suspicious_content(message: Message) -> tuple[bool, str]:
        """
        Comprehensive content analysis that returns if content is suspicious
        and the reason why.
        """
        if not message.text and not message.caption:
            return False, ""
        
        text = (message.text or message.caption or "")
        
        # Check for links
        if MessageAnalyzer.has_links(message):
            return True, "contains links"
        
        # Check for potential ads
        if MessageAnalyzer.is_potential_ad(message):
            return True, "appears to be advertisement"
        
        # Check for spam patterns
        if len(text) > 10:
            # Too many repeated characters
            for char in text:
                if char * 10 in text:  # 10+ same characters in a row
                    return True, "contains spam patterns"
        
        # Check for excessive formatting
        if message.entities:
            formatting_count = sum(1 for entity in message.entities 
                                 if entity.type in ['bold', 'italic', 'underline', 'strikethrough'])
            if formatting_count > len(text.split()) // 2:  # More formatting than half the words
                return True, "excessive formatting (potential spam)"
        
        return False, ""

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