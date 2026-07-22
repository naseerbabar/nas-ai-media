# ---------------------------------------------------------------
# TEXT TO VIDEO (with audio)
# ---------------------------------------------------------------
st.write("---")
st.subheader("🎬 Create a Video from Text")
st.caption("Describe a scene. The model generates video with synchronized audio, including speech.")

t2v_prompt = st.text_area(
    "Describe your video",
    value="A man in a coffee shop looks at the camera and says, 'Are you talking to me?'",
    key="t2v_prompt",
    height=100
)

col_a, col_b, col_c = st.columns(3)
with col_a:
    t2v_resolution = st.selectbox("Resolution", ["480p", "720p", "1080p"], index=1, key="t2v_res")
with col_b:
    t2v_duration = st.selectbox("Duration (seconds)", ["auto", "4", "5", "6", "8", "10"], index=0, key="t2v_dur")
with col_c:
    t2v_aspect = st.selectbox("Aspect ratio", ["auto", "16:9", "9:16", "1:1"], index=0, key="t2v_aspect")

t2v_audio = st.checkbox("Generate audio (speech, effects, ambience)", value=True, key="t2v_audio")

if st.button("Generate Video", key="t2v_btn"):
    os.environ["FAL_KEY"] = fal_key
    with st.spinner("🎬 Creating your video (this can take several minutes)..."):
        try:
            t2v_handler = fal_client.submit(
                "bytedance/seedance-2.0/text-to-video",
                arguments={
                    "prompt": t2v_prompt,
                    "resolution": t2v_resolution,
                    "duration": t2v_duration,
                    "aspect_ratio": t2v_aspect,
                    "generate_audio": t2v_audio
                }
            )
            t2v_result = t2v_handler.get()
            st.session_state.t2v_video_url = t2v_result['video']['url']
        except Exception as e:
            st.error(f"Text-to-video error: {e}")

if st.session_state.get("t2v_video_url"):
    st.success("Your video is ready!")
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        st.video(st.session_state.t2v_video_url)
    try:
        vid_bytes = requests.get(st.session_state.t2v_video_url).content
        st.download_button(
            label="⬇️ Download Video",
            data=vid_bytes,
            file_name="text_to_video.mp4",
            mime="video/mp4",
            key="download_t2v_btn"
        )
    except Exception as e:
        st.warning(f"Could not prepare download: {e}")
