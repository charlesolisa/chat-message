import streamlit as st
from datetime import datetime
from deep_translator import GoogleTranslator
from gtts import gTTS
import uuid
import os

# Initialize session state storage
if 'messages' not in st.session_state:
    # messages stored as:
    # { (user1, user2): [ {sender, message, time}, ... ] }
    st.session_state.messages = {}

if 'username' not in st.session_state:
    st.session_state.username = None

# Language options for translation and TTS
language_options = {
    'English': 'en',
    'French': 'fr',
    'Spanish': 'es',
    'German': 'de',
    'Arabic': 'ar',
    'Chinese (Simplified)': 'zh-CN',
    'Hindi': 'hi',
    'Russian': 'ru',
}

# ----- HEADER -----
st.markdown(
    """
    <style>
    .header {
        background-color: #4CAF50;
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        font-family: 'Poppins', sans-serif;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown('<div class="header"><h1>💬 Multilingual Private Chat App</h1></div>', unsafe_allow_html=True)

# User login section
if not st.session_state.username:
    username = st.text_input("Enter your name to start chatting", max_chars=20)
    if st.button("Set username") and username:
        st.session_state.username = username.strip()
        st.rerun()  # Rerun app after login to show chat UI
    st.stop()  # stop further execution until username is set

# Sidebar info & controls
st.sidebar.markdown(f"**Logged in as:** {st.session_state.username}")

# User picks their interface language (used for translation and TTS)
user_lang_name = st.sidebar.selectbox("Choose your interface language", list(language_options.keys()), index=0)
user_lang_code = language_options[user_lang_name]

# Gather all users seen so far from messages
all_users = set()
for chat_pair in st.session_state.messages.keys():
    all_users.update(chat_pair)
all_users.add(st.session_state.username)

# Build list of possible chat partners excluding self
user_list = sorted(u for u in all_users if u != st.session_state.username)
if not user_list:
    user_list = ["No other users yet"]

chat_with = st.sidebar.selectbox("Chat with", user_list)

if chat_with == "No other users yet":
    st.info("Waiting for other users to join...")
    st.stop()

# Key for message storage is sorted tuple of the two usernames
chat_key = tuple(sorted([st.session_state.username, chat_with]))
if chat_key not in st.session_state.messages:
    st.session_state.messages[chat_key] = []

# Message input form
with st.form("chat_form", clear_on_submit=True):
    message = st.text_area("Type your message...", height=100)
    submitted = st.form_submit_button("Send")

    if submitted and message.strip():
        timestamp = datetime.now().strftime("%H:%M")
        st.session_state.messages[chat_key].append({
            "sender": st.session_state.username,
            "message": message.strip(),
            "time": timestamp
        })

# Function to translate text (with fallback)
def translate_text(text, target_lang):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except Exception:
        return text

# Display chat messages
st.markdown(f"### Chat between **{st.session_state.username}** and **{chat_with}**:")

for msg in st.session_state.messages[chat_key]:
    sender = msg["sender"]
    time = msg["time"]
    original_text = msg["message"]

    # Translate incoming messages to current user's chosen language
    if sender != st.session_state.username:
        display_text = translate_text(original_text, user_lang_code)
    else:
        display_text = original_text

    # Message alignment and styling
    if sender == st.session_state.username:
        st.markdown(f"<p style='text-align: right;'><b>You [{time}]</b>: {display_text}</p>", unsafe_allow_html=True)
    else:
        st.markdown(f"<p style='text-align: left;'><b>{sender} [{time}]</b>: {display_text}</p>", unsafe_allow_html=True)

    # Generate and play TTS audio for the displayed text
    tts_filename = f"tts_{uuid.uuid4()}.mp3"
    try:
        tts = gTTS(text=display_text, lang=user_lang_code)
        tts.save(tts_filename)
        audio_bytes = open(tts_filename, "rb").read()
        st.audio(audio_bytes, format="audio/mp3")
    except Exception as e:
        st.write(f"⚠️ Could not generate audio: {e}")
    finally:
        if os.path.exists(tts_filename):
            os.remove(tts_filename)
