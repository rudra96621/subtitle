import os
import tempfile
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import whisper
import srt
from datetime import timedelta
import cv2
import textwrap
import numpy as np
from PIL import ImageFont, ImageDraw, Image
import re
from deep_translator import GoogleTranslator

SUPPORTED_LANGS = GoogleTranslator().get_supported_languages(as_dict=True)
LANG_DICT = {name.title(): code for name, code in SUPPORTED_LANGS.items()}

def get_font_for_text(text):
    if re.search(r'[\u0600-\u06FF]', text):
        return "fonts/NotoSansArabic-Regular.ttf"
    elif re.search(r'[\u0590-\u05FF]', text):
        return "fonts/NotoSansHebrew-Regular.ttf"
    elif re.search(r'[\u3040-\u30FF\u31F0-\u31FF]', text):
        return "fonts/NotoSansCJKjp-Regular.otf"
    elif re.search(r'[\uAC00-\uD7AF]', text):
        return "fonts/NotoSansCJKkr-Regular.otf"
    elif re.search(r'[\u4E00-\u9FFF]', text):
        return "fonts/NotoSansSC-Regular.ttf"
    elif re.search(r'[\u0900-\u097F]', text):
        return "fonts/NotoSansDevanagari-Regular.ttf"
    elif re.search(r'[\u0980-\u09FF]', text):
        return "fonts/NotoSansBengali-Regular.ttf"
    elif re.search(r'[\u0A00-\u0A7F]', text):
        return "fonts/NotoSansGurmukhi-Regular.ttf"
    elif re.search(r'[\u0A80-\u0AFF]', text):
        return "fonts/NotoSansGujarati-Regular.ttf"
    elif re.search(r'[\u0B00-\u0B7F]', text):
        return "fonts/NotoSansOriya-Regular.ttf"
    elif re.search(r'[\u0B80-\u0BFF]', text):
        return "fonts/NotoSansTamil-Regular.ttf"
    elif re.search(r'[\u0C00-\u0C7F]', text):
        return "fonts/NotoSansTelugu-Regular.ttf"
    elif re.search(r'[\u0C80-\u0CFF]', text):
        return "fonts/NotoSansKannada-Regular.ttf"
    elif re.search(r'[\u0D00-\u0D7F]', text):
        return "fonts/NotoSansMalayalam-Regular.ttf"
    elif re.search(r'[\u0E00-\u0E7F]', text):
        return "fonts/NotoSansThai-Regular.ttf"
    elif re.search(r'[\u0E80-\u0EFF]', text):
        return "fonts/NotoSansLao-Regular.ttf"
    elif re.search(r'[\u1780-\u17FF]', text):
        return "fonts/NotoSansKhmer-Regular.ttf"
    elif re.search(r'[\u1000-\u109F]', text):
        return "fonts/NotoSansMyanmar-Regular.ttf"
    elif re.search(r'[\u1200-\u137F]', text):
        return "fonts/NotoSansEthiopic-Regular.ttf"
    elif re.search(r'[\u0530-\u058F]', text):
        return "fonts/NotoSansArmenian-Regular.ttf"
    elif re.search(r'[\u10A0-\u10FF]', text):
        return "fonts/NotoSansGeorgian-Regular.ttf"
    else:
        return "fonts/NotoSans-Regular.ttf"

def select_video_file():
    return filedialog.askopenfilename(title="Select Video File", filetypes=[("Video Files", "*.mp4 *.avi *.mov")])

def extract_audio(video_path):
    audio_path = tempfile.mktemp(suffix=".wav")
    command = ['ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', audio_path]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return audio_path

def transcribe_audio(audio_path, model_size="medium"):
    model = whisper.load_model(model_size)
    result = model.transcribe(audio_path, task="transcribe")
    detected_lang = result.get("language", "unknown")
    return result["segments"], result["text"], detected_lang

def translate_segments(segments, target_lang):
    translated_segments = []
    for seg in segments:
        text = seg["text"]
        try:
            translated_text = GoogleTranslator(source="auto", target=target_lang).translate(text)
        except Exception:
            translated_text = "[Translation Failed]"
        translated_segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": translated_text
        })
    return translated_segments

