import streamlit as st
import os
import json
import hashlib
import uuid
from datetime import datetime
from deep_translator import GoogleTranslator
from gtts import gTTS

# -------------------- File setup --------------------
USER_FILE = "users.json"
if not os.path.exists(USER_FILE):
    with open(USER_FILE, "w") as f:
        json.dump({}, f)

# -------------------- Helpers --------------------
def load_users():
    with open(USER_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# -------------------- App State --------------------
if "users" not in st.session_state:
    st.session_state.users = load_users()

if "username" not in st.session_state:
    st.session_state.username = None

if "messages" not in st.session_state:
    st.session_state.messages = {}  # {("user1", "user2"): [msg_dict]}

if "lang_pref" not in st.session_state:
    st.session_state.lang_pref = "en"

# -------------------- Language Options --------------------
language_options = {
    'English': 'en',
    'French': 'fr',
    'Spanish': 'es',
    'German': 'de',
    'Arabic': 'ar',
    'Chinese': 'zh-CN'
}

# -------------------- Auth --------------------
def login():
    st.header("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        users = st.session_state.users
        if username in users and users[username]["password"] == hash_password(password):
            st.session_state.username = username
            st.success(f"Welcome back, {username}!")
            st.experimental_rerun()
        else:
            st.error("Invalid credentials")

def register():
    st.header("📝 Register")
    username = st.text_input("Choose username")
    password = st.text_input("Choose password", type="password")
    if st.button("Register"):
        users = st.session_state.users
        if username in users:
            st.error("Username already exists")
        else:
            users[username] = {"password": hash_password(password)}
            save_users(users)
            st.session_state.users = users
            st.success("Registered successfully! Now login.")

# -------------------- Chat Logic --------------------
def get_chat_key(user1, user2):
    return tuple(sorted([user1, user2]))

def translate_text(text, target_lang):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except:
        return text

def tts_audio(text, lang_code):
    try:
        tts = gTTS(text=text, lang=lang_code)
        file = f"{uuid.uuid4()}.mp3"
        tts.save(file)
        audio = open(file, "rb").read()
        os.remove(file)
        return audio
    except Exception as e:
        st.error(f"TTS failed: {e}")
        return None

# -------------------- Main Chat App --------------------
def chat_app():
    st.sidebar.title("Chat Settings")
    st.sidebar.markdown(f"👤 **Logged in as:** `{st.session_state.username}`")

    lang_name = st.sidebar.selectbox("Your preferred language", list(language_options.keys()))
    st.session_state.lang_pref = language_options[lang_name]

    users = list(st.session_state.users.keys())
    other_users = [u for u in users if u != st.session_state.username]

    if not other_users:
        st.warning("No other users available.")
        return

    chat_partner = st.sidebar.selectbox("Chat with", other_users)
    chat_key = get_chat_key(st.session_state.username, chat_partner)

    if chat_key not in st.session_state.messages:
        st.session_state.messages[chat_key] = []

    st.title(f"💬 Chat with {chat_partner}")

    # Chat history
    for msg in st.session_state.messages[chat_key]:
        sender = msg["sender"]
        time = msg["time"]
        content = msg["message"]
        lang = st.session_state.lang_pref
        if sender != st.session_state.username:
            content = translate_text(content, lang)

        st.markdown(f"**{sender} [{time}]:** {content}")
        audio = tts_audio(content, lang)
        if audio:
            st.audio(audio, format="audio/mp3")

    # Message box
    with st.form("chat_form", clear_on_submit=True):
        new_msg = st.text_input("Type your message...")
        send = st.form_submit_button("Send")
        if send and new_msg:
            st.session_state.messages[chat_key].append({
                "sender": st.session_state.username,
                "message": new_msg.strip(),
                "time": datetime.now().strftime("%H:%M")
            })

    # Logout
    if st.sidebar.button("Logout"):
        for key in ["username", "lang_pref"]:
            st.session_state.pop(key, None)
        st.experimental_rerun()

# -------------------- Run App --------------------
if not st.session_state.username:
    mode = st.radio("Select Action", ["Login", "Register"])
    login() if mode == "Login" else register()
else:
    chat_app()
