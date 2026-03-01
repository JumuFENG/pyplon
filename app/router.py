import json
from fastapi import APIRouter, Query, Form, Body, Header, Depends
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel
from functools import lru_cache
import emxg
import stockrt as srt
from app.lofig import Config, logger
from app.users import UserManager as um
from app.stock.date import TradingDate
from app.stock.manager import StockManager as usm
from app.selector import SelectorsFactory as sfac


@lru_cache(maxsize=1)
def query_f4lost():
    pdata = emxg.search('连续4个季度亏损大于1000万元')
    pdata = pdata.rename(columns={'代码': 'code'})
    return [srt.get_fullcode(code[:6]) for code in pdata['code']]

def normalize_codes(codes: Union[str, List[str]]) -> List[str]:
    """标准化股票代码输入"""
    if isinstance(codes, str):
        return codes.split(',') if ',' in codes else [codes]
    return codes if isinstance(codes, list) else [str(codes)]


router = APIRouter(prefix="/stock", tags=["dataservice"])


@router.get("")
async def stock_query(
    act: str = Query(..., description="操作类型"),
    codes: Optional[str] = Query(None, description="股票代码列表，逗号分隔"),
    date: Optional[str] = Query(None, description="日期，格式如 2026-02-25"),
    stocks: Optional[str] = Query(None, description="股票代码"),
    accid: Optional[str] = Query(None, description="账户ID"),
    acc: Optional[str] = Query(None, description="账户名称"),
    key: Optional[str] = Query(None, description="策略关键字"),
    bks: Optional[str] = Query(None, description="板块代码"),
    days: Optional[int] = Query(None, description="天数"),
    steps: Optional[int] = Query(None, description="连板次数"),
) -> Any:
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
    if act == 'rtbkchanges':
        return []
    if act == "planeddividen":
        return []
    if act == 'f4lost':
        return query_f4lost()
    if act == 'getistr':
        if key == 'istrategy_zt1wb':
            wbtbl = sfac.get('StockZt1WbSelector')
            z1stks = wbtbl.dumpDataByDate()
            td = TradingDate.max_traded_date()
            return [x[1] for x in z1stks if x[0] == td]
        elif key == 'istrategy_hsrzt0':
            shs = sfac.get('StockHotStocksRetryZt0Selector')
            return shs.dumpDataByDate()
        else:
            logger.warning(f"Unknown strategy key: {key}")
            return []

    user = None
    if acc or accid:
        user = um.get_user_by(acc=acc, accid=accid)
    if act == 'watchings':
        return usm.get_watchings(user)
    if act == "deals":
        return usm.get_deals(user)
    return {}


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
    return []


@router.post("")
async def stock_post(
    act: str = Form(...),
    date: Optional[str] = Form(None),
    acc: Optional[str] = Form(None),
    accid: Optional[str] = Form(None),
    data: Optional[str] = Form(None),
    buysid: Optional[str] = Form(None),
    sellsid: Optional[str] = Form(None),
    code: Optional[str] = Form(None),
) -> Any:
    """
    股票数据提交接口

    POST /stock
    Content-Type: application/x-www-form-urlencoded
    - act: `deals`
        - acc: 账户名称
        - data: JSON 字符串化的成交记录数组
    - act: `strategy`
        - acc: 账户名称
        - code: 股票代码
        - data: JSON 字符串化的策略配置
    - act: 'save_auction_details':
        # deprecated
    - act: 'save_auction_matched':
        # deprecated
    """
    if code:
        code = code.lower()

    user = None
    if acc or accid:
        user = um.get_user_by(acc=acc, accid=accid)

    if act == 'deals':
        await usm.add_deals(user, data)
    elif act == 'fixdeals':
        await usm.fix_deals(user, data)
    elif act == 'forget':
        await usm.forget_stock(user, code)
    # elif act == 'costdog':
    #     usm.save_costdog(data)
    elif act == 'watch':
        usm.watch_stock(user, code)
    elif act == 'rmwatch':
        usm.forget_stock(user, code)
        bsid = buysid.split(',')
        ssid = sellsid.split(',')
        usm.remove_deals(user, code, bsid, ssid)
    elif act == 'strategy':
        if len(code) != 8:
            code = srt.get_fullcode(code)
        if data is None or len(data) == 0:
            usm.remove_strategy(user, code)
        else:
            usm.save_strategy(user, code, data)
    else:
        logger.warning(f"Unknown act: {act}")
    return {"status": "ok"}


@router.get("/quotes")
def stock_quotes(code: str = Query(..., min_length=6)):
    """
    获取股票报价数据

    GET /stock/quotes?code={code}

    - code: 股票代码，至少6位
    - 返回: 股票报价数据对象
    """
    codes = normalize_codes(code)
    return srt.quotes(codes)
