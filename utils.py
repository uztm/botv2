import re
from typing import List, Optional, Tuple
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
        """Extract all mentions from message with improved accuracy - handles mentions anywhere in text"""
        mentions = []
        text = message.text or message.caption or ""
        
        # Method 1: Extract from entities (most reliable)
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
                    if username not in mentions:  # Avoid duplicates
                        mentions.append(username)
        
        # Method 2: Extract with regex (catches mentions entities might miss)
        # This handles cases like "some message @username more text"
        # Valid Telegram username pattern - matches mentions anywhere in text
        mention_patterns = [
            # Standard @username pattern
            r'@([a-zA-Z][a-zA-Z0-9_]{2,31})(?=\s|$|[^\w])',  # Username followed by space, end, or non-word char
            # Handle cases where @ is at word boundary
            r'(?<!\w)@([a-zA-Z][a-zA-Z0-9_]{2,31})',  # @ not preceded by word character
        ]
        
        for pattern in mention_patterns:
            regex_mentions = re.findall(pattern, text)
            for mention in regex_mentions:
                mention_lower = mention.lower()
                if mention_lower not in mentions:  # Avoid duplicates
                    mentions.append(mention_lower)
        
        # Method 3: Additional cleanup and validation
        validated_mentions = []
        for mention in mentions:
            # Clean and validate each mention
            clean_mention = mention.strip().lower()
            
            # Skip empty or too short mentions
            if not clean_mention or len(clean_mention) < 3:
                continue
                
            # Skip mentions with invalid characters
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', clean_mention):
                continue
                
            # Skip if too long (Telegram max is 32 chars)
            if len(clean_mention) > 32:
                continue
                
            validated_mentions.append(clean_mention)
        
        return validated_mentions
    
    @staticmethod
    def is_potential_ad(message: Message) -> bool:
        """
        FIXED: Much more conservative ad detection to reduce false positives.
        Only flags obvious spam/ads, not regular conversation.
        """
        if not message.text and not message.caption:
            return False
        
        text = (message.text or message.caption or "").lower().strip()
        
        # Skip very short messages (likely not ads)
        if len(text) < 20:
            return False
        
        # STRONG ad indicators - only flag if multiple criteria match
        ad_score = 0
        
        # 1. Check for obvious commercial keywords (more specific)
        strong_ad_keywords = [
            # English - very specific commercial terms
            'buy now', 'click here', 'limited time', 'special offer', 'act now',
            'earn money online', 'work from home', 'make money fast', 'business opportunity',
            'get rich', 'investment opportunity', 'guaranteed profit', 'no risk money',
            'free money', 'easy money', 'passive income', 'financial freedom',
            
            # Russian - specific commercial phrases
            'купить сейчас', 'заработать деньги', 'бизнес возможность', 'гарантированная прибыль',
            'легкие деньги', 'работа на дому', 'пассивный доход', 'финансовая свобода',
            
            # Uzbek - specific commercial phrases  
            'hozir xarid qiling', 'oson pul', 'kafolatlangan foyda', 'biznes imkoniyati',
            'uyda ishlash', 'tez daromad', 'pul topish',
            
            # Crypto/MLM specific
            'bitcoin', 'cryptocurrency', 'forex', 'trading signals', 'mlm', 'pyramid',
            'referral program', 'affiliate marketing', 'network marketing'
        ]
        
        for keyword in strong_ad_keywords:
            if keyword in text:
                ad_score += 2  # Strong indicator
        
        # 2. Check for promotional phrases (medium strength)
        medium_ad_keywords = [
            'discount', 'sale', 'promo', 'offer', 'deal', 'cheap', 'free',
            'скидка', 'акция', 'распродажа', 'дешево', 'бесплатно',
            'chegirma', 'aksiya', 'arzon', 'bepul'
        ]
        
        medium_keyword_count = 0
        for keyword in medium_ad_keywords:
            if keyword in text:
                medium_keyword_count += 1
        
        # Only add score if multiple medium keywords (reduces false positives)
        if medium_keyword_count >= 2:
            ad_score += 1
        
        # 3. Check for excessive emoji usage (spam indicator)
        if len(text) > 50:
            emoji_count = sum(1 for char in text if ord(char) > 127 or char in '😀😁😂🤣😃😄😅😆😉😊😋😎😍😘🥰😗😙🤗🤔🤨🤐🤑🤫🤭🤬🙄😤😠😡🤯😳🥵🥶😱😨😰😥😢😭😩😫😖😣☹️🙁😞😓😔😟😕🤓🤒🤕🤢🤮🤧🥴😵🤪😯😴🤤😪😧🤝👋🙏💪👍👎👌✌️🤞🤟🤘👈👉☝️👆👇🤙💯🔥⭐✨💫⚡☄️🌟💥💢💨💦💧🌊💎💰💸💳💴💵💷💶🏆🥇🎯🎰🎲🛒🛍️📱💻⌚🔔🎵🎶🎤🎧🎮🎯🎲🎰🔥👀💯💢💫⚡✨🌟💥🔝🆕🆓🔄🔁')
            emoji_ratio = emoji_count / len(text)
            if emoji_ratio > 0.3:  # More than 30% emojis
                ad_score += 1
        
        # 4. Check for excessive caps (much more conservative)
        if len(text) > 30:
            letters = [c for c in text if c.isalpha()]
            if len(letters) > 10:  # Only check if enough letters
                caps_count = sum(1 for char in letters if char.isupper())
                caps_ratio = caps_count / len(letters)
                if caps_ratio > 0.8:  # More than 80% uppercase (very aggressive)
                    ad_score += 1
        
        # 5. Check for phone numbers + commercial content combination
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
            r'\d{3,4}[-.\s]?\d{2,3}[-.\s]?\d{2,3}[-.\s]?\d{2,3}',
        ]
        
        has_phone = False
        for pattern in phone_patterns:
            if re.search(pattern, text):
                has_phone = True
                break
        
        if has_phone and ad_score > 0:  # Phone + other ad indicators
            ad_score += 1
        
        # 6. Check for repetitive spam patterns (very conservative)
        if len(text) > 100:
            # Look for repeated phrases only in very long messages
            words = text.split()
            if len(words) >= 8:
                # Look for repeated sequences of 3+ words
                for i in range(len(words) - 5):
                    phrase = ' '.join(words[i:i+3])
                    remaining_text = ' '.join(words[i+3:])
                    if phrase in remaining_text and len(phrase) > 10:
                        ad_score += 1
                        break
        
        # DECISION LOGIC: Only flag as ad if score is HIGH (reduces false positives)
        # Require score of 3+ for very obvious ads
        return ad_score >= 3
    
    @staticmethod
    def is_potential_ad_debug(message: Message) -> Tuple[bool, str, int]:
        """
        DEBUG version that returns detailed information about why message was flagged
        """
        if not message.text and not message.caption:
            return False, "No text content", 0
        
        text = (message.text or message.caption or "").lower().strip()
        debug_reasons = []
        
        # Skip very short messages
        if len(text) < 20:
            return False, f"Too short ({len(text)} chars)", 0
        
        ad_score = 0
        
        # Check strong ad keywords
        strong_ad_keywords = [
            'buy now', 'click here', 'limited time', 'special offer', 'act now',
            'earn money online', 'work from home', 'make money fast', 'business opportunity',
            'get rich', 'investment opportunity', 'guaranteed profit', 'no risk money',
            'free money', 'easy money', 'passive income', 'financial freedom',
            'купить сейчас', 'заработать деньги', 'бизнес возможность', 'гарантированная прибыль',
            'легкие деньги', 'работа на дому', 'пассивный доход', 'финансовая свобода',
            'hozir xarid qiling', 'oson pul', 'kafolatlangan foyda', 'biznes imkoniyati',
            'uyda ishlash', 'tez daromad', 'pul topish',
            'bitcoin', 'cryptocurrency', 'forex', 'trading signals', 'mlm', 'pyramid',
            'referral program', 'affiliate marketing', 'network marketing'
        ]
        
        found_strong = []
        for keyword in strong_ad_keywords:
            if keyword in text:
                found_strong.append(keyword)
                ad_score += 2
        
        if found_strong:
            debug_reasons.append(f"Strong ad keywords: {found_strong}")
        
        # Check medium keywords
        medium_ad_keywords = [
            'discount', 'sale', 'promo', 'offer', 'deal', 'cheap', 'free',
            'скидка', 'акция', 'распродажа', 'дешево', 'бесплатно',
            'chegirma', 'aksiya', 'arzon', 'bepul'
        ]
        
        found_medium = []
        for keyword in medium_ad_keywords:
            if keyword in text:
                found_medium.append(keyword)
        
        if len(found_medium) >= 2:
            ad_score += 1
            debug_reasons.append(f"Multiple medium keywords: {found_medium}")
        
        # Check emoji ratio
        if len(text) > 50:
            emoji_count = sum(1 for char in text if ord(char) > 127 or char in '😀😁😂🤣😃😄😅😆😉😊😋😎😍😘🥰😗😙🤗🤔🤨🤐🤑🤫🤭🤬🙄😤😠😡🤯😳🥵🥶😱😨😰😥😢😭😩😫😖😣☹️🙁😞😓😔😟😕🤓🤒🤕🤢🤮🤧🥴😵🤪😯😴🤤😪😧🤝👋🙏💪👍👎👌✌️🤞🤟🤘👈👉☝️👆👇🤙💯🔥⭐✨💫⚡☄️🌟💥💢💨💦💧🌊💎💰💸💳💴💵💷💶🏆🥇🎯🎰🎲🛒🛍️📱💻⌚🔔🎵🎶🎤🎧🎮🎯🎲🎰🔥👀💯💢💫⚡✨🌟💥🔝🆕🆓🔄🔁')
            emoji_ratio = emoji_count / len(text)
            if emoji_ratio > 0.3:
                ad_score += 1
                debug_reasons.append(f"High emoji ratio: {emoji_ratio:.2f} ({emoji_count}/{len(text)})")
        
        # Check caps ratio
        if len(text) > 30:
            letters = [c for c in text if c.isalpha()]
            if len(letters) > 10:
                caps_count = sum(1 for char in letters if char.isupper())
                caps_ratio = caps_count / len(letters)
                if caps_ratio > 0.8:
                    ad_score += 1
                    debug_reasons.append(f"High caps ratio: {caps_ratio:.2f} ({caps_count}/{len(letters)})")
        
        # Check phone + commercial combo
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
            r'\d{3,4}[-.\s]?\d{2,3}[-.\s]?\d{2,3}[-.\s]?\d{2,3}',
        ]
        
        has_phone = False
        for pattern in phone_patterns:
            if re.search(pattern, text):
                has_phone = True
                break
        
        if has_phone and ad_score > 0:
            ad_score += 1
            debug_reasons.append("Phone number + commercial content")
        
        # Check repetitive patterns
        if len(text) > 100:
            words = text.split()
            if len(words) >= 8:
                for i in range(len(words) - 5):
                    phrase = ' '.join(words[i:i+3])
                    remaining_text = ' '.join(words[i+3:])
                    if phrase in remaining_text and len(phrase) > 10:
                        ad_score += 1
                        debug_reasons.append(f"Repetitive pattern: '{phrase}'")
                        break
        
        is_ad = ad_score >= 3
        reason = "; ".join(debug_reasons) if debug_reasons else "No ad indicators found"
        
        return is_ad, reason, ad_score
    
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
        
        # Check for potential ads (using the FIXED version)
        if MessageAnalyzer.is_potential_ad(message):
            return True, "appears to be advertisement"
        
        # Check for spam patterns (more conservative)
        if len(text) > 20:
            # Too many repeated characters (must be excessive)
            for char in text:
                if char * 15 in text:  # 15+ same characters in a row (was 10)
                    return True, "contains spam patterns"
        
        # Check for excessive formatting (more conservative)
        if message.entities and len(text.split()) > 5:
            formatting_count = sum(1 for entity in message.entities 
                                 if entity.type in ['bold', 'italic', 'underline', 'strikethrough'])
            if formatting_count > len(text.split()):  # More formatting than words (was half)
                return True, "excessive formatting (potential spam)"
        
        return False, ""


