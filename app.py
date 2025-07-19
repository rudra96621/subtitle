# Import Required Modules
import streamlit as st
import whisper
import os
import tempfile
from deep_translator import GoogleTranslator
from subtitle_generator import get_font_for_text, export_srt, render_subtitles_on_video
from pymongo import MongoClient
import bcrypt
from urllib.parse import quote_plus

# MongoDB Connection
def get_database():
    username = "rudra"
    password = quote_plus("Rudra@123")  # URL-safe
    uri = f"mongodb+srv://{username}:{password}@cluster0.ucw0onm.mongodb.net/subtitleApp?retryWrites=true&w=majority"

    # Force TLS with cert requirements (recommended for Render)
    client = MongoClient(
        uri,
        ssl=True,
        ssl_cert_reqs=ssl.CERT_NONE  # Relax certificate checks
    )
    db = client["subtitleApp"]
    return db

# Initialize Collections
def create_tables():
    db = get_connection()
    if "users" not in db.list_collection_names():
        db.create_collection("users")

# 🌐 Session Initialization
for key, value in {
    'authenticated': False,
    'username': "",
    'page': 'main',
    'processing_done': False,
    'srt_file': None,
    'video_file': None,
    'uploaded_file': None,
    'spoken_lang': 'Auto',
    'target_lang': 'English',
    'show_dropdown': False,
    'device': 'CPU',
    'model_size': 'tiny',
    'history': [],
    'is_processing': False,
    'model_loaded': {}
}.items():
    if key not in st.session_state:
        st.session_state[key] = value

if 'SUPPORTED_LANGS' not in st.session_state:
    langs = GoogleTranslator().get_supported_languages(as_dict=True)
    st.session_state.LANG_DICT = {name.title(): code for name, code in langs.items()}

os.makedirs('output', exist_ok=True)

@st.cache_resource(show_spinner="🔄 Loading Whisper model...")
def load_whisper_model(model_size="tiny", device="cpu"):
    os.environ["WHISPER_CACHE_DIR"] = os.path.expanduser("~/.cache/whisper")
    return whisper.load_model(model_size, device=device)

def get_or_load_model():
    key = f"{st.session_state.model_size}_{st.session_state.device}"
    if key not in st.session_state.model_loaded:
        with st.spinner("🔄 Loading Whisper model..."):
            st.session_state.model_loaded[key] = load_whisper_model(
                model_size=st.session_state.model_size,
                device="cuda" if st.session_state.device == "GPU (CUDA)" else "cpu"
            )
    return st.session_state.model_loaded[key]

def signup():
    st.title("📝 Sign Up")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Sign Up"):
        if username and password:
            db = get_connection()
            users = db["users"]

            if users.find_one({"username": username}):
                st.error("Username already exists.")
            else:
                hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
                users.insert_one({"username": username, "password": hashed_pw, "history": []})
                st.success("Account created! Please log in.")
                st.session_state.page = "login"
                st.rerun()

def login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        db = get_connection()
        users = db["users"]

        user = users.find_one({"username": username})
        if user and bcrypt.checkpw(password.encode("utf-8"), user["password"]):
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.page = "main"

            st.session_state.history = []
            history_items = user.get("history", [])[-3:][::-1]

            for entry in history_items:
                video_file_path = entry.get("video_path")
                srt_file_path = entry.get("srt_path")
                try:
                    with open(video_file_path, "rb") as vid, open(srt_file_path, "rb") as srt:
                        st.session_state.history.append({
                            "video_name": os.path.basename(video_file_path),
                            "srt_name": os.path.basename(srt_file_path),
                            "video_data": vid.read(),
                            "srt_data": srt.read()
                        })
                except FileNotFoundError:
                    continue

            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.markdown("---")
    st.markdown("Don't have an account?")
    if st.button("Sign Up"):
        st.session_state.page = "signup"
        st.rerun()

def logout():
    st.session_state.clear()
    st.session_state.page = "login"
    st.rerun()

