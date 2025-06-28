import streamlit as st
import whisper
from deep_translator import GoogleTranslator
import tempfile
import os
from subtitle_generator import get_font_for_text, export_srt, render_subtitles_on_video

# Initialize session state variables
if 'users' not in st.session_state:
    st.session_state.users = {}

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if 'username' not in st.session_state:
    st.session_state.username = ""

if 'page' not in st.session_state:
    st.session_state.page = 'login'

if 'SUPPORTED_LANGS' not in st.session_state:
    SUPPORTED_LANGS = GoogleTranslator().get_supported_languages(as_dict=True)
    st.session_state.LANG_DICT = {name.title(): code for name, code in SUPPORTED_LANGS.items()}

os.makedirs('output', exist_ok=True)


def merge_segments(segments, max_gap=1.0):
    if not segments:
        return []

    merged = []
    current = segments[0].copy()

    for seg in segments[1:]:
        if seg['start'] - current['end'] <= max_gap:
            current['end'] = seg['end']
            current['text'] += ' ' + seg['text']
        else:
            merged.append(current)
            current = seg.copy()

    merged.append(current)
    return merged


def signup():
    st.title("📝 Sign Up")
    username = st.text_input("Create Username")
    password = st.text_input("Create Password", type="password")

    if st.button("Sign Up"):
        if username in st.session_state.users:
            st.error("Username already exists!")
        else:
            st.session_state.users[username] = password
            st.success("Account created successfully! Please log in.")
            st.session_state.page = 'login'
            st.rerun()

    if st.button("Go to Login"):
        st.session_state.page = 'login'
        st.rerun()


def login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in st.session_state.users and st.session_state.users[username] == password:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid username or password")

    if st.button("Go to Sign Up"):
        st.session_state.page = 'signup'
        st.rerun()


def logout():
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.page = 'login'
    st.rerun()


def main_page():
    st.title("🎬 Subtitle Generator")

    st.write(f"Welcome, {st.session_state.username}!")
    if st.button("Logout"):
        logout()

    file = st.file_uploader("Upload Video or Audio", type=['mp4', 'mp3', 'wav', 'm4a'])

    spoken_lang = st.selectbox("Spoken Language", ["Auto"] + list(st.session_state.LANG_DICT.keys()))
    target_lang = st.selectbox("Subtitle Language", list(st.session_state.LANG_DICT.keys()))

    if st.button("Generate Subtitles"):
        if file is not None:
            with st.spinner("Processing..."):
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                temp_file.write(file.read())
                temp_file.close()

                model = whisper.load_model('tiny')
                transcription = model.transcribe(temp_file.name, language=None if spoken_lang == 'Auto' else st.session_state.LANG_DICT[spoken_lang])
                transcribed_text = transcription['text']

                segments = transcription['segments']

                translated_segments = []
                for seg in segments:
                    text = seg['text']
                    if not text or text.strip() == "":
                        continue  # Skip empty segments
                    try:
                        translated_text_segment = GoogleTranslator(source='auto', target=st.session_state.LANG_DICT[target_lang]).translate(text)
                    except Exception:
                        translated_text_segment = '[Translation Failed]'
                    translated_segments.append({
                        'start': seg['start'],
                        'end': seg['end'],
                        'text': translated_text_segment if translated_text_segment else '[No Content]'
                    })

                # Merge close subtitle segments
                translated_segments = merge_segments(translated_segments)

                if not translated_segments:
                    st.error("No valid subtitles found after processing.")
                    return

                base_name = os.path.splitext(os.path.basename(temp_file.name))[0]
                srt_filename = f"{base_name}.srt"
                video_filename = f"{base_name}_subtitled.mp4"

                srt_path = os.path.join('output', srt_filename)
                export_srt(translated_segments, srt_path)

                sample_text = translated_segments[0]['text'] if translated_segments else ''
                font_path = get_font_for_text(sample_text)

                video_output_path = os.path.join('output', video_filename)
                render_subtitles_on_video(temp_file.name, translated_segments, video_output_path, font_path)

                st.success("Subtitle generation complete!")

                with open(srt_path, "rb") as file:
                    st.download_button("Download Subtitle (.srt)", file, srt_filename)

                with open(video_output_path, "rb") as file:
                    st.download_button("Download Subtitled Video", file, video_filename)
        else:
            st.error("Please upload a file first.")


def main():
    if not st.session_state.authenticated:
        if st.session_state.page == 'login':
            login()
        elif st.session_state.page == 'signup':
            signup()
    else:
        main_page()


if __name__ == "__main__":
    main()