# Debug function to add to your handlers.py
async def debug_message_command(self, message: Message):
    """Debug command to test ad detection - for superadmin only"""
    if message.from_user.id != Config.SUPERADMIN_ID:
        await message.answer("❌ Sizda bu buyruqni ishlatish huquqi yo'q!")
        return
    
    # Get the text to analyze (reply to a message or provide text)
    target_message = message.reply_to_message if message.reply_to_message else message
    
    if not target_message or (not target_message.text and not target_message.caption):
        await message.answer("❌ Test qilish uchun matn bilan xabar yozing yoki xabarga reply qiling!")
        return
    
    # Analyze the message
    is_ad, reason, score = MessageAnalyzer.is_potential_ad_debug(target_message)
    has_links = MessageAnalyzer.has_links(target_message)
    mentions = MessageAnalyzer.extract_mentions(target_message)
    
    text = target_message.text or target_message.caption
    
    debug_text = f"""
🔍 **Xabar tahlili**

📝 **Matn:** `{text[:100]}{'...' if len(text) > 100 else ''}`
📏 **Uzunlik:** {len(text)} belgi

🚫 **Reklama tekshiruvi:**
• Ball: {score}/3+ (3+ reklama hisoblanadi)
• Natija: {'✅ Reklama EMAS' if not is_ad else '❌ REKLAMA'}
• Sabab: {reason}

🔗 **Link tekshiruvi:** {'❌ Linklar bor' if has_links else '✅ Link yo\'q'}

👥 **Mention tekshiruvi:**
• Topildi: {len(mentions)} ta
• Mention lar: {', '.join(['@' + m for m in mentions]) if mentions else 'Yo\'q'}

⚙️ **Yakuniy qaror:**
• O'chirilishi kerak: {'❌ HA' if (is_ad or has_links) else '✅ YO\'Q'}
• Sabab: {'Reklama' if is_ad else 'Linklar' if has_links else 'Xavfsiz'}
    """
    
    await message.answer(debug_text, parse_mode="Markdown")


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