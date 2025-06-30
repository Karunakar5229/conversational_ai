import streamlit as st
import pyrebase
import requests
import uuid
from datetime import datetime
import sys
import os
from dotenv import load_dotenv

# ------------------ System & Env Setup ------------------
load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from firebase_config import firebase_config
from backend.agent import run_agent

# ------------------ 🔐 Backend API URL ------------------
API_URL = os.getenv("API_URL", "http://localhost:8000/chat")

# ------------------ Firebase Setup ------------------
firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()
db = firebase.database()

# ------------------ Streamlit Config ------------------
st.set_page_config(
    page_title="🧠 Conversational AI Agent",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🧠 Conversational AI Agent")

# ------------------ Project Info (Before Login) ------------------
if "user" not in st.session_state:
    with st.expander("About This Agent", expanded=True):
        st.markdown("""
*Conversational AI Agent* helps users schedule and manage meetings just by chatting.

- ➤ Users can interact simply by chatting — no need for forms or manual inputs.
- ➤ Works for both *guests* and *signed-in* users.
- ➤ Examples of what you can say:
    - "Book a meeting tomorrow at 3 PM"
    - "Check my availability this Friday"
- ⚠ Guest users' chats will not be saved for future access.
        """)

# ------------------ Session State ------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "chat_id" not in st.session_state:
    st.session_state.chat_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_titles" not in st.session_state:
    st.session_state.chat_titles = {}

# ------------------ Firebase Auth ------------------
def login_ui():
    with st.sidebar:
        st.header("Login or Signup")
        choice = st.radio("Mode", ["Login", "Signup"])
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button(choice):
            try:
                if choice == "Login":
                    user = auth.sign_in_with_email_and_password(email, password)
                    st.toast("✅ Logged in successfully", icon="🔓")
                else:
                    user = auth.create_user_with_email_and_password(email, password)
                    st.toast("🎉 Account created successfully", icon="✅")
                st.session_state.user = user
                st.rerun()
            except requests.exceptions.HTTPError as e:
                response = getattr(e, "response", None)
                if response is not None:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                        if error_msg in ["EMAIL_NOT_FOUND", "INVALID_PASSWORD"]:
                            st.toast("❌ Invalid email or password", icon="⚠")
                        elif error_msg == "EMAIL_EXISTS":
                            st.toast("❌ Email already exists", icon="⚠")
                        else:
                            st.toast(f"❌ Error: {error_msg}", icon="⚠")
                    except Exception:
                        st.toast("❌ Failed to parse error response", icon="⚠")
                else:
                    st.toast("❌ Network or authentication error. Please try again.", icon="⚠")

        if st.button("Continue as Guest"):
            st.session_state.user = {"email": "guest", "localId": "guest"}
            st.toast("🟢 Guest mode activated", icon="👤")
            st.rerun()

if not st.session_state.user:
    login_ui()
    st.stop()

# ------------------ Chat History Management ------------------
def load_user_chats():
    if st.session_state.user["localId"] == "guest":
        return
    try:
        chats = db.child("chats").child(st.session_state.user["localId"]).get()
        if chats.each():
            for chat in chats.each():
                st.session_state.chat_titles[chat.key()] = chat.val().get("title", "Untitled")
    except Exception as e:
        st.warning(f"⚠ Could not load chats: {e}")

def save_current_chat():
    if st.session_state.user["localId"] == "guest":
        return
    try:
        db.child("chats").child(st.session_state.user["localId"]).child(st.session_state.chat_id).set({
            "title": st.session_state.chat_history[0]["content"][:30] if st.session_state.chat_history else "New Chat",
            "messages": st.session_state.chat_history,
            "updated": str(datetime.now())
        })
    except Exception as e:
        st.warning(f"⚠ Could not save chat: {e}")

def switch_chat(chat_id):
    st.session_state.chat_id = chat_id
    data = db.child("chats").child(st.session_state.user["localId"]).child(chat_id).get()
    st.session_state.chat_history = data.val().get("messages", []) if data.val() else []

def delete_chat(chat_id):
    try:
        db.child("chats").child(st.session_state.user["localId"]).child(chat_id).remove()
        st.session_state.chat_titles.pop(chat_id, None)
        if st.session_state.chat_id == chat_id:
            st.session_state.chat_id = str(uuid.uuid4())
            st.session_state.chat_history = []
        st.rerun()
    except Exception as e:
        st.warning(f"❌ Failed to delete chat: {e}")

# ------------------ Sidebar: Chat Titles ------------------
with st.sidebar:
    st.subheader("Chats")
    load_user_chats()
    for cid, title in st.session_state.chat_titles.items():
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(title, key=f"chat-{cid}"):
                switch_chat(cid)
        with col2:
            if st.button("🗑", key=f"del-{cid}"):
                delete_chat(cid)

    if st.button("➕ New Chat"):
        st.session_state.chat_id = str(uuid.uuid4())
        st.session_state.chat_history = []

    if st.button("🚪 Logout"):
        for key in ["user", "chat_id", "chat_history", "chat_titles"]:
            if key in st.session_state:
                del st.session_state[key]
        st.toast("👋 Logged out successfully", icon="🚪")
        st.rerun()

# ------------------ Chat Display ------------------
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ------------------ Chat Input ------------------
user_input = st.chat_input("Ask something like 'book next Monday 2PM'")
if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.spinner("🤖 Agent is Typing..."):
        try:
            response = requests.post(API_URL, json={"message": user_input})
            if response.status_code == 200:
                reply = response.json()["response"]
            else:
                reply = "❌ Error from backend"
        except Exception as e:
            reply = f"❌ Could not reach backend: {e}"

    st.chat_message("assistant").markdown(reply)
    st.session_state.chat_history.append({"role": "assistant", "content": reply})
    save_current_chat()