def profile_page():
    st.title("🧾 Profile")
    new_username = st.text_input("New Username", value=st.session_state.username)
    new_password = st.text_input("New Password", type="password")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("📏 Update"):
            db = get_connection()
            users = db["users"]
            hashed_pw = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
            users.update_one({"username": st.session_state.username}, {"$set": {"username": new_username, "password": hashed_pw}})
            st.session_state.username = new_username
            st.success("Profile updated!")

    with col2:
        if st.button("🏠 Back to Home"):
            st.session_state.page = "main"
            st.rerun()

def estimate_total_time(duration_sec, model_size="medium"):
    speed = {"tiny": 1.0, "base": 1.5, "small": 2.0, "medium": 3.5, "large": 5.0}
    return int(duration_sec * speed.get(model_size, 2))

def format_eta(seconds):
    return f"{seconds // 60}m {seconds % 60}s" if seconds >= 60 else f"{seconds}s"

def save_subtitle_history(username, original_language, translated_language, filename):
    db = get_connection()
    users = db["users"]

    video_path = os.path.join("output", filename)
    srt_path = video_path.replace("_subtitled.mp4", ".srt")

    new_entry = {
        "video_path": video_path,
        "srt_path": srt_path,
        "original_language": original_language,
        "translated_language": translated_language
    }

    user = users.find_one({"username": username})
    history = user.get("history", [])

    history.append(new_entry)
    if len(history) > 3:
        to_delete = history[:-3]
        for entry in to_delete:
            try:
                if os.path.exists(entry["video_path"]):
                    os.remove(entry["video_path"])
                if os.path.exists(entry["srt_path"]):
                    os.remove(entry["srt_path"])
            except Exception as e:
                print(f"Error deleting files: {e}")
        history = history[-3:]

    users.update_one({"username": username}, {"$set": {"history": history}})

def process_video():
    st.session_state.is_processing = True
    file = st.session_state.uploaded_file
    spoken_lang = st.session_state.spoken_lang
    target_lang = st.session_state.target_lang

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
        temp_file.write(file.read())
        temp_path = temp_file.name

    duration = whisper.audio.load_audio(temp_path).shape[0] / whisper.audio.SAMPLE_RATE
    st.markdown(f"🕒 **Estimated time:** `{format_eta(estimate_total_time(duration, st.session_state.model_size))}`")

    progress_bar = st.progress(0)
    progress = 0

    model = get_or_load_model()
    progress_bar.progress(progress := 20)

    transcription = model.transcribe(temp_path, language=None if spoken_lang == "Auto" else st.session_state.LANG_DICT[spoken_lang])
    progress_bar.progress(progress := 45)

    segments = transcription['segments']
    translated_segments = []
    for seg in segments:
        try:
            translated = GoogleTranslator(source='auto', target=st.session_state.LANG_DICT[target_lang]).translate(seg['text'])
        except Exception:
            translated = "[Translation Failed]"
        translated_segments.append({'start': seg['start'], 'end': seg['end'], 'text': translated})
    progress_bar.progress(progress := 70)

    base = os.path.splitext(os.path.basename(temp_path))[0]
    srt_path = f"output/{base}.srt"
    video_output_path = f"output/{base}_subtitled.mp4"
    font_path = get_font_for_text(translated_segments[0]['text'] if translated_segments else '')

    export_srt(translated_segments, srt_path)
    progress_bar.progress(progress := 85)

    render_subtitles_on_video(temp_path, translated_segments, video_output_path, font_path)
    progress_bar.progress(100)

    st.session_state.processing_done = True
    st.session_state.srt_file = srt_path
    st.session_state.video_file = video_output_path
    st.session_state.is_processing = False

    with open(srt_path, "rb") as f1, open(video_output_path, "rb") as f2:
        st.session_state.history.insert(0, {
            "video_name": os.path.basename(video_output_path),
            "srt_name": os.path.basename(srt_path),
            "video_data": f2.read(),
            "srt_data": f1.read()
        })
        st.session_state.history = st.session_state.history[:3]

    save_subtitle_history(st.session_state.username, spoken_lang, target_lang, os.path.basename(video_output_path))

