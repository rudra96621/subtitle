import os
import tempfile
import subprocess
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
    else:
        return "fonts/NotoSans-Regular.ttf"


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
            y = height - padding - len(lines) * 40

            for line in lines:
                text_size = draw.textbbox((0, 0), line, font=font)
                text_width = text_size[2] - text_size[0]
                text_height = text_size[3] - text_size[1]
                x = (width - text_width) // 2
                draw.rectangle([x - 10, y - 5, x + text_width + 10, y + text_height + 5], fill=(0, 0, 0))
                draw.text((x, y), line, font=font, fill=(255, 255, 255))
                y += text_height + 10

            frame = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)

        out.write(frame)

    cap.release()
    out.release()

    # ⚡️ Removed: cv2.destroyAllWindows() (not supported on headless servers)

    subprocess.run([
        "ffmpeg", "-y", "-i", temp_no_audio, "-i", video_path,
        "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0", output_path
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
