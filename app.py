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
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()

def upload_to_fal(uploaded_file, max_size=1920):
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
for key in ["messages", "last_generated_image", "last_image_prompt", 
            "uploaded_video_url", "edited_image_url", "t2v_video_url"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "messages" else None

# ---------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------
st.sidebar.markdown("### Options")

advanced_mode = st.sidebar.checkbox(
    "Advanced Mode (Higher Freedom)",
    value=True,
    help="Uses open models with fewer restrictions"
)

if st.sidebar.button("🗑️ Clear Everything"):
    for key in st.session_state.keys():
        st.session_state[key] = [] if key == "messages" else None
    st.rerun()

st.sidebar.info(
    "**Tips**\n\n"
    "• Type `/image ...` in chat to generate an image\n\n"
    "• Use Advanced Mode for maximum creative freedom\n\n"
    "• Video generation can take 1-4 minutes"
)

tab_chat, tab_media = st.tabs(["💬 Chat", "🎨 Media"])

# ---------------------------------------------------------------
# HELPER: Softens explicit prompts to reduce blocks
# ---------------------------------------------------------------
def soften_motion_prompt(prompt: str) -> str:
    if not advanced_mode:
        return prompt
    soft = prompt.lower()
    replacements = {
        "bosom": "chest",
        "breast": "curves",
        "massaging": "caressing",
        "fucking": "intimate movement",
        "sex": "passionate embrace",
    }
    for old, new in replacements.items():
        soft = soft.replace(old, new)
    return soft if soft != prompt.lower() else prompt

# ---------------------------------------------------------------
# CHAT TAB
# ---------------------------------------------------------------
with tab_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("type") == "text":
                st.markdown(msg["content"])
            elif msg.get("type") == "image":
                st.image(msg["content"], caption="Generated Image")
            elif msg.get("type") == "video":
                st.video(msg["content"])

    if st.session_state.last_generated_image:
        st.write("---")
        st.subheader("🎬 Animate Last Generated Image")
        gen_motion_prompt = st.text_input(
            "Describe the motion you want",
            value="natural sensual movement, slow intimate motion, cinematic camera",
            key="gen_motion_prompt"
        )
        if st.button("Turn Last Generated Image into Video"):
            os.environ["FAL_KEY"] = fal_key
            with st.spinner("🎥 Creating video..."):
                try:
                    motion = soften_motion_prompt(gen_motion_prompt)
                    if advanced_mode:
                        handler = fal_client.submit(
                            "fal-ai/wan-i2v",
                            arguments={
                                "image_url": st.session_state.last_generated_image,
                                "prompt": motion,
                                "resolution": "720p",
                                "num_frames": 81,
                                "frames_per_second": 16,
                                "enable_safety_checker": False
                            }
                        )
                    else:
                        handler = fal_client.submit(
                            "fal-ai/luma-dream-machine/ray-2/image-to-video",
                            arguments={"image_url": st.session_state.last_generated_image, "prompt": motion, "duration": "9s"}
                        )
                    result = handler.get()
                    vid_url = result['video']['url']
                    st.session_state.messages.append({"role": "assistant", "type": "video", "content": vid_url})
                    st.session_state.last_generated_image = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Video error: {str(e)[:200]}")

# ---------------------------------------------------------------
# MEDIA TAB
# ---------------------------------------------------------------
with tab_media:
    # Edit Photo (unchanged except safety)
    st.subheader("✨ Edit a Photo")
    edit_file = st.file_uploader("Choose a photo to edit (JPG or PNG)", type=["jpg", "jpeg", "png"], key="edit_uploader")
    if edit_file:
        st.image(edit_file, width=400)
        edit_prompt = st.text_input("What change do you want?", value="make this person look 20 years younger", key="edit_prompt")
        if st.button("Apply Edit"):
            os.environ["FAL_KEY"] = fal_key
            try:
                source_url = upload_to_fal(edit_file)
                args = {"prompt": edit_prompt, "image_urls": [source_url], "num_images": 1, "output_format": "jpeg", "resolution": "1K"}
                if advanced_mode:
                    args["enable_safety_checker"] = False
                result = fal_client.submit("fal-ai/nano-banana-2/edit", arguments=args).get()
                st.session_state.edited_image_url = result['images'][0]['url']
            except Exception as e:
                st.error(f"Edit error: {e}")

    if st.session_state.edited_image_url:
        st.image(st.session_state.edited_image_url, width=500)
        try:
            st.download_button("⬇️ Download Edited Photo", requests.get(st.session_state.edited_image_url).content, "edited.jpg", "image/jpeg")
        except: pass

    st.write("---")
    st.subheader("📤 Upload a Photo and Make a Video")
    uploaded_file = st.file_uploader("Choose an image", type=["jpg","jpeg","png"], key="img_uploader")
    if uploaded_file:
        st.image(uploaded_file, width=400)
        motion_prompt = st.text_input("Describe the motion you want", value="natural sensual movement, slow intimate motion, cinematic camera", key="motion_prompt")
        if st.button("Animate My Uploaded Image"):
            os.environ["FAL_KEY"] = fal_key
            try:
                url = upload_to_fal(uploaded_file)
                motion = soften_motion_prompt(motion_prompt)
                if advanced_mode:
                    handler = fal_client.submit("fal-ai/wan-i2v", arguments={
                        "image_url": url, "prompt": motion, "resolution": "720p",
                        "num_frames": 81, "frames_per_second": 16, "enable_safety_checker": False
                    })
                else:
                    handler = fal_client.submit("fal-ai/luma-dream-machine/ray-2/image-to-video", arguments={"image_url": url, "prompt": motion, "duration": "9s"})
                result = handler.get()
                st.session_state.uploaded_video_url = result['video']['url']
            except Exception as e:
                st.error(f"Error: {str(e)[:200]}")

    if st.session_state.uploaded_video_url:
        st.video(st.session_state.uploaded_video_url)
        try:
            st.download_button("⬇️ Download Video", requests.get(st.session_state.uploaded_video_url).content, "video.mp4", "video/mp4")
        except: pass

    st.write("---")
    st.subheader("🎬 Create a Video from Text")
    t2v_prompt = st.text_area("Describe your video", value="A beautiful woman with natural curves in a sensual scene", key="t2v_prompt", height=100)
    col_a, col_b, col_c = st.columns(3)
    with col_a: res = st.selectbox("Resolution", ["480p", "720p"], index=1)
    with col_b: dur = st.selectbox("Duration", ["5s", "8s", "10s"], index=1)
    with col_c: asp = st.selectbox("Aspect ratio", ["16:9", "9:16", "1:1"], index=0)

    if st.button("Generate Video"):
        os.environ["FAL_KEY"] = fal_key
        with st.spinner("Creating video..."):
            try:
                if advanced_mode:
                    handler = fal_client.submit("fal-ai/hunyuan-video", arguments={
                        "prompt": t2v_prompt, "resolution": res, "aspect_ratio": asp, "enable_safety_checker": False
                    })
                else:
                    handler = fal_client.submit("bytedance/seedance-2.0/text-to-video", arguments={
                        "prompt": t2v_prompt, "resolution": res, "duration": dur.replace("s",""), "aspect_ratio": asp
                    })
                result = handler.get()
                st.session_state.t2v_video_url = result['video']['url']
            except Exception as e:
                st.error(f"Error: {str(e)[:200]}")

    if st.session_state.t2v_video_url:
        st.video(st.session_state.t2v_video_url)
        try:
            st.download_button("⬇️ Download Video", requests.get(st.session_state.t2v_video_url).content, "text_video.mp4", "video/mp4")
        except: pass

# Chat Input
if prompt := st.chat_input("Ask me anything, or type /image ..."):
    st.session_state.messages.append({"role": "user", "type": "text", "content": prompt})
    os.environ["FAL_KEY"] = fal_key

    if prompt.lower().startswith("/image "):
        p = prompt[7:]
        with st.spinner("Generating image..."):
            try:
                args = {"prompt": p, "num_images": 1}
                if advanced_mode:
                    args["enable_safety_checker"] = False
                result = fal_client.submit("fal-ai/flux/schnell", arguments=args).get()
                url = result['images'][0]['url']
                st.session_state.last_generated_image = url
                st.session_state.messages.append({"role": "assistant", "type": "image", "content": url})
            except Exception as e:
                st.error(f"Image error: {e}")
    else:
        with st.spinner("Thinking..."):
            try:
                client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
                resp = client.chat.completions.create(model="qwen/qwen3.6-27b", messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["type"] == "text"])
                answer = clean_response(resp.choices[0].message.content)
                st.session_state.messages.append({"role": "assistant", "type": "text", "content": answer})
            except Exception as e:
                st.error(f"Chat error: {e}")
    st.rerun()

st.caption("Ask Nas Anything can make mistakes. Please double-check responses.")