# 🏠 Main Page

def main_page():
    st.markdown("## 🎨 Subtitle Generator")
    st.write(f"👋 Welcome, **{st.session_state.username}**")
    st.markdown("---")

    # Sidebar
    with st.sidebar:
        avatar_letter = st.session_state.username[:1].upper()
        if st.button(avatar_letter, key="avatar_btn"):
            if not st.session_state.is_processing:
                st.session_state.show_dropdown = not st.session_state.show_dropdown
        if st.session_state.show_dropdown:
            if st.button("🧾 Profile") and not st.session_state.is_processing:
                st.session_state.page = "profile"
                st.session_state.show_dropdown = False
                st.rerun()
            if st.button("🚪 Logout") and not st.session_state.is_processing:
                logout()

        st.markdown("## 📂 Recent Downloads")
        if st.session_state.history:
            for idx, item in enumerate(st.session_state.history):
                st.markdown(f"**🎮 {item['video_name']}**")
                st.download_button("📄 Subtitle", item['srt_data'], file_name=item['srt_name'], key=f"srt_{idx}")
                st.download_button("🎮 Video", item['video_data'], file_name=item['video_name'], key=f"vid_{idx}")
        else:
            st.info("No recent files yet.")

        with st.expander("❓ How to Use"):
            st.markdown("""
1. Upload a video/audio  
2. Choose the spoken language  
3. Pick model 🐆/🐬/🐋  
4. Choose subtitle language  
5. Click ▶️ Start  
6. Download results
            """)

    # Upload & language
    st.markdown("### 📤 Upload Audio/Video")
    st.session_state.uploaded_file = st.file_uploader("", type=["mp4", "mp3", "wav", "m4a"])
    st.session_state.spoken_lang = st.selectbox("🗣️ Spoken Language", ["Auto"] + list(st.session_state.LANG_DICT.keys()))

    # Model Cards
    st.markdown("### ⚙️ Transcription Mode")
    model_map = {
        "tiny": ("🐆 Cheetah", "Fastest But Less Accurate"),
        "medium": ("🐬 Dolphin", "Balanced In Both Accuracy And Speed"),
        "large": ("🐋 Whale", "Most Accurate But Very Slow")
    }
    cols = st.columns(3)
    for i, (key, (emoji, label)) in enumerate(model_map.items()):
        with cols[i]:
            if st.button(f"{emoji} {label}", key=key):
                st.session_state.model_size = key
    selected_emoji, selected_label = model_map[st.session_state.model_size]
    st.markdown(f"<div style='margin-top:10px;padding:8px;border-radius:6px;background-color:#004225;color:white;font-weight:bold;display:inline-block;'>✅ Selected: {selected_label} Mode ({selected_emoji})</div>", unsafe_allow_html=True)

    # Subtitle language
    st.markdown("### 🌐 Subtitle Language")
    st.session_state.target_lang = st.selectbox("Select subtitle output language:", list(st.session_state.LANG_DICT.keys()))

    # Process button
    if st.button("▶️ Start Processing"):
        if not st.session_state.authenticated:
            st.warning("Login required.")
            st.session_state.page = "login"
            st.rerun()
        elif not st.session_state.uploaded_file:
            st.warning("Please upload a file.")
        else:
            process_video()

    # Result
    if st.session_state.processing_done:
        st.success("✅ Subtitles generated!")
        col1, col2 = st.columns(2)
        with col1:
            with open(st.session_state.srt_file, "rb") as srt:
                st.download_button("📄 Download Subtitle", srt, file_name=os.path.basename(st.session_state.srt_file))
        with col2:
            with open(st.session_state.video_file, "rb") as vid:
                st.download_button("🎮 Download Video", vid, file_name=os.path.basename(st.session_state.video_file))
        
# 🚦 Router
def main():
    create_tables()
    if st.session_state.page == "login":
        login()
    elif st.session_state.page == "signup":
        signup()
    elif st.session_state.page == "profile":
        profile_page()
    else:
        main_page()

if __name__ == "__main__":
    main()
