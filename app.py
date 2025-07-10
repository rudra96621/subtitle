import streamlit as st
import whisper
from deep_translator import GoogleTranslator
import tempfile
import os
import mysql.connector
from subtitle_generator import get_font_for_text, export_srt, render_subtitles_on_video

# MySQL connection
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",             # change to your MySQL username
        password="", # change to your MySQL password
        database="subtitle_app"
    )

# Session initialization
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if 'username' not in st.session_state:
    st.session_state.username = ""

if 'page' not in st.session_state:
    st.session_state.page = 'main'

if 'SUPPORTED_LANGS' not in st.session_state:
    SUPPORTED_LANGS = GoogleTranslator().get_supported_languages(as_dict=True)
    st.session_state.LANG_DICT = {name.title(): code for name, code in SUPPORTED_LANGS.items()}

if 'processing_done' not in st.session_state:
    st.session_state.processing_done = False

if 'srt_file' not in st.session_state:
    st.session_state.srt_file = None

if 'video_file' not in st.session_state:
    st.session_state.video_file = None

if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None

if 'spoken_lang' not in st.session_state:
    st.session_state.spoken_lang = 'Auto'

if 'target_lang' not in st.session_state:
    st.session_state.target_lang = 'English'

os.makedirs('output', exist_ok=True)

# --------------------- Authentication ---------------------

def signup():
    st.markdown("## 📝 Sign Up")
    username = st.text_input("👤 Create Username")
    password = st.text_input("🔒 Create Password", type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sign Up"):
            if username and password:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
                if cursor.fetchone():
                    st.error("⚠️ Username already exists!")
                else:
                    cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
                    conn.commit()
                    st.success("✅ Account created! Please log in.")
                    st.session_state.page = 'login'
                    st.rerun()
                conn.close()
            else:
                st.error("❌ Please fill in all fields.")

    with col2:
        if st.button("⬅️ Go to Login"):
            st.session_state.page = 'login'
            st.rerun()

def login():
    st.markdown("## 🔐 Login")
    username = st.text_input("👤 Username")
    password = st.text_input("🔒 Password", type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login"):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
            if cursor.fetchone():
                st.session_state.authenticated = True
                st.session_state.username = username
                st.success("✅ Logged in successfully!")
                st.session_state.page = 'main'
                st.rerun()
            else:
                st.error("❌ Invalid credentials")
            conn.close()

    with col2:
        if st.button("✍️ Go to Sign Up"):
            st.session_state.page = 'signup'
            st.rerun()

def logout():
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.page = 'login'
    st.session_state.processing_done = False
    st.session_state.srt_file = None
    st.session_state.video_file = None
    st.session_state.uploaded_file = None
    st.rerun()

# --------------------- Subtitle Processing ---------------------

def process_video():
    file = st.session_state.uploaded_file
    spoken_lang = st.session_state.spoken_lang
    target_lang = st.session_state.target_lang

    with st.spinner("🔄 Transcribing and translating..."):
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        temp_file.write(file.read())
        temp_file.close()

        model = whisper.load_model('tiny')
        transcription = model.transcribe(
            temp_file.name, 
            language=None if spoken_lang == 'Auto' else st.session_state.LANG_DICT[spoken_lang]
        )

        base_name = os.path.splitext(os.path.basename(temp_file.name))[0]
        srt_filename = f"{base_name}.srt"
        video_filename = f"{base_name}_subtitled.mp4"

        segments = transcription['segments']
        translated_segments = []
        for seg in segments:
            try:
                translated_text_segment = GoogleTranslator(
                    source='auto',
                    target=st.session_state.LANG_DICT[target_lang]
                ).translate(seg['text'])
            except Exception:
                translated_text_segment = '[Translation Failed]'
            translated_segments.append({
                'start': seg['start'],
                'end': seg['end'],
                'text': translated_text_segment
            })

        srt_path = os.path.join('output', srt_filename)
        export_srt(translated_segments, srt_path)

        sample_text = translated_segments[0]['text'] if translated_segments else ''
        font_path = get_font_for_text(sample_text)

        video_output_path = os.path.join('output', video_filename)
        render_subtitles_on_video(temp_file.name, translated_segments, video_output_path, font_path)

        st.session_state.processing_done = True
        st.session_state.srt_file = srt_path
        st.session_state.video_file = video_output_path

        st.success("✅ Subtitle generation complete!")

        st.markdown("### 📥 Download Results")
        with open(st.session_state.srt_file, "rb") as file:
            st.download_button("📄 Download Subtitle (.srt)", file, os.path.basename(st.session_state.srt_file), key="srt_download")

        with open(st.session_state.video_file, "rb") as file:
            st.download_button("🎞️ Download Subtitled Video", file, os.path.basename(st.session_state.video_file), key="video_download")

# --------------------- Main Page ---------------------

def main_page():
    st.markdown("## 🎬 Subtitle Generator")
    st.write(f"👋 Welcome, **{st.session_state.username}**")
    st.markdown("---")

    with st.sidebar:
        st.header("🔧 Settings")
        st.session_state.spoken_lang = st.selectbox("🗣️ Spoken Language", ["Auto"] + list(st.session_state.LANG_DICT.keys()))
        st.session_state.target_lang = st.selectbox("🌐 Subtitle Language", list(st.session_state.LANG_DICT.keys()))
        st.button("Logout", on_click=logout)

    st.markdown("### 📤 Upload Video or Audio")
    st.session_state.uploaded_file = st.file_uploader("", type=['mp4', 'mp3', 'wav', 'm4a'])

    st.markdown("### ⚙️ Generate Subtitles")
    if st.button("▶️ Start Processing"):
        if not st.session_state.authenticated:
            st.warning("🔒 Please login to continue.")
            st.session_state.page = 'login'
            st.rerun()
        elif not st.session_state.uploaded_file:
            st.warning("⚠️ Please upload a file before starting.")
        else:
            process_video()

# --------------------- Router ---------------------

def main():
    if st.session_state.page == 'login':
        login()
    elif st.session_state.page == 'signup':
        signup()
    else:
        main_page()

if __name__ == "__main__":
    main()
