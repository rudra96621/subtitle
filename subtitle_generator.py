import os                      # For interacting with the operating system (file paths, directories)
import tempfile                # To create temporary files and directories safely
import subprocess              # To run external commands (e.g., ffmpeg) as subprocesses
import threading               # For running tasks concurrently in threads (background processing)
import tkinter as tk           # Core Tkinter GUI module
from tkinter import filedialog, messagebox  # File dialogs and popup message boxes in Tkinter
from tkinter import ttk        # Themed Tkinter widgets (better styled widgets)
import whisper                 # OpenAI Whisper speech-to-text model for transcription
import srt                     # For handling subtitle (.srt) files (parsing and generation)
from datetime import timedelta # For handling time durations, useful for subtitle timestamps
import cv2                     # OpenCV for video processing and manipulation
import textwrap                # For wrapping and formatting text (subtitle line wrapping)
import numpy as np             # Numerical operations, image array manipulation
from PIL import ImageFont, ImageDraw, Image  # Pillow (PIL) for drawing text and fonts on images (subtitles rendering)
import re                      # Regular expressions, for pattern matching (e.g., font selection based on Unicode)
from deep_translator import GoogleTranslator  # For translating text segments using Google Translate API
import concurrent.futures      # For high-level concurrency, running translation or processing in parallel (threads or processes)


# Language setup
SUPPORTED_LANGS = GoogleTranslator().get_supported_languages(as_dict=True)
LANG_DICT = {name.title(): code for name, code in SUPPORTED_LANGS.items()}

# Font selection
def get_font_for_text(text):
    if re.search(r'[\u0600-\u06FF]', text): return "fonts/NotoSansArabic-Regular.ttf"
    elif re.search(r'[\u0590-\u05FF]', text): return "fonts/NotoSansHebrew-Regular.ttf"
    elif re.search(r'[\u3040-\u30FF\u31F0-\u31FF]', text): return "fonts/NotoSansCJKjp-Regular.otf"
    elif re.search(r'[\uAC00-\uD7AF]', text): return "fonts/NotoSansCJKkr-Regular.otf"
    elif re.search(r'[\u4E00-\u9FFF]', text): return "fonts/NotoSansSC-Regular.ttf"
    elif re.search(r'[\u0900-\u097F]', text): return "fonts/NotoSansDevanagari-Regular.ttf"
    elif re.search(r'[\u0980-\u09FF]', text): return "fonts/NotoSansBengali-Regular.ttf"
    elif re.search(r'[\u0A00-\u0A7F]', text): return "fonts/NotoSansGurmukhi-Regular.ttf"
    elif re.search(r'[\u0A80-\u0AFF]', text): return "fonts/NotoSansGujarati-Regular.ttf"
    elif re.search(r'[\u0B00-\u0B7F]', text): return "fonts/NotoSansOriya-Regular.ttf"
    elif re.search(r'[\u0B80-\u0BFF]', text): return "fonts/NotoSansTamil-Regular.ttf"
    elif re.search(r'[\u0C00-\u0C7F]', text): return "fonts/NotoSansTelugu-Regular.ttf"
    elif re.search(r'[\u0C80-\u0CFF]', text): return "fonts/NotoSansKannada-Regular.ttf"
    elif re.search(r'[\u0D00-\u0D7F]', text): return "fonts/NotoSansMalayalam-Regular.ttf"
    elif re.search(r'[\u0E00-\u0E7F]', text): return "fonts/NotoSansThai-Regular.ttf"
    elif re.search(r'[\u0E80-\u0EFF]', text): return "fonts/NotoSansLao-Regular.ttf"
    elif re.search(r'[\u1780-\u17FF]', text): return "fonts/NotoSansKhmer-Regular.ttf"
    elif re.search(r'[\u1000-\u109F]', text): return "fonts/NotoSansMyanmar-Regular.ttf"
    elif re.search(r'[\u1200-\u137F]', text): return "fonts/NotoSansEthiopic-Regular.ttf"
    elif re.search(r'[\u0530-\u058F]', text): return "fonts/NotoSansArmenian-Regular.ttf"
    elif re.search(r'[\u10A0-\u10FF]', text): return "fonts/NotoSansGeorgian-Regular.ttf"
    else: return "fonts/NotoSans-Regular.ttf"

# Translation

def translate_segment_parallel(segment, target_lang):
    try:
        translated = GoogleTranslator(source="auto", target=target_lang).translate(segment["text"])
    except Exception:
        translated = "[Translation Failed]"
    return {"start": segment["start"], "end": segment["end"], "text": translated}

def translate_segments(segments, target_lang):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(translate_segment_parallel, seg, target_lang) for seg in segments]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    return sorted(results, key=lambda x: x['start'])

# SRT export
def export_srt(segments, srt_path):
    subs = []
    for idx, seg in enumerate(segments, start=1):   
        if seg["text"].strip():
            subs.append(srt.Subtitle(index=idx,
                                     start=timedelta(seconds=seg["start"]),
                                     end=timedelta(seconds=seg["end"]),
                                     content=seg["text"].strip()))
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt.compose(subs))

# Subtitle rendering

def render_subtitles_on_video(video_path, segments, output_path, font_path, progress_callback=None):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    temp_no_audio = tempfile.mktemp(suffix=".mp4")
    out = cv2.VideoWriter(temp_no_audio, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))

    font_size = max(24, width // 40)
    font = ImageFont.truetype(font_path, font_size)
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
            seg = segments[segment_index]
            if seg["start"] <= current_time <= seg["end"]:
                current_sub = seg["text"]
                break
            elif current_time > seg["end"]:
                segment_index += 1
                current_sub = ""
            else:
                break

        if current_sub:
            frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(frame_pil)

            max_chars_per_line = max(20, width // (font_size // 2))
            wrapped_lines = textwrap.wrap(current_sub, width=max_chars_per_line)
            wrapped_lines = wrapped_lines[:2]  # Limit to 2 lines

            line_height = font_size + 8
            y = height - padding - line_height * len(wrapped_lines)

            for line in wrapped_lines:
                text_width = draw.textlength(line, font=font)
                x = (width - text_width) // 2

                for dx in [-2, 2]:
                    for dy in [-2, 2]:
                        draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))
                draw.text((x, y), line, font=font, fill=(255, 255, 255))
                y += line_height

            frame = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)
        out.write(frame)

        if progress_callback and frame_count > 0:
            progress_callback(80 + (frame_idx / frame_count) * 15)

    cap.release()
    out.release()
    cv2.destroyAllWindows()

    subprocess.run([
        "ffmpeg", "-y", "-i", temp_no_audio, "-i", video_path,
        "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", output_path
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if progress_callback:
        progress_callback(100)
