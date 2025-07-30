import streamlit as st
from datetime import datetime
from deep_translator import GoogleTranslator
from gtts import gTTS
import uuid
import os
import json

# ----------- Constants -----------
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

CHAT_FILE = "chat_data.json"

# ----------- Load / Save Chat Data -----------
def load_chat():
    if not os.path.exists(CHAT_FILE):
        with open(CHAT_FILE, "w") as f:
            json.dump({}, f)
    with open(CHAT_FILE, "r") as f:
        return json.load(f)

def save_chat(chat_data):
    with open(CHAT_FILE, "w") as f:
        json.dump(chat_data, f)

# ----------- Translate and TTS -----------
def translate_text(text, target_lang):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except Exception:
        return text

def generate_tts(text, lang_code):
    try:
        tts = gTTS(text=text, lang=lang_code)
        filename = f"tts_{uuid.uuid4()}.mp3"
        tts.save(filename)
        audio = open(filename, "rb").read()
        os.remove(filename)
        return audio
    except Exception:
        return None

# ----------- UI Header -----------
st.markdown("""
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
""", unsafe_allow_html=True)
st.markdown('<div class="header"><h2>💬 Multilingual Private Chat</h2></div>', unsafe_allow_html=True)

# ----------- Username Setup -----------
if 'username' not in st.session_state:
    username = st.text_input("Enter your name to join", max_chars=20)
    if st.button("Join") and username.strip():
        st.session_state.username = username.strip()
        st.rerun()
    st.stop()

username = st.session_state.username
st.sidebar.markdown(f"👤 Logged in as: `{username}`")

# ----------- Language Selection -----------
user_lang_name = st.sidebar.selectbox("Your preferred language", list(language_options.keys()))
user_lang_code = language_options[user_lang_name]

# ----------- Load Chat Data -----------
chat_data = load_chat()

# ----------- Get all users -----------
all_users = set()
for pair in chat_data:
    all_users.update(pair.split('|'))
all_users.discard(username)

chat_partner = st.sidebar.selectbox("💬 Chat with", sorted(all_users) if all_users else ["(Waiting for others...)"])

if chat_partner == "(Waiting for others...)":
    st.info("No one else is online yet.")
    st.stop()

# ----------- Chat Key -----------
def chat_key(user1, user2):
    return "|".join(sorted([user1, user2]))

key = chat_key(username, chat_partner)
if key not in chat_data:
    chat_data[key] = []

# ----------- Chat Display -----------
st.markdown(f"### Chat between `{username}` and `{chat_partner}`")

for msg in chat_data[key][-50:]:
    sender = msg["sender"]
    time = msg["time"]
    content = msg["message"]

    if sender != username:
        content = translate_text(content, user_lang_code)

    align = "right" if sender == username else "left"
    st.markdown(f"<p style='text-align:{align};'><b>{sender} [{time}]</b>: {content}</p>", unsafe_allow_html=True)

    audio = generate_tts(content, user_lang_code)
    if audio:
        st.audio(audio, format="audio/mp3")

# ----------- Chat Input -----------
with st.form("chat_form", clear_on_submit=True):
    message = st.text_area("Type your message...", height=100)
    send = st.form_submit_button("Send")
    if send and message.strip():
        chat_data[key].append({
            "sender": username,
            "message": message.strip(),
            "time": datetime.now().strftime("%H:%M")
        })
        save_chat(chat_data)
        st.experimental_rerun()

# ----------- Logout Option -----------
if st.sidebar.button("Leave Chat"):
    del st.session_state.username
    st.experimental_rerun()
