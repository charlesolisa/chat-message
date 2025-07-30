import streamlit as st
from datetime import datetime
from deep_translator import GoogleTranslator
from gtts import gTTS
import uuid
import os
import json

# ----------- Constants -----------
CHAT_FILE = "chat_data.json"
USER_FILE = "users.json"

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

# ----------- Load & Save Helpers -----------
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f)
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

# ----------- UI STYLES (Text: black, visible) -----------
st.markdown("""
<style>
body, p, div, span, label, h1, h2, h3, h4, h5, h6 {
    color: #000 !important;
    font-family: 'Poppins', sans-serif;
}
[data-testid="stMarkdownContainer"] {
    background-color: white !important;
}
.header {
    background-color: #e0e0e0;
    padding: 20px;
    border-radius: 10px;
    color: black !important;
    text-align: center;
    font-family: 'Poppins', sans-serif;
    box-shadow: 0 4px 10px rgba(0,0,0,0.05);
}
.stSidebar {
    background-color: #f7f7f7 !important;
    color: black !important;
}
input, textarea {
    color: black !important;
    background-color: #fff !important;
}
</style>
""", unsafe_allow_html=True)

# ----------- Header -----------
st.markdown('<div class="header"><h2>💬 Multilingual Private Chat</h2></div>', unsafe_allow_html=True)

# ----------- Chat Data & User List -----------
chat_data = load_json(CHAT_FILE, {})
user_list = load_json(USER_FILE, [])

# ----------- User Join Flow -----------
if 'username' not in st.session_state:
    username_input = st.text_input("Enter your name to join:", max_chars=20)
    if st.button("Join") and username_input.strip():
        username = username_input.strip()
        st.session_state.username = username
        if username not in user_list:
            user_list.append(username)
            save_json(USER_FILE, user_list)
    else:
        st.stop()

username = st.session_state.username
st.sidebar.markdown(f"👤 Logged in as: `{username}`")

# ----------- Language & Chat Partner -----------
user_lang_name = st.sidebar.selectbox("Your language", list(language_options.keys()))
user_lang_code = language_options[user_lang_name]

available_users = [u for u in user_list if u != username]
if not available_users:
    st.info("No one else has joined yet.")
    st.stop()

chat_with = st.sidebar.selectbox("Chat with:", available_users)

# ----------- Chat Key Generator -----------
def chat_key(user1, user2):
    return "|".join(sorted([user1, user2]))

key = chat_key(username, chat_with)
if key not in chat_data:
    chat_data[key] = []

# ----------- Display Chat Messages -----------
st.markdown(f"### Chat with `{chat_with}`:")

for msg in chat_data[key][-50:]:
    sender = msg["sender"]
    time = msg["time"]
    content = msg["message"]

    # Translate if incoming
    if sender != username:
        try:
            content = GoogleTranslator(source='auto', target=user_lang_code).translate(content)
        except:
            pass

    align = "right" if sender == username else "left"
    st.markdown(f"<p style='text-align:{align};'><b>{sender} [{time}]</b>: {content}</p>", unsafe_allow_html=True)

    try:
        tts = gTTS(text=content, lang=user_lang_code)
        filename = f"tts_{uuid.uuid4()}.mp3"
        tts.save(filename)
        st.audio(open(filename, "rb").read(), format="audio/mp3")
        os.remove(filename)
    except:
        pass

# ----------- Message Form -----------
with st.form("message_form", clear_on_submit=True):
    new_msg = st.text_area("Type your message...", height=100)
    send_btn = st.form_submit_button("Send")
    if send_btn and new_msg.strip():
        chat_data[key].append({
            "sender": username,
            "message": new_msg.strip(),
            "time": datetime.now().strftime("%H:%M")
        })
        save_json(CHAT_FILE, chat_data)

# ----------- Leave Button -----------
if st.sidebar.button("🚪 Leave Chat"):
    del st.session_state.username
