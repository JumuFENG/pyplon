from fastapi import APIRouter, Query, Form, Body, Header, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class WatchingsResponse(BaseModel):
    """关注股票列表响应"""
    pass


class UserBindResponse(BaseModel):
    """用户绑定响应"""
    pass


class TradingDatesResponse(BaseModel):
    """交易日历响应"""
    pass


class CaptchaResponse(BaseModel):
    """验证码识别响应"""
    pass


class DealsResponse(BaseModel):
    """成交记录响应"""
    pass



# ==================== pyiun (dataservice) 接口 ====================
# pyiun 通过 dataservice.server 配置，提供的接口用于:
# - 涨停天数查询
# - 竞价数据保存
# - 板块/股票数据查询
# - 资金流向查询
# - 财务数据查询

router = APIRouter(prefix="/stock", tags=["dataservice"])


# ==================== Response Models ====================

class ZdtInDaysResponse(BaseModel):
    """涨停天数查询响应"""
    pass


class BkIgnoredResponse(BaseModel):
    """忽略板块查询响应"""
    pass


class PlannedDividendResponse(BaseModel):
    """计划分红查询响应"""
    pass


class StockBksResponse(BaseModel):
    """股票所属板块响应"""
    pass


class BkStocksResponse(BaseModel):
    """板块成分股响应"""
    pass


class ZtStocksResponse(BaseModel):
    """近期涨停股票响应"""
    pass


class HotBksResponse(BaseModel):
    """热门板块响应"""
    pass


class HotStocksResponse(BaseModel):
    """热门股票响应"""
    pass


class ZdtEmotResponse(BaseModel):
    """涨停分布统计响应"""
    pass


class ZtStepsHistResponse(BaseModel):
    """涨停连板统计响应"""
    pass


class F4LostResponse(BaseModel):
    """财务异常股票响应"""
    pass


# ==================== Route Definitions ====================

@router.get("")
async def stock_query(
    act: str = Query(..., description="操作类型"),
    codes: Optional[str] = Query(None, description="股票代码列表，逗号分隔"),
    date: Optional[str] = Query(None, description="日期，格式如 2026-02-25"),
    stocks: Optional[str] = Query(None, description="股票代码"),
    bks: Optional[str] = Query(None, description="板块代码"),
    days: Optional[int] = Query(None, description="天数"),
    steps: Optional[int] = Query(None, description="连板次数"),
    save: Optional[int] = Query(None, description="是否保存"),
) -> Dict[str, Any]:
    """
    股票数据查询接口
    
    GET /stock?act={action}&...
    
    支持的操作 (act 参数):
    - zdtindays: 涨停天数查询
      - codes: 股票代码列表逗号分隔
      - date: 日期
    - bk_ignored: 忽略板块查询
    - planeddividen: 计划分红查询
      - date: 日期
    - stockbks: 股票所属板块
      - stocks: 股票代码
    - bkstocks: 板块成分股
      - bks: 板块代码
    - ztstocks: 近期涨停股票
      - days: 天数
    - hotbks: 热门板块
      - days: 天数
    - hotstocks: 热门股票
      - days: 天数
    - zdtemot: 涨停分布统计
      - days: 天数
    - ztstepshist: 涨停连板统计
      - days: 天数
      - steps: 连板次数
    - f4lost: 财务异常股票
    - rtbkchanges: 板块异动数据
      - save: 是否保存
    - watchings: 关注股票列表
    """
    pass


@router.get("/stock_fflow")
async def stock_fflow(
    code: str = Query(..., description="股票代码"),
    date: Optional[str] = Query(None, description="开始日期"),
) -> List[List[Any]]:
    """
    股票资金流向查询
    
    GET /stock_fflow?code={code}&date={date}
    
    - code: 股票代码
    - date: 开始日期 (可选)
    
    返回: 资金流向数据数组
    格式: [[日期, 主力, 小单, 中单, 大单, 超大单, 净流入, 占比...], ...]
    """
    pass


@router.post("")
async def stock_post(
    act: str = Form(...),
    date: Optional[str] = Form(None),
    acc: Optional[str] = Form(None),
    auctions: Optional[str] = Form(None),
    matched: Optional[str] = Form(None),
    data: Optional[str] = Form(None),
) -> Any:
    """
    股票数据提交接口
    
    POST /stock
    Content-Type: application/x-www-form-urlencoded
    - act: `deals`
        - acc: 账户名称
        - data: JSON 字符串化的成交记录数组

    支持的操作:
    - save_auction_details: 保存竞价详情
      - date: 日期
      - auctions: JSON 字符串化的竞价数据
    - save_auction_matched: 保存竞价匹配结果
      - matched: JSON 字符串化的匹配结果数组
    """
    pass
