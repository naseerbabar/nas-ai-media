import streamlit as st
import openai
import os
import re
import fal_client
import requests
from PIL import Image

st.set_page_config(page_title="Ask Nas Anything", page_icon="🎨", layout="wide")
st.title("🎨 Ask Nas Anything")
st.caption("Chat • Generate images • Edit photos • Make videos")

groq_key = st.secrets["groq_key"]
fal_key = st.secrets["fal_key"]

def clean_response(text):
    """Strip model reasoning tags so only the final answer is shown."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()

def upload_to_fal(uploaded_file, max_size=1920):
    """Resize if needed, save temporarily, upload to fal, return the URL."""
    img = Image.open(uploaded_file)
    img = img.convert("RGB")
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size))
    temp_path = "temp_upload.jpg"
    img.save(temp_path, "JPEG", quality=95)
    url = fal_client.upload_file(temp_path)
    os.remove(temp_path)
    return url

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_generated_image" not in st.session_state:
    st.session_state.last_generated_image = None
if "last_image_prompt" not in st.session_state:
    st.session_state.last_image_prompt = ""
if "uploaded_video_url" not in st.session_state:
    st.session_state.uploaded_video_url = None
if "edited_image_url" not in st.session_state:
    st.session_state.edited_image_url = None
if "t2v_video_url" not in st.session_state:
    st.session_state.t2v_video_url = None

# ---------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------
st.sidebar.markdown("### Options")

advanced_mode = st.sidebar.checkbox(
    "Advanced Mode (Higher Freedom)",
    value=True,
    help="Uses more open models with fewer restrictions"
)

if st.sidebar.button("🗑️ Clear Everything"):
    st.session_state.messages = []
    st.session_state.last_generated_image = None
    st.session_state.last_image_prompt = ""
    st.session_state.uploaded_video_url = None
    st.session_state.edited_image_url = None
    st.session_state.t2v_video_url = None
    st.rerun()

st.sidebar.info(
    "**Tips**\n\n"
    "• Type `/image a red car` in chat to generate an image\n\n"
    "• Photo editing and video are in the Media tab\n\n"
    "• Advanced Mode provides higher creative freedom\n\n"
    "• Video generation can take 1-4 minutes"
)

tab_chat, tab_media = st.tabs(["💬 Chat", "🎨 Media"])

# ---------------------------------------------------------------
# CHAT TAB
# ---------------------------------------------------------------
with tab_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["type"] == "text":
                st.markdown(msg["content"])
            elif msg["type"] == "image":
                st.image(msg["content"], caption="Generated Image")
            elif msg["type"] == "video":
                st.video(msg["content"])

    if st.session_state.last_generated_image:
        st.write("---")
        st.subheader("🎬 Animate Last Generated Image")

        gen_motion_prompt = st.text_input(
            "Describe the motion you want",
            value="natural body movement, cinematic camera",
            key="gen_motion_prompt"
        )

        if st.button("Turn Last Generated Image into Video", key="video_gen_btn"):
            os.environ["FAL_KEY"] = fal_key
            with st.spinner("🎥 Creating video (1-3 minutes)..."):
                try:
                    if advanced_mode:
                        video_handler = fal_client.submit(
                            "fal-ai/wan-i2v",
                            arguments={
                                "image_url": st.session_state.last_generated_image,
                                "prompt": gen_motion_prompt,
                                "resolution": "720p",
                                "num_frames": 81,
                                "frames_per_second": 16,
                                "enable_safety_checker": False,
                                "enable_prompt_expansion": False
                            }
                        )
                    else:
                        video_handler = fal_client.submit(
                            "fal-ai/luma-dream-machine/ray-2/image-to-video",
                            arguments={
                                "image_url": st.session_state.last_generated_image,
                                "prompt": gen_motion_prompt,
                                "duration": "9s"
                            }
                        )

                    video_result = video_handler.get()
                    vid_url = video_result['video']['url']
                    st.session_state.messages.append({"role": "assistant", "type": "video", "content": vid_url})
                    st.session_state.last_generated_image = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Video error: {e}")

# ---------------------------------------------------------------
# MEDIA TAB
# ---------------------------------------------------------------
with tab_media:

    st.subheader("✨ Edit a Photo")
    st.caption("Upload a photo and describe the change you want in plain language.")

    edit_file = st.file_uploader(
        "Choose a photo to edit (JPG or PNG)",
        type=["jpg", "jpeg", "png"],
        key="edit_uploader"
    )

    if edit_file is not None:
        st.image(edit_file, caption="Original photo", width=400)

        edit_prompt = st.text_input(
            "What change do you want?",
            value="make this person look 20 years younger",
            key="edit_prompt"
        )

        if st.button("Apply Edit", key="edit_btn"):
            os.environ["FAL_KEY"] = fal_key
            try:
                with st.spinner("📤 Uploading photo..."):
                    source_url = upload_to_fal(edit_file)

                with st.spinner("✨ Editing photo..."):
                    edit_args = {
                        "prompt": edit_prompt,
                        "image_urls": [source_url],
                        "num_images": 1,
                        "output_format": "jpeg",
                        "resolution": "1K"
                    }
                    if advanced_mode:
                        edit_args["enable_safety_checker"] = False

                    edit_handler = fal_client.submit(
                        "fal-ai/nano-banana-2/edit",
                        arguments=edit_args
                    )
                    edit_result = edit_handler.get()
                    st.session_state.edited_image_url = edit_result['images'][0]['url']
            except Exception as e:
                st.error(f"Edit error: {e}")

    if st.session_state.edited_image_url:
        st.success("Edit complete!")
        st.image(st.session_state.edited_image_url, caption="Edited photo", width=500)
        try:
            img_bytes = requests.get(st.session_state.edited_image_url).content
            st.download_button(
                label="⬇️ Download Edited Photo",
                data=img_bytes,
                file_name="edited_photo.jpg",
                mime="image/jpeg",
                key="download_edit_btn"
            )
        except Exception as e:
            st.warning(f"Could not prepare download: {e}")

    st.write("---")
    st.subheader("📤 Upload a Photo and Make a Video")

    uploaded_file = st.file_uploader(
        "Choose an image (JPG or PNG)",
        type=["jpg", "jpeg", "png"],
        key="img_uploader"
    )

    if uploaded_file is not None:
        st.image(uploaded_file, caption="Your uploaded image", width=400)

        motion_prompt = st.text_input(
            "Describe the motion you want",
            value="natural sensual movement, soft body motion, cinematic camera",
            key="motion_prompt"
        )

        if st.button("Animate My Uploaded Image", key="upload_video_btn"):
            os.environ["FAL_KEY"] = fal_key
            try:
                with st.spinner("📤 Preparing and uploading your image..."):
                    uploaded_url = upload_to_fal(uploaded_file)

                with st.spinner("🎥 Creating video (this takes 1-3 minutes)..."):
                    if advanced_mode:
                        video_handler = fal_client.submit(
                            "fal-ai/wan-i2v",
                            arguments={
                                "image_url": uploaded_url,
                                "prompt": motion_prompt,
                                "resolution": "720p",
                                "num_frames": 81,
                                "frames_per_second": 16,
                                "enable_safety_checker": False,
                                "enable_prompt_expansion": False
                            }
                        )
                    else:
                        video_handler = fal_client.submit(
                            "fal-ai/luma-dream-machine/ray-2/image-to-video",
                            arguments={
                                "image_url": uploaded_url,
                                "prompt": motion_prompt,
                                "duration": "9s"
                            }
                        )

                    video_result = video_handler.get()
                    st.session_state.uploaded_video_url = video_result['video']['url']
            except Exception as e:
                st.error(f"Error: {e}")

    if st.session_state.uploaded_video_url:
        st.success("Your video is ready!")
        c1, c2, c3 = st.columns([2, 1, 2])
        with c2:
            st.video(st.session_state.uploaded_video_url)
        try:
            video_bytes = requests.get(st.session_state.uploaded_video_url).content
            st.download_button(
                label="⬇️ Download Video",
                data=video_bytes,
                file_name="nas_ai_video.mp4",
                mime="video/mp4",
                key="download_vid_btn"
            )
        except Exception as e:
            st.warning(f"Could not prepare download: {e}")

    st.write("---")
    st.subheader("🎬 Create a Video from Text")
    st.caption("Describe a scene.")

    t2v_prompt = st.text_area(
        "Describe your video",
        value="A beautiful woman with natural curves moving slowly and sensually",
        key="t2v_prompt",
        height=100
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        t2v_resolution = st.selectbox("Resolution", ["480p", "720p"], index=1, key="t2v_res")
    with col_b:
        t2v_duration = st.selectbox("Duration", ["5s", "8s", "10s"], index=0, key="t2v_dur")
    with col_c:
        t2v_aspect = st.selectbox("Aspect ratio", ["16:9", "9:16", "1:1"], index=0, key="t2v_aspect")

    if st.button("Generate Video", key="t2v_btn"):
        os.environ["FAL_KEY"] = fal_key
        with st.spinner("🎬 Creating your video (this can take several minutes)..."):
            try:
                if advanced_mode:
                    t2v_handler = fal_client.submit(
                        "fal-ai/hunyuan-video",
                        arguments={
                            "prompt": t2v_prompt,
                            "resolution": t2v_resolution,
                            "aspect_ratio": t2v_aspect,
                            "enable_safety_checker": False
                        }
                    )
                else:
                    t2v_handler = fal_client.submit(
                        "bytedance/seedance-2.0/text-to-video",
                        arguments={
                            "prompt": t2v_prompt,
                            "resolution": t2v_resolution,
                            "duration": t2v_duration.replace("s", ""),
                            "aspect_ratio": t2v_aspect,
                            "generate_audio": True
                        }
                    )

                t2v_result = t2v_handler.get()
                st.session_state.t2v_video_url = t2v_result['video']['url']
            except Exception as e:
                st.error(f"Text-to-video error: {e}")

    if st.session_state.t2v_video_url:
        st.success("Your video is ready!")
        d1, d2, d3 = st.columns([1, 3, 1])
        with d2:
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

# ---------------------------------------------------------------
# CHAT INPUT
# ---------------------------------------------------------------
if prompt := st.chat_input("Ask me anything, or type /image followed by a description..."):
    st.session_state.messages.append({"role": "user", "type": "text", "content": prompt})

    os.environ["FAL_KEY"] = fal_key

    if prompt.lower().startswith("/image "):
        image_prompt = prompt[7:]
        with st.spinner("🎨 Generating image..."):
            try:
                args = {
                    "prompt": image_prompt,
                    "num_images": 1
                }
                if advanced_mode:
                    args["enable_safety_checker"] = False

                handler = fal_client.submit("fal-ai/flux/schnell", arguments=args)
                result = handler.get()
                img_url = result['images'][0]['url']
                st.session_state.last_generated_image = img_url
                st.session_state.last_image_prompt = image_prompt
                st.session_state.messages.append({"role": "assistant", "type": "image", "content": img_url})
            except Exception as e:
                st.error(f"Image generation error: {e}")
    else:
        with st.spinner("Thinking..."):
            try:
                client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
                response = client.chat.completions.create(
                    model="qwen/qwen3.6-27b",
                    messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["type"] == "text"]
                )
                answer = clean_response(response.choices[0].message.content)
                st.session_state.messages.append({"role": "assistant", "type": "text", "content": answer})
            except Exception as e:
                st.error(f"Chat error: {e}")
    st.rerun()

st.caption("Ask Nas Anything can make mistakes. Please double-check responses.")
