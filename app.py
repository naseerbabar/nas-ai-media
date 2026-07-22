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

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["type"] == "text":
            st.markdown(msg["content"])
        elif msg["type"] == "image":
            st.image(msg["content"], caption="Generated Image")
        elif msg["type"] == "video":
            st.video(msg["content"])

# Chat input
if prompt := st.chat_input("Ask me anything, or type /image followed by a description..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "type": "text", "content": prompt})

    os.environ["FAL_KEY"] = fal_key

    # IMAGE GENERATION
    if prompt.lower().startswith("/image "):
        image_prompt = prompt[7:]
        with st.spinner("🎨 Generating image..."):
            try:
                handler = fal_client.submit("fal-ai/flux/schnell", arguments={"prompt": image_prompt})
                result = handler.get()
                img_url = result['images'][0]['url']

                st.session_state.last_generated_image = img_url
                st.session_state.last_image_prompt = image_prompt

                with st.chat_message("assistant"):
                    st.image(img_url, caption=image_prompt)
                st.session_state.messages.append({"role": "assistant", "type": "image", "content": img_url})
                st.rerun()
            except Exception as e:
                st.error(f"Image generation error: {e}")

    # TEXT CHAT
    else:
        with st.spinner("Thinking..."):
            try:
                client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
                response = client.chat.completions.create(
                    model="qwen/qwen3.6-27b",
                    messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["type"] == "text"]
                )
                answer = clean_response(response.choices[0].message.content)
                with st.chat_message("assistant"):
                    st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "type": "text", "content": answer})
            except Exception as e:
                st.error(f"Chat error: {e}")

# ANIMATE LAST GENERATED IMAGE
if st.session_state.last_generated_image:
    st.write("---")
    st.subheader("🎬 Animate Last Generated Image")

    gen_motion_prompt = st.text_input(
        "Describe the motion you want",
        value="cinematic camera movement, slow motion",
        key="gen_motion_prompt"
    )

    if st.button("Turn Last Generated Image into Video", key="video_gen_btn"):
        os.environ["FAL_KEY"] = fal_key
        with st.spinner("🎥 Creating video (this takes 1-3 minutes)..."):
            try:
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

                with st.chat_message("assistant"):
                    st.video(vid_url)
                st.session_state.messages.append({"role": "assistant", "type": "video", "content": vid_url})

                st.session_state.last_generated_image = None
                st.rerun()
            except Exception as e:
                st.error(f"Video error: {e}")

# ---------------------------------------------------------------
# PHOTO EDITING
# ---------------------------------------------------------------
st.write("---")
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
                edit_handler = fal_client.submit(
                    "fal-ai/nano-banana-2/edit",
                    arguments={
                        "prompt": edit_prompt,
