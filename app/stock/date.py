import os
import json
import datetime
import requests
from functools import lru_cache
from bs4 import BeautifulSoup
from app.lofig import logger, Config


class TradingDate:
    """交易日历管理类"""

    @staticmethod
    def today(sep='-'):
        return datetime.datetime.now().strftime(f'%Y{sep}%m{sep}%d')

    @staticmethod
    @lru_cache(maxsize=1)
    def _holidays():
        """获取节假日列表"""
        holidayfile = Config.holiday_file()
        if os.path.isfile(holidayfile):
            try:
                with open(holidayfile, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load holidays: {e}")
        return []

    @staticmethod
    @lru_cache(maxsize=1)
    def max_trading_date():
        """获取最近一个交易日"""
        d = datetime.datetime.now().date()
        while TradingDate.is_holiday(d.strftime('%Y-%m-%d')):
            d -= datetime.timedelta(days=1)
        return d.strftime('%Y-%m-%d')

    @staticmethod
    def max_traded_date():
        today = TradingDate.today()
        if TradingDate.is_trading_date(today):
            return today if datetime.datetime.now().hour >= 15 else TradingDate.prev_trading_date(today)
        return TradingDate.max_trading_date()

    @staticmethod
    def is_holiday(date=None):
        """判断是否为节假日"""
        if not date:
            daynow = datetime.datetime.now()
            date = daynow.strftime('%Y-%m-%d')
            return date in TradingDate._holidays() or daynow.weekday() >= 5
        if date in TradingDate._holidays() or datetime.datetime.strptime(date, '%Y-%m-%d').weekday() >= 5:
            return True
        return False

    @staticmethod
    def is_trading_date(date):
        """判断是否为交易日"""
        if not date:
            return False
        return not TradingDate.is_holiday(date)

    @classmethod
    @lru_cache(maxsize=10)
    def prev_trading_date(cls, date, ndays=1):
        """
        获取指定日期前第N个交易日
        :param date: 基准日期
        :param ndays: 向前偏移的天数（默认1）
        :return: 前第N个交易日日期，如果不存在返回第一天
        """
        d = datetime.datetime.strptime(date, '%Y-%m-%d')
        while ndays > 0:
            d -= datetime.timedelta(days=1)
            if not cls.is_holiday(d.strftime('%Y-%m-%d')):
                ndays -= 1
        return d.strftime('%Y-%m-%d')

    @classmethod
    @lru_cache(maxsize=10)
    def next_trading_date(cls, date, ndays=1):
        """
        获取指定日期后第N个交易日
        :param date: 基准日期
        :param ndays: 向后偏移的天数（默认1）
        :return: 后第N个交易日日期，如果不存在返回最后一天
        """
        d = datetime.datetime.strptime(date, '%Y-%m-%d')
        while ndays > 0:
            d += datetime.timedelta(days=1)
            if not cls.is_holiday(d.strftime('%Y-%m-%d')):
                ndays -= 1
        return min(d.strftime('%Y-%m-%d'), cls.max_trading_date())

    @classmethod
    def recent_trading_dates(cls, n):
        """获取最近N个交易日列表"""
        dates = [cls.max_trading_date()]
        d = datetime.datetime.strptime(cls.max_trading_date(), '%Y-%m-%d')
        while len(dates) < n:
            d -= datetime.timedelta(days=1)
            date_str = d.strftime('%Y-%m-%d')
            if not cls.is_holiday(date_str):
                dates.append(date_str)
        dates.reverse()
        return dates

    @classmethod
    def calc_trading_days(cls, bdate, edate):
        """
        计算两个日期(含)之间的交易日数
        :param bdate: 起始日期
        :param edate: 结束日期
        :return: 交易日数
        """
        wkdays = 0
        if ' ' in bdate:
            bdate = bdate.split(' ')[0]
        if ' ' in edate:
            edate = edate.split(' ')[0]
        d = datetime.datetime.strptime(bdate, '%Y-%m-%d')
        while d <= datetime.datetime.strptime(edate, '%Y-%m-%d'):
            if cls.is_trading_date(d.strftime('%Y-%m-%d')):
                wkdays += 1
            d += datetime.timedelta(days=1)
        return wkdays

    @classmethod
    def update_holiday(cls):
        url = 'https://www.tdx.com.cn/url/holiday/'
        response = requests.get(url)
        response.raise_for_status()
        response.encoding = 'gbk'
        soup = BeautifulSoup(response.text, 'html.parser', from_encoding='gbk')
        txt_data = soup.select_one('textarea#data')
        txt = txt_data.get_text()
        holidays = txt.strip().splitlines()
        cn_holidays = []
        for hol in holidays:
            d, n, r, *_ = hol.split('|')
            d = d[:4] + '-' + d[4:6] + '-' + d[6:]
            if r == '中国':
                if d not in cls._holidays():
                    cn_holidays.append([d, n])
        if len(cn_holidays) > 0:
            holidays = cls._holidays()
            holidays.extend([h[0] for h in cn_holidays])
            with open(Config.holiday_file(), 'w') as f:
                return json.dump(holidays, f)
            cls._holidays.cache_clear()
        return cls._holidays()
