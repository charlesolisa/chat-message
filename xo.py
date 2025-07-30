import streamlit as st
from datetime import datetime
from deep_translator import GoogleTranslator
from gtts import gTTS
import uuid
import os

# -------------------- Language Options --------------------
language_options = {
    'English': 'en',
    'French': 'fr',
    'Spanish': 'es',
    'German': 'de',
    'Arabic': 'ar',
    'Chinese': 'zh-CN'
}

# -------------------- Session State --------------------
if 'username' not in st.session_state:
    st.session_state.username = None

if 'messages' not in st.session_state:
    st.session_state.messages = {}  # (user1, user2): [ {sender, message, time}, ... ]

if 'lang_pref' not in st.session_state:
    st.session_state.lang_pref = 'en'

# -------------------- Header --------------------
st.markdown("""
    <style>
    .header {
        background-color: #4CAF50;
        padding: 15px;
        border-radius: 10px;
        color: white;
        text-align: center;
        font-family: 'Poppins', sans-serif;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="header"><h2>💬 Multilingual Chat App</h2></div>', unsafe_allow_html=True)

# -------------------- Ask for Username --------------------
if not st.session_state.username:
    name = st.text_input("Enter your name to join the chat")
    if st.button("Join"):
        if not name.strip().isalpha():
            st.error("Name must contain only letters.")
        else:
            st.session_state.username = name.strip()
            st.experimental_rerun()
    st.stop()

# -------------------- Sidebar --------------------
st.sidebar.markdown(f"👤 You are: `{st.session_state.username}`")
st.sidebar.markdown("### 🌐 Language Preference")
lang_name = st.sidebar.selectbox("Choose your language", list(language_options.keys()))
st.session_state.lang_pref = language_options[lang_name]

# Get list of all known users from chat messages
all_users = set()
for pair in st.session_state.messages:
    all_users.update(pair)
all_users.add(st.session_state.username)
other_users = sorted(u for u in all_users if u != st.session_state.username)

chat_partner = st.sidebar.selectbox("💬 Chat with", other_users if other_users else ["No one yet"])

if chat_partner == "No one yet":
    st.info("No one else has joined yet.")
    st.stop()

# -------------------- Chat Functions --------------------
def get_chat_key(u1, u2):
    return tuple(sorted([u1, u2]))

def translate_text(text, target_lang):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except:
        return text

def generate_tts(text, lang_code):
    try:
        tts = gTTS(text=text, lang=lang_code)
        fname =