def export_srt(segments, srt_path):
    subs = []
    for i, segment in enumerate(segments, start=1):
        subs.append(srt.Subtitle(index=i,
                                 start=timedelta(seconds=segment["start"]),
                                 end=timedelta(seconds=segment["end"]),
                                 content=segment["text"]))
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt.compose(subs))

def render_subtitles_on_video(video_path, segments, output_path, font_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    temp_no_audio = tempfile.mktemp(suffix=".mp4")
    out = cv2.VideoWriter(temp_no_audio, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

    font = ImageFont.truetype(font_path, 32)
    padding = 30
    frame_idx = 0
    segment_index = 0
    current_sub = ""

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        current_time = frame_idx / fps
        frame_idx += 1

        while segment_index < len(segments):
            start = segments[segment_index]["start"]
            end = segments[segment_index]["end"]
            if start <= current_time <= end:
                current_sub = segments[segment_index]["text"]
                break
            elif current_time > end:
                segment_index += 1
                current_sub = ""
            else:
                break

        if current_sub:
            frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(frame_pil)

            lines = textwrap.wrap(current_sub, width=40)
            y = height - padding - len(lines)*40

            for line in lines:
                text_size = draw.textbbox((0, 0), line, font=font)
                text_width = text_size[2] - text_size[0]
                text_height = text_size[3] - text_size[1]
                x = (width - text_width) // 2
                draw.rectangle([x-10, y-5, x+text_width+10, y+text_height+5], fill=(0, 0, 0))
                draw.text((x, y), line, font=font, fill=(255, 255, 255))
                y += text_height + 10

            frame = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)

        out.write(frame)

    cap.release()
    out.release()
    cv2.destroyAllWindows()

    subprocess.run([
        "ffmpeg", "-y", "-i", temp_no_audio, "-i", video_path,
        "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", output_path
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def process_video(video_path, target_lang_code, progress_callback, button):
    try:
        base_name = os.path.splitext(video_path)[0]
        progress_callback(5)
        audio_path = extract_audio(video_path)
        progress_callback(20)
        segments, full_text, detected_lang = transcribe_audio(audio_path)
        progress_callback(50)
        translated_segments = translate_segments(segments, target_lang_code)
        progress_callback(70)
        srt_path = base_name + ".srt"
        export_srt(translated_segments, srt_path)
        progress_callback(80)
        sample_text = translated_segments[0]['text'] if translated_segments else ''
        font_path = get_font_for_text(sample_text)
        final_output = base_name + "_with_subs.mp4"
        render_subtitles_on_video(video_path, translated_segments, final_output, font_path)
        progress_callback(100)
        with open(base_name + "_summary.txt", "w", encoding="utf-8") as f:
            f.write(full_text)
        messagebox.showinfo("Done!", f"Detected language: {detected_lang}\n\nSubtitled video saved as:\n{final_output}")
    except Exception as e:
        messagebox.showerror("Error", str(e))
    finally:
        button["state"] = "normal"

def run_gui():
    root = tk.Tk()
    root.title("Whisper Subtitle Translator (Auto Language Detection)")

    tk.Label(root, text="Subtitle Output Language:").pack(pady=5)
    target_lang_var = tk.StringVar(value="Arabic")
    target_menu = tk.OptionMenu(root, target_lang_var, *LANG_DICT.keys())
    target_menu.pack(pady=5)

    progress = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
    progress.pack(pady=10)

    def update_progress(val):
        progress["value"] = val
        root.update_idletasks()

    def on_submit():
        video_path = select_video_file()
        if not video_path:
            return
        target_lang_code = LANG_DICT[target_lang_var.get()]
        submit_btn["state"] = "disabled"
        update_progress(0)
        threading.Thread(target=process_video, args=(video_path, target_lang_code, update_progress, submit_btn)).start()

    submit_btn = tk.Button(root, text="Select Video & Generate Subtitle", command=on_submit)
    submit_btn.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    run_gui()
