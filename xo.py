import streamlit as st
from datetime import datetime
from deep_translator import GoogleTranslator
from gtts import gTTS
import uuid
import os
import json
import re

# ------------------ File Paths ------------------
USERS_FILE = "users.json"
CHAT_FILE = "chat_data.json"
GROUPS_FILE = "groups.json"
UNREAD_FILE = "unread.json"

# ------------------ Language Options ------------------
language_options = {
    'English': 'en', 'French': 'fr', 'Spanish': 'es', 'German': 'de',
    'Arabic': 'ar', 'Chinese (Simplified)': 'zh-CN', 'Hindi': 'hi',
    'Russian': 'ru', 'Portuguese': 'pt', 'Japanese': 'ja'
}

# ------------------ JSON Helpers ------------------
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f)
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ------------------ Load Data ------------------
users = load_json(USERS_FILE, [])
chat_data = load_json(CHAT_FILE, {})
groups = load_json(GROUPS_FILE, {})
unread_data = load_json(UNREAD_FILE, {})

# ------------------ UI Styles ------------------
st.markdown("""
<style>
.header {
    background-color: #4caf50;
    padding: 20px;
    border-radius: 10px;
    color: white;
    text-align: center;
    font-size: 24px;
    font-weight: bold;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="header">🌐 Multilingual Chat App</div>', unsafe_allow_html=True)

# ------------------ Name Validation ------------------
def is_valid_name(name):
    return bool(re.match(r'^[A-Za-z]+$', name.strip()))

# ------------------ Login ------------------
if "user_info" not in st.session_state:
    st.subheader("🔐 Join the Chat")
    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")
    country = st.text_input("Country")

    if st.button("Join"):
        if not all([first_name, last_name, country]):
            st.warning("Please fill in all fields.")
            st.stop()
        if not is_valid_name(first_name) or not is_valid_name(last_name):
            st.error("Names must only contain letters.")
            st.stop()
        full_name = f"{first_name.strip()} {last_name.strip()} ({country.strip()})"
        if full_name in users:
            st.error("This name is already taken.")
            st.stop()

        users.append(full_name)
        save_json(USERS_FILE, users)
        st.session_state.user_info = {
            "username": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "country": country
        }
        st.rerun()
    st.stop()

username = st.session_state.user_info["username"]

# ------------------ Chat Mode Select ------------------
if "chat_mode" not in st.session_state:
    st.subheader("💬 Select Chat Mode")
    chat_mode = st.radio("Choose chat type:", ["Public Chat", "Private Chat"])
    if st.button("Continue"):
        st.session_state.chat_mode = chat_mode
        st.rerun()
    st.stop()

# ------------------ Sidebar ------------------
st.sidebar.title("📋 Sidebar")
st.sidebar.markdown(f"👤 You: **{username}**")
st.sidebar.markdown(f"🌍 Country: **{st.session_state.user_info['country']}**")

# Switch Chat Mode
st.sidebar.markdown("---")
st.sidebar.subheader("💡 Chat Mode")
if st.sidebar.button("🔄 Switch Chat Mode"):
    current = st.session_state.chat_mode
    st.session_state.chat_mode = "Private Chat" if current == "Public Chat" else "Public Chat"
    st.rerun()

# Language and Audio
audio_enabled = st.sidebar.checkbox("Enable Audio", value=True)
lang_name = st.sidebar.selectbox("Interface Language", list(language_options.keys()))
lang_code = language_options[lang_name]

# Group Creation
if st.session_state.chat_mode == "Public Chat":
    st.sidebar.markdown("---")
    st.sidebar.subheader("➕ Create Group")
    group_name = st.sidebar.text_input("Group Name")
    group_members = st.sidebar.multiselect("Select Members", users, default=[username])
    if st.sidebar.button("Create Group"):
        if group_name and group_members:
            groups[group_name] = group_members
            chat_data[f"group|{group_name}"] = []
            save_json(GROUPS_FILE, groups)
            save_json(CHAT_FILE, chat_data)
            st.sidebar.success(f"Group '{group_name}' created.")

# Delete Contact or Group
st.sidebar.markdown("---")
if st.session_state.chat_mode == "Private Chat":
    st.sidebar.subheader("❌ Delete Contact")
    contacts = [u for u in users if u != username]
    contact_to_remove = st.sidebar.selectbox("Select contact to remove", contacts)
    if st.sidebar.button("Remove Contact"):
        confirm = st.sidebar.checkbox("Confirm removal")
        if confirm:
            chat_key = "|".join(sorted([username, contact_to_remove]))
            chat_data.pop(chat_key, None)
            unread_data.pop(chat_key, None)
            if contact_to_remove in users:
                users.remove(contact_to_remove)
            save_json(USERS_FILE, users)
            save_json(CHAT_FILE, chat_data)
            save_json(UNREAD_FILE, unread_data)
            st.sidebar.success(f"Contact '{contact_to_remove}' removed.")
            st.rerun()
else:
    st.sidebar.subheader("🗑️ Delete Group Chat")
    group_chats = [f"group|{g}" for g in groups if username in groups[g]]
    chat_to_delete = st.sidebar.selectbox("Select group to delete", group_chats)
    if st.sidebar.button("Delete Group"):
        confirm = st.sidebar.checkbox("Confirm deletion")
        if confirm:
            group_name = chat_to_delete.split("|")[1]
            groups.pop(group_name, None)
            chat_data.pop(chat_to_delete, None)
            unread_data.pop(chat_to_delete, None)
            save_json(GROUPS_FILE, groups)
            save_json(CHAT_FILE, chat_data)
            save_json(UNREAD_FILE, unread_data)
            st.sidebar.success(f"Group '{group_name}' deleted.")
            st.rerun()

# ------------------ Chat List ------------------
st.sidebar.markdown("---")
st.sidebar.subheader("💬 Chats")
if st.session_state.chat_mode == "Private Chat":
    all_chats = [f"user|{u}" for u in users if u != username]
else:
    all_chats = [f"group|{g}" for g in groups if username in groups[g]]

selected_chat = None
for chat_id in all_chats:
    label = f"👤 {chat_id.split('|')[1]}" if chat_id.startswith("user|") else f"👥 {chat_id.split('|')[1]}"
    unread = unread_data.get(chat_id, {}).get(username, 0)
    label += f" 🔔" if unread else ""
    if st.sidebar.button(label):
        selected_chat = chat_id

if not selected_chat:
    st.warning("Please select a chat.")
    st.stop()

# ------------------ Chat Setup ------------------
chat_key = ""
chat_members = []
if selected_chat.startswith("group|"):
    group_name = selected_chat.split("|")[1]
    chat_key = f"group|{group_name}"
    chat_members = groups.get(group_name, [])
    chat_title = f"Group Chat: {group_name}"
else:
    partner = selected_chat.split("|")[1]
    chat_key = "|".join(sorted([username, partner]))
    chat_members = [username, partner]
    chat_title = f"Private Chat with {partner}"

if chat_key not in chat_data:
    chat_data[chat_key] = []

# ------------------ Leave Chat Button ------------------
st.markdown("---")
if selected_chat.startswith("group|"):
    if st.button("🚪 Leave Group"):
        group_name = selected_chat.split("|")[1]
        if group_name in groups:
            groups[group_name] = [u for u in groups[group_name] if u != username]
            save_json(GROUPS_FILE, groups)
            if not groups[group_name]:
                groups.pop(group_name, None)
                chat_data.pop(f"group|{group_name}", None)
            save_json(CHAT_FILE, chat_data)
            st.success("You left the group.")
            st.rerun()
else:
    if st.button("🚪 End Private Chat"):
        partner = selected_chat.split("|")[1]
        chat_key = "|".join(sorted([username, partner]))
        chat_data.pop(chat_key, None)
        unread_data.pop(chat_key, None)
        save_json(CHAT_FILE, chat_data)
        save_json()
