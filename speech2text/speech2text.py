import uuid
import streamlit as st
from st_audiorec import st_audiorec
from pydub import AudioSegment
from .session import PageSessionState
from .common import get_global_datadir
from .common import audio_segment_split, generate_openai_transcribe
from .common import openai_text_generate
from .common import write_stream_text
from .common import BLOG_PROMPT_STR, SUMMARY_PROMPT_STR
from hashlib import md5
import io
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="语音创作", page_icon="✨")

st.sidebar.title("🔊 语音创作 ✨")

def main():
    with st.sidebar:
        tab1, tab2 = st.tabs(["参数设置",  "关于"])
        with tab1:
            param_box = st.container()

        with tab2:
            st.caption("基于语音的 AI 创作，让 AI 为你的创作提供灵感和帮助。")


    page_state = PageSessionState("speech")

    # 用于存储临时文件
    audio_tempdir = get_global_datadir("temp_audio")

    page_state.initn_attr("input_type", "microphone")
    page_state.initn_attr("audio_text_source", None)
    page_state.initn_attr("recode_text", None)
    page_state.initn_attr("latest_blog_file", None)
    page_state.initn_attr("latest_summary_file", None)
    page_state.initn_attr("latest_custom_file", None)

    st.markdown(
        """
        <style>
        /* Target code blocks */
        .stCodeBlock > div {
            white-space: pre-wrap !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


    @st.cache_data(persist="disk")
    def get_speech(filename, language: str = "en"):
        return generate_openai_transcribe(filename, language, format="text")


    def get_speech_text(audio_path):
        basename = os.path.basename(audio_path)
        audio_format = basename.split(".")[-1]
        audio_segment = AudioSegment.from_file(audio_path, format=audio_format)
        segs = audio_segment_split(audio_segment, 120)
        page_state.recode_text = ""
        for seg in segs:
            md5hash = md5(seg.raw_data).hexdigest()
            seg_audio_path = os.path.join(audio_tempdir, md5hash + ".mp3")
            seg.export(seg_audio_path, format="mp3")
            text = get_speech(seg_audio_path, language)
            page_state.recode_text += "\n" + text
        return page_state.recode_text


    language = param_box.selectbox("选择源语言", ["zh", "en"], index=0)
    output_type = param_box.selectbox("输出类型", ["summary", "blog", "custom"], index=0)
    if output_type == "custom":
        custom_prompt = param_box.text_area(
            "自定义 Prompt", 
            "对输入的语音识别文本内容进行处理， 纠正错误，添加标点符号， 合理分段，使其更加通顺易读。", height=140,
        )

    wav_audio_recode = None
    audio_path = None


    tab1, tab2 = st.tabs(["录制语音", "上传音频"])

    with tab1:
        wav_audio_recode = st_audiorec()
        if st.button("识别语音", key="do_recode"):
            if wav_audio_recode is not None:
                status = st.status("正在识别录制语音....", state="running", expanded=True)
                with status:
                    status.update(label="正在保存语音....")
                    _filename = md5(wav_audio_recode[:100]).hexdigest()
                    # _filename = uuid.uuid4().hex
                    audio_segment = AudioSegment.from_wav(io.BytesIO(wav_audio_recode))
                    audio_path = os.path.join(audio_tempdir, f"{_filename}.audio.wav")
                    audio_segment.export(audio_path, format="wav")
                    status.update(label="已保存语音， 正在识别....")
                    result = get_speech_text(audio_path)
                    status.update(label="识别完成", state="complete")
            else:
                st.warning("没有录制到语音")

    with tab2:
        uploaded_file = st.file_uploader(
            "上传音频文件", type=["wav", "mp3", "mp4", "ogg", "m4a"]
        )
        if uploaded_file:
            audio_path = os.path.join(audio_tempdir, os.path.basename(uploaded_file.name))
            with open(audio_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            st.audio(audio_path)

        if audio_path and st.button("识别语音", key="do_uploadfile"):
            with st.spinner("正在识别上传语音...."):
                result = get_speech_text(audio_path)


    st.divider()

    if page_state.recode_text:
        st.code(page_state.recode_text)
        create_action = st.button("创建内容", type="primary",)
        placeholder = st.empty()
        if create_action:
            if output_type == "summary":
                with st.spinner("正在创建摘要...."):
                    response = openai_text_generate(
                        SUMMARY_PROMPT_STR, page_state.recode_text
                    )
                    placeholder = st.empty()
                    full_response = write_stream_text(placeholder, response)
                    page_state.latest_summary_file = os.path.join(
                        audio_tempdir, uuid.uuid4().hex + ".txt"
                    )
                    with open(page_state.latest_summary_file, "w") as f:
                        f.write(full_response)
            elif output_type == "blog":
                with st.spinner("正在创建 Blog...."):
                    response = openai_text_generate(
                        BLOG_PROMPT_STR, page_state.recode_text
                    )
                    placeholder = st.empty()
                    full_response = write_stream_text(placeholder, response)
                    page_state.latest_blog_file = os.path.join(
                        audio_tempdir, uuid.uuid4().hex + ".txt"
                    )
                    with open(page_state.latest_blog_file, "w") as f:
                        f.write(full_response)
            elif output_type == "custom":
                if custom_prompt:
                    with st.spinner("正在创建自定义内容...."):
                        response = openai_text_generate(
                            custom_prompt, page_state.recode_text
                        )
                        placeholder = st.empty()
                        full_response = write_stream_text(placeholder, response)
                        page_state.latest_custom_file = os.path.join(
                            audio_tempdir, uuid.uuid4().hex + ".txt"
                        )
                        with open(page_state.latest_custom_file, "w") as f:
                            f.write(full_response)
                else:
                    st.warning("自定义 Prompt 不能为空！")


    if page_state.recode_text:
        param_box.download_button(
            label=f"下载识别文本",
            data=page_state.recode_text,
            file_name=f"recode_{uuid.uuid4().hex}.md",
            mime="text/plain",
        )

    if page_state.latest_blog_file:
        param_box.download_button(
            label=f"下载 Blog 内容",
            data=open(page_state.latest_blog_file, "rb"),
            file_name=page_state.latest_blog_file,
            mime="text/plain",
        )

    if page_state.latest_custom_file:
        param_box.download_button(
            label=f"下载自定义内容",
            data=open(page_state.latest_custom_file, "rb"),
            file_name=page_state.latest_custom_file,
            mime="text/plain",
        )

    if page_state.latest_summary_file:
        param_box.download_button(
            label=f"下载内容摘要",
            data=open(page_state.latest_summary_file, "rb"),
            file_name=page_state.latest_summary_file,
            mime="text/plain",
        )


    if param_box.button("清除历史数据", type="secondary"):
        page_state.recode_text = None
        page_state.latest_blog_file = None
        page_state.latest_summary_file = None
        page_state.latest_custom_file = None
        st.rerun()
        