import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import json
import os

# Firebase Setup
if not firebase_admin._apps:
    cred = credentials.Certificate("your_firebase_adminsdk.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://your-project-id.firebaseio.com/'
    })

st.title("🔔 Real-Time Chat with Notifications")

username = st.text_input("Enter your name")
if not username:
    st.stop()

chat_ref = db.reference("chats")

# Poll for new messages every few seconds
messages = chat_ref.get() or {}

last_seen = st.session_state.get("last_seen", "")

# New message check
new_message = None
for key, msg in messages.items():
    if msg['sender'] != username and msg['time'] != last_seen:
        new_message = msg
        st.session_state["last_seen"] = msg["time"]
        break

if new_message:
    st.success(f"New message from {new_message['sender']}: {new_message['message']}")
    
    # JavaScript Notification (pop-up)
    js_code = f"""
    <script>
    if (Notification.permission !== "granted")
        Notification.requestPermission();
    else {{
        var notification = new Notification("📬 New message from {new_message['sender']}", {{
            body: "{new_message['message']}",
        }});
    }}
    </script>
    """
    st.components.v1.html(js_code)

# Input form
with st.form("send"):
    text = st.text_input("Type a message")
    send = st.form_submit_button("Send")
    if send and text.strip():
        chat_ref.push({
            "sender": username,
            "message": text.strip(),
            "time": datetime.now().strftime("%H:%M:%S")
        })
        st.experimental_rerun()
