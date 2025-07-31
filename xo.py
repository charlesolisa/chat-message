import streamlit as st
import asyncio
import aiofiles
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
from gtts import gTTS
import uuid
import os
import json
import hashlib
import time
from threading import Lock
import sqlite3
from contextlib import contextmanager
import logging
from typing import Dict, List, Optional
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DB_FILE = "chat_app.db"
CACHE_DURATION = 300  # 5 minutes cache
MAX_MESSAGE_LENGTH = 1000
MAX_CHAT_HISTORY = 100
AUDIO_CACHE_DIR = "audio_cache"

# Create audio cache directory
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)

# Enhanced language options with more languages
LANGUAGE_OPTIONS = {
    'English': 'en', 'French': 'fr', 'Spanish': 'es', 'German': 'de',
    'Arabic': 'ar', 'Chinese (Simplified)': 'zh-CN', 'Chinese (Traditional)': 'zh-TW',
    'Hindi': 'hi', 'Russian': 'ru', 'Japanese': 'ja', 'Portuguese': 'pt',
    'Italian': 'it', 'Korean': 'ko', 'Dutch': 'nl', 'Turkish': 'tr',
    'Polish': 'pl', 'Swedish': 'sv', 'Norwegian': 'no', 'Danish': 'da',
    'Finnish': 'fi', 'Greek': 'el', 'Hebrew': 'he', 'Thai': 'th',
    'Vietnamese': 'vi', 'Indonesian': 'id', 'Malay': 'ms', 'Filipino': 'tl'
}

