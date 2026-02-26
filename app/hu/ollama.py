import os
import json
import requests
import base64
from functools import lru_cache
from app.lofig import logger


class Ollama:
    """Ollama API 客户端"""

    def __init__(self, api_key=None, model="qwen2.5vl:7b"):
        self.api_key = api_key
        self.model = model
        self.url = "https://ollama.com/api/chat"

    def chat(self, content, images=None):
        """
        向Ollama API发送聊天请求

        参数:
            content (str): 用户输入的内容（必填）
            images (list, optional): base64图片列表，默认为None
        返回:
            str: API响应内容
        """
        headers = {
            "Content-Type": "application/json"
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        message = {
            "role": "user",
            "content": content
        }

        if images:
            message["images"] = images

        data = {
            "model": self.model,
            "messages": [message],
            "stream": False
        }

        try:
            response = requests.post(self.url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            return result.get("message", {}).get("content", "")
        except requests.exceptions.RequestException as e:
            logger.error(f"请求错误: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
            return None

    def img_to_text(self, img):
        """识别图片中的文字"""
        if isinstance(img, str) and os.path.isfile(img):
            with open(img, 'rb') as f:
                img = base64.b64encode(f.read()).decode('utf-8')

        return self.chat('识别图片中的数字,直接告诉我结果', images=[img])


@lru_cache(maxsize=5)
def ollama_client(api_key=None, model="qwen2.5vl:7b") -> Ollama:
    """获取Ollama客户端单例"""
    return Ollama(api_key, model)
