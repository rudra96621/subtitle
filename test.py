result = process_video(temp_video_path, LANG_DICT[target_lang], progress_callback=update_progress)

if result:
    st.success(f"✅ Subtitled video generated successfully!\nDetected Language: {result['detected_language']}")

    with open(result["output_video"], "rb") as f:
        st.download_button("⬇️ Download Video with Subtitles", f, file_name=os.path.basename(result["output_video"]))

    with open(result["subtitle_file"], "rb") as f:
        st.download_button("⬇️ Download Subtitle File (.srt)", f, file_name=os.path.basename(result["subtitle_file"]))

    with open(result["summary_file"], "rb") as f:
        st.download_button("⬇️ Download Full Transcript", f, file_name=os.path.basename(result["summary_file"]))
else:
    st.error("Processing failed. Please check the logs.")
