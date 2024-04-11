import json
import os
import jwt
from pydub import AudioSegment
import requests


BLOG_PROMPT_STR ="""
You are asked to act as a good writer, you like to write Blog, you not only have literary attainments, but you are also like Einstein, Feynman, Hawking and other physicists like scientific insight. Your task is to write a good Blog article based on the content given by the user, and the style of the final output: simple and calm language, no exaggeration, but also a trace of humor and wisdom, and the output language is consistent with the user's input language.
"""

SUMMARY_PROMPT_STR ="""
Personas and Objectives: This GPT is designed to summarize video or audio text content, ensuring that the abstract is at least one-third the length of the original manuscript. It combines a global overview and a list format to highlight key points.

Constraint: The abstract should not be overly simplistic and should accurately capture the essence of the video content. It should match the language of the original video text, if it is Chinese, please use Chinese Simplified.

Guidelines: GPT will use simple, engaging natural language to make summaries accessible and understandable to the public.

Clarification: If the desired length of the video content or summary is unclear, GPT should ask for clarification.

Personalization: GPT should present information in a simple, friendly way that ensures the summary is engaging and easy to understand.
"""

def check_apptoken_from_apikey(apikey: str):
    if not apikey:
        return None
    apisecret = os.environ.get('APP_SECRET')
    if apikey:
        try:
            payload = jwt.decode(apikey, apisecret, algorithms=['HS256'])
            uid = payload.get('uid')
            if uid :
                return uid
        except Exception as e:
            return None
    return None

def get_global_datadir(subpath: str = None):
    """
    获取全局数据目录。

    Args:
        subpath (str, optional): 子路径。默认为None。

    Returns:
        str: 数据目录路径。
    """
    datadir = os.environ.get("DATA_DIR", "/tmp/teamsgpt")
    if subpath:
        datadir = os.path.join(datadir, subpath)
    if not os.path.exists(datadir):
        os.makedirs(datadir)
    return datadir


def audio_segment_split(audio_segment_src: AudioSegment, split_second: int):
    """
    将音频片段分割成指定时长的小片段。

    Args:
        audio_segment_src (AudioSegment): 要分割的音频片段。
        split_second (int): 每个分割片段的时长，以秒为单位。

    Returns:
        list: 分割后的音频片段列表。
    """

    split_list = []
    duration = len(audio_segment_src)
    start_time = 0
    end_time = split_second * 1000

    while end_time <= duration:
        split_list.append(audio_segment_src[start_time:end_time])
        start_time = end_time
        end_time += split_second * 1000

    if start_time < duration:
        split_list.append(audio_segment_src[start_time:])

    return split_list


def openai_text_generate(sysmsg: str, prompt: str, apikey: str):
    url = os.getenv("TEAMSGPT_APISITE", "https://api.teamsgpt.net") + "/api/generate"
    # Prepare headers and data
    headers = {'Content-Type': 'application/json', "Authorization": f"Bearer {apikey}"}
    data = json.dumps({
        "sysmsg": sysmsg,
        "prompt": prompt,
        "temperature": 0.7,  # Adjust this as needed
    })
    
    with requests.post(url, data=data, headers=headers, stream=True) as response:
        if response.status_code == 200:
            for line in response.iter_lines():
                decoded_line = line.decode('utf-8')               
                if decoded_line.startswith('data:'):
                    try:
                        json_str = decoded_line[len('data: '):]
                        if json_str:  
                            yield json.loads(json_str)
                        else:
                            pass
                    except json.JSONDecodeError as e:
                        print(f"JSON decoding failed: {e}")
                elif "data: [DONE]" in decoded_line:
                    break
        else:
            raise Exception(f"Error: {response.status_code} {response.reason}")

def generate_openai_transcribe(filename: str, language: str = "en", format: str = "text", apikey: str= None) -> str:
    url = os.getenv("TEAMSGPT_APISITE", "https://api.teamsgpt.net") + "/api/speech2text"
    headers = {"Authorization": f"Bearer {apikey}"}
    with open(filename, 'rb') as f:
        files = {'file': (os.path.basename(filename), f)}
        data = {'language': language, 'format': format}
        
        response = requests.post(url, files=files, data=data, headers=headers)
        
        if response.status_code == 200:
            json_response = response.json()
            return json_response["data"]
        else:
            raise Exception(f"Error: {response.status_code} {response.reason}")


def write_stream_text(placeholder, response):
    """写入流式响应。"""
    full_response = ""
    for tobj in response:
        text = tobj.get("content")
        if text is not None:
            full_response += text
            placeholder.markdown(full_response)
        placeholder.markdown(full_response)
    return full_response