class DatabaseManager:
    """Handles all database operations with connection pooling and error handling"""
    
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.lock = Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    last_seen TIMESTAMP,
                    preferred_language TEXT DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Messages table with better indexing
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_key TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    message TEXT NOT NULL,
                    original_language TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_hash TEXT UNIQUE
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_key ON messages(chat_key)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sender ON messages(sender)')
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_file, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def check_user_exists(self, username: str) -> bool:
        """Check if username already exists and is currently active"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Check if user exists and was active in last 2 minutes (currently using the app)
                cutoff_time = datetime.now() - timedelta(minutes=2)
                cursor.execute('''
                    SELECT username FROM users 
                    WHERE username = ? AND last_seen > ?
                ''', (username, cutoff_time))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking user existence: {e}")
            return False
    
    def add_user(self, username: str, preferred_language: str = 'en') -> bool:
        """Add new user (only if username is not currently active)"""
        try:
            # Check if user is currently active
            if self.check_user_exists(username):
                return False  # User already exists and is active
            
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    # Insert or update user
                    cursor.execute('''
                        INSERT OR REPLACE INTO users (username, last_seen, preferred_language)
                        VALUES (?, CURRENT_TIMESTAMP, ?)
                    ''', (username, preferred_language))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Error adding user {username}: {e}")
            return False
    
    def get_active_users(self, minutes: int = 2) -> List[str]:
        """Get users active within specified minutes (currently using the app)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cutoff_time = datetime.now() - timedelta(minutes=minutes)
                cursor.execute('''
                    SELECT username FROM users 
                    WHERE last_seen > ? 
                    ORDER BY last_seen DESC
                ''', (cutoff_time,))
                return [row['username'] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []
    
    def update_user_activity(self, username: str):
        """Update user's last seen timestamp"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE users SET last_seen = CURRENT_TIMESTAMP 
                        WHERE username = ?
                    ''', (username,))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error updating activity for {username}: {e}")
    
    def remove_user(self, username: str) -> bool:
        """Remove user from active users (set last_seen to past)"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    # Set last_seen to 5 minutes ago to effectively "log out" the user
                    past_time = datetime.now() - timedelta(minutes=5)
                    cursor.execute('''
                        UPDATE users SET last_seen = ? 
                        WHERE username = ?
                    ''', (past_time, username))
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Error removing user {username}: {e}")
            return False
    
    def add_message(self, chat_key: str, sender: str, message: str, original_language: str = 'en') -> bool:
        """Add message to database with duplicate prevention"""
        try:
            # Create hash to prevent duplicates
            message_content = f"{chat_key}:{sender}:{message}:{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            message_hash = hashlib.md5(message_content.encode()).hexdigest()
            
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO messages (chat_key, sender, message, original_language, message_hash)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (chat_key, sender, message, original_language, message_hash))
                    conn.commit()
                    return True
        except sqlite3.IntegrityError:
            # Duplicate message, ignore
            return False
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return False
    
    def get_messages(self, chat_key: str, limit: int = MAX_CHAT_HISTORY) -> List[Dict]:
        """Get messages for a chat with limit"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sender, message, original_language, timestamp
                    FROM messages 
                    WHERE chat_key = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (chat_key, limit))
                
                messages = []
                for row in cursor.fetchall():
                    messages.append({
                        'sender': row['sender'],
                        'message': row['message'],
                        'original_language': row['original_language'],
                        'time': datetime.fromisoformat(row['timestamp']).strftime("%H:%M")
                    })
                return list(reversed(messages))  # Return in chronological order
        except Exception as e:
            logger.error(f"Error getting messages for {chat_key}: {e}")
            return []

class TranslationCache:
    """Simple in-memory cache for translations"""
    
    def __init__(self, max_size: int = 1000):
        self.cache = {}
        self.max_size = max_size
        self.access_times = {}
    
    def _make_key(self, text: str, target_lang: str) -> str:
        """Create cache key"""
        return hashlib.md5(f"{text}:{target_lang}".encode()).hexdigest()
    
    def get(self, text: str, target_lang: str) -> Optional[str]:
        """Get cached translation"""
        key = self._make_key(text, target_lang)
        if key in self.cache:
            self.access_times[key] = time.time()
            return self.cache[key]
        return None
    
    def set(self, text: str, target_lang: str, translation: str):
        """Set cached translation"""
        if len(self.cache) >= self.max_size:
            # Remove oldest accessed item
            oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
            del self.cache[oldest_key]
            del self.access_times[oldest_key]
        
        key = self._make_key(text, target_lang)
        self.cache[key] = translation
        self.access_times[key] = time.time()

class AudioManager:
    """Manages TTS audio generation and caching"""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
    
    def _get_audio_filename(self, text: str, lang: str) -> str:
        """Generate filename for audio cache"""
        text_hash = hashlib.md5(f"{text}:{lang}".encode()).hexdigest()
        return os.path.join(self.cache_dir, f"audio_{text_hash}.mp3")
    
    def get_audio_bytes(self, text: str, lang: str) -> Optional[bytes]:
        """Get audio bytes, using cache if available"""
        filename = self._get_audio_filename(text, lang)
        
        # Check if cached file exists and is recent
        if os.path.exists(filename):
            file_age = time.time() - os.path.getmtime(filename)
            if file_age < CACHE_DURATION:
                try:
                    with open(filename, 'rb') as f:
                        return f.read()
                except Exception as e:
                    logger.error(f"Error reading cached audio: {e}")
        
        # Generate new audio
        try:
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(filename)
            with open(filename, 'rb') as f:
                audio_bytes = f.read()
            return audio_bytes
        except Exception as e:
            logger.error(f"Error generating audio: {e}")
            return None
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """Clean up old audio files"""
        try:
            current_time = time.time()
            for filename in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_hours * 3600:
                        os.remove(file_path)
        except Exception as e:
            logger.error(f"Error cleaning up audio files: {e}")

# Initialize managers
@st.cache_resource
def get_managers():
    db_manager = DatabaseManager(DB_FILE)
    translation_cache = TranslationCache()
    audio_manager = AudioManager(AUDIO_CACHE_DIR)
    return db_manager, translation_cache, audio_manager

def chat_key(user1: str, user2: str) -> str:
    """Generate consistent chat key for two users"""
    return "|".join(sorted([user1, user2]))

def sanitize_input(text: str) -> str:
    """Sanitize user input - only allow first name (single word)"""
    # Remove potentially harmful characters and limit length
    text = re.sub(r'[<>"\']', '', text)
    # Extract only the first word (first name only)
    first_word = text.split()[0] if text.split() else ""
    return first_word[:20].strip()  # Limit to 20 characters for first name

def translate_text(text: str, target_lang: str, cache: TranslationCache) -> str:
    """Translate text with caching"""
    if not text.strip():
        return text
    
    # Check cache first
    cached = cache.get(text, target_lang)
    if cached:
        return cached
    
    try:
        translator = GoogleTranslator(source='auto', target=target_lang)
        translation = translator.translate(text)
        cache.set(text, target_lang, translation)
        return translation
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text  # Return original text if translation fails

def main():
    """Main application function"""
    
    # Initialize managers
    db_manager, translation_cache, audio_manager = get_managers()
    
    # Enhanced CSS styling
    st.markdown("""
    <style>
    .header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 25px;
        border-radius: 15px;
        color: white;
        text-align: center;
        font-family: 'Poppins', sans-serif;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        margin-bottom: 30px;
    }
    
    .message-container {
        padding: 12px;
        margin: 8px 0;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        # background: linear-gradient(145deg, #f8f9fa, #e9ecef);
    }
    
    .user-message {
        background: linear-gradient(145deg, #d4edda, #c3e6cb);
        margin-left: 20%;
    }
    
    .other-message {
        background: linear-gradient(145deg, #fff3cd, #ffeaa7);
        margin-right: 20%;
    }
    
    .online-indicator {
        color: #28a745;
        font-weight: bold;
    }
    
    .sidebar-section {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
    }
    
    .leave-button {
        background: linear-gradient(135deg, #ff6b6b, #ee5a52) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-weight: bold !important;
        transition: all 0.3s ease !important;
    }
    
    .leave-button:hover {
        background: linear-gradient(135deg, #ff5252, #f44336) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(255, 107, 107, 0.4) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown('<div class="header"><h1>🌍 Advanced Multilingual Chat</h1><p>Connect with people worldwide in real-time</p></div>', unsafe_allow_html=True)
    
    # User authentication
    if "username" not in st.session_state:
        st.markdown("### Welcome! Please enter your details to start chatting")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            name = st.text_input("📝 First Name Only", max_chars=20, placeholder="Enter your first name...")
            st.caption("*Only your first name is allowed - no spaces or multiple words*")
        
        with col2:
            preferred_lang = st.selectbox("🌐 Preferred Language", list(LANGUAGE_OPTIONS.keys()))
        
        if st.button("🚀 Start Chatting", type="primary") and name.strip():
            username = sanitize_input(name)
            if len(username) >= 2:
                # Check if username is already taken by an active user
                if db_manager.check_user_exists(username):
                    st.error(f"❌ Username '{username}' is already in use by someone currently active. Please choose a different name.")
                elif db_manager.add_user(username, LANGUAGE_OPTIONS[preferred_lang]):
                    st.session_state.username = username
                    st.session_state.preferred_language = preferred_lang
                    st.success(f"✅ Welcome {username}! Joining the chat...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Error creating user. Please try again.")
            else:
                st.error("First name must be at least 2 characters long.")
        st.stop()
    
    username = st.session_state.username
    preferred_lang = st.session_state.get('preferred_language', 'English')
    
    # Update user activity
    db_manager.update_user_activity(username)
    
    # Sidebar
    with st.sidebar:
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown(f"### 👤 Welcome, {username}!")
        
        # Leave button at the top
        if st.button("🚪 Leave Chat", key="leave_button", help="Leave the chat and go offline"):
            if db_manager.remove_user(username):
                # Clear session state
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.success("👋 You have left the chat successfully!")
                st.balloons()
                time.sleep(2)
                st.rerun()
            else:
                st.error("Error leaving chat. Please try again.")
        
        st.markdown("---")
        
        # Settings
        st.markdown("### ⚙️ Settings")
        audio_enabled = st.checkbox("🔊 Enable Audio", value=True)
        user_lang_name = st.selectbox("🌐 Display Language", list(LANGUAGE_OPTIONS.keys()), 
                                    index=list(LANGUAGE_OPTIONS.keys()).index(preferred_lang))
        user_lang_code = LANGUAGE_OPTIONS[user_lang_name]
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox("🔄 Auto-refresh messages", value=True)
        if auto_refresh:
            refresh_interval = st.slider("Refresh interval (seconds)", 5, 60, 10)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Active users
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("### 👥 Currently Active Users")
        
        active_users = db_manager.get_active_users()
        available_users = [u for u in active_users if u != username]
        
        if available_users:
            st.markdown(f"**{len(active_users)} users online now:**")
            for user in available_users[:15]:  # Show max 15 users
                st.markdown(f'<span class="online-indicator">🟢</span> {user}', unsafe_allow_html=True)
        else:
            st.info("🔍 No other users online right now")
            st.markdown("*Users shown here are actively using the app*")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Chat selection
        if available_users:
            chat_with = st.selectbox("💬 Chat with:", available_users)
        else:
            st.info("Waiting for other users...")
            if auto_refresh:
                time.sleep(refresh_interval)
                st.rerun()
            st.stop()
    
    # Main chat interface
    if available_users:
        key = chat_key(username, chat_with)
        
        st.markdown(f"## 💬 Chat with **{chat_with}**")
        
        # Message container
        message_container = st.container()
        
        with message_container:
            messages = db_manager.get_messages(key)
            
            if not messages:
                st.info("👋 Start the conversation! Send your first message below.")
            
            for msg in messages:
                sender = msg["sender"]
                time_str = msg["time"]
                original_text = msg["message"]
                
                # Translate message
                displayed_text = translate_text(original_text, user_lang_code, translation_cache)
                
                # Style messages differently for current user vs others
                is_user_message = sender == username
                container_class = "user-message" if is_user_message else "other-message"
                
                st.markdown(f'''
                <div class="message-container {container_class}">
                    <strong>{sender}</strong> <small style="color: #666;">[{time_str}]</small><br>
                    {displayed_text}
                </div>
                ''', unsafe_allow_html=True)
                
                # Audio playback
                if audio_enabled and displayed_text != original_text:
                    audio_bytes = audio_manager.get_audio_bytes(displayed_text, user_lang_code)
                    if audio_bytes:
                        st.audio(audio_bytes, format="audio/mp3")
        
        # Message input
        st.markdown("---")
        with st.form("chat_form", clear_on_submit=True):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                new_msg = st.text_area("✍️ Your message:", height=100, 
                                     placeholder="Type your message here...", 
                                     max_chars=MAX_MESSAGE_LENGTH)
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                send = st.form_submit_button("📤 Send", type="primary", use_container_width=True)
                
                # Message stats
                if new_msg:
                    st.caption(f"Characters: {len(new_msg)}/{MAX_MESSAGE_LENGTH}")
        
        if send and new_msg.strip():
            sanitized_msg = sanitize_input(new_msg)
            if sanitized_msg:
                if db_manager.add_message(key, username, sanitized_msg, user_lang_code):
                    st.success("Message sent!")
                    if auto_refresh:
                        time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Message not sent (possible duplicate)")
        
        # Auto-refresh
        if auto_refresh:
            time.sleep(refresh_interval)
            st.rerun()
    
    # Cleanup old audio files periodically
    if st.session_state.get('last_cleanup', 0) < time.time() - 3600:  # Every hour
        audio_manager.cleanup_old_files()
        st.session_state.last_cleanup = time.time()

if __name__ == "__main__":
    # Configure Streamlit page
    st.set_page_config(
        page_title="Advanced Multilingual Chat",
        page_icon="🌍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    main()
