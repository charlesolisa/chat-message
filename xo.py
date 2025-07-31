import streamlit as st
from datetime import datetime
from deep_translator import GoogleTranslator
from gtts import gTTS
import uuid
import os
import json

CHAT_FILE = "chat_data.json"
GUESTS_FILE = "guests.json"

language_options = {
    'English': 'en',
    'French': 'fr',
    'Spanish': 'es',
    'German': 'de',
    'Arabic': 'ar',
    'Chinese (Simplified)': 'zh-CN',
    'Hindi': 'hi',
    'Russian': 'ru',
    'Japanese': 'ja',
    'Portuguese': 'pt',
}

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f)
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

def chat_key(user1, user2):
    return "|".join(sorted([user1, user2]))

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
    margin-bottom: 20px;
}
.sidebar-badge {
    color: white;
    background-color: red;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 12px;
    margin-left: 5px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header"><h1>💬 Multilingual Public Chat App</h1></div>', unsafe_allow_html=True)

# ----------- USERNAME ENTRY ----------
if "username" not in st.session_state:
    name = st.text_input("Enter your display name to start chatting", max_chars=20)
    if st.button("Start Chatting") and name.strip():
        username = name.strip()
        guests = load_json(GUESTS_FILE, [])
        if username not in guests:
            guests.append(username)
            save_json(GUESTS_FILE, guests)
        st.session_state.username = username
        st.rerun()
    else:
        st.stop()

username = st.session_state.username
chat_data = load_json(CHAT_FILE, {})
guests = load_json(GUESTS_FILE, [])

# ---------- SIDEBAR ----------
st.sidebar.markdown(f"👤 You are: **{username}**")
audio_enabled = st.sidebar.checkbox("Enable Audio Playback", value=True)
user_lang_name = st.sidebar.selectbox("Choose your display language", list(language_options.keys()), index=0)
user_lang_code = language_options[user_lang_name]

available_users = [u for u in guests if u != username]
if not available_users:
    st.sidebar.info("Waiting for other users to join...")

# ----------- NOTIFICATION SYSTEM ----------
if "last_seen_times" not in st.session_state:
    st.session_state.last_seen_times = {}

chat_badges = {}
for other_user in available_users:
    key = chat_key(username, other_user)
    chat_history = chat_data.get(key, [])
    last_seen = st.session_state.last_seen_times.get(key, "")
    if chat_history:
        latest_msg = chat_history[-1]
        if latest_msg["sender"] != username and latest_msg["time"] != last_seen:
            chat_badges[other_user] = True  # new unseen message

# Show badge if unread messages exist
def display_user(user):
    return f"{user} 🔴" if chat_badges.get(user) else user

chat_with = st.sidebar.selectbox("Chat with:", [display_user(u) for u in available_users] if available_users else ["No users online"])

if chat_with == "No users online":
    st.info("No one else is online right now. Please wait for others to join.")
    st.stop()

# Remove badge suffix to get actual username
chat_with = chat_with.replace(" 🔴", "")
key = chat_key(username, chat_with)

if key not in chat_data:
    chat_data[key] = []

st.markdown(f"## Chatting with **{chat_with}**")

# ---------- CHAT DISPLAY ----------
latest_msg_time = ""
for msg in chat_data[key][-50:]:
    sender = msg["sender"]
    time = msg["time"]
    original_text = msg["message"]
    try:
        displayed_text = GoogleTranslator(source='auto', target=user_lang_code).translate(original_text)
    except Exception:
        displayed_text = original_text

    align = "right" if sender == username else "left"
    st.markdown(f"<p style='text-align: {align}; color: black;'><b>{sender} [{time}]</b>: {displayed_text}</p>", unsafe_allow_html=True)

    if audio_enabled:
        try:
            tts = gTTS(text=displayed_text, lang=user_lang_code)
            tts_filename = f"tts_{uuid.uuid4()}.mp3"
            tts.save(tts_filename)
            audio_bytes = open(tts_filename, "rb").read()
            st.audio(audio_bytes, format="audio/mp3")
        except Exception as e:
            st.write(f"⚠️ Audio error: {e}")
        finally:
            if os.path.exists(tts_filename):
                os.remove(tts_filename)
    
    latest_msg_time = time

# ----------- UPDATE LAST SEEN TIME ----------
st.session_state.last_seen_times[key] = latest_msg_time

# ---------- MESSAGE INPUT ----------
with st.form("chat_form", clear_on_submit=True):
    new_msg = st.text_area("Your message:", height=100)
    send = st.form_submit_button("Send")

    if send and new_msg.strip():
        chat_data[key].append({
            "sender": username,
            "message": new_msg.strip(),
            "time": datetime.now().strftime("%H:%M")
        })
        save_json(CHAT_FILE, chat_data)
        st.rerun()
