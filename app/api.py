from fastapi import APIRouter, Query, Form, Body, Header, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import base64

from app.stock.date import TradingDate
from app.hu.ollama import ollama_client
from app.lofig import Config, logger


router = APIRouter(prefix="/api", tags=["api"])


@router.get("/tradingdates")
def get_trading_dates(
    len: int = Query(30, description="获取天数", gt=0),
) -> List[str]:
    """
    获取交易日历
    
    GET /api/tradingdates?len=30
    
    - len: 获取的天数
    - 返回: 日期数组 ["2026-02-20", "2026-02-21", ...]
    """
    return TradingDate.recent_trading_dates(len)


def _recognize_captcha(img: str) -> str:
    """识别验证码图片"""
    if img is None:
        raise HTTPException(status_code=400, detail="No img specified.")
    
    # 处理图片格式
    if img.startswith('http'):
        import requests
        img_data = requests.get(img).content
    elif ',' in img:
        img_data = base64.b64decode(img.split(',')[1])
    else:
        # 已经是 base64 字符串
        try:
            img_data = base64.b64decode(img)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image data.")
    
    # 使用 ollama 识别
    ollama_instance = ollama_client(
        api_key=Config.client_config().get('ollama_api_key', None),
        model=Config.client_config().get('ollama_model', 'qwen2.5vl:7b')
    )
    
    img_b64 = base64.b64encode(img_data).decode('utf-8')
    result = ollama_instance.img_to_text(img_b64)
    
    if result is None:
        raise HTTPException(status_code=500, detail="Image recognition failed.")
    
    return result


@router.get("/captcha")
def get_captcha(
    img: str = Query(..., description="图片URL或base64字符串"),
) -> str:
    """
    识别验证码图片 (GET)
    
    GET /api/captcha?img={url_or_base64}
    
    - img: 图片URL或base64编码的字符串
    - 返回: 识别到的验证码字符
    """
    return _recognize_captcha(img)


@router.post("/captcha")
def post_captcha(
    img: str = Form(..., description="base64 编码的验证码图片"),
) -> str:
    """
    识别验证码图片 (POST)
    
    POST /api/captcha
    Content-Type: application/x-www-form-urlencoded
    
    - img: base64 编码的验证码图片
    - 返回: 识别到的验证码字符
    """
    return _recognize_captcha(img)
