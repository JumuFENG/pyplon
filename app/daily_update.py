# Python 3
# -*- coding:utf-8 -*-

import sys
import os
import traceback
from datetime import datetime
sys.path.insert(0, os.path.realpath(os.path.dirname(__file__) + '/..'))
from app.lofig import Config, logging
from app.stock.date import TradingDate
from app.selector import SelectorsFactory as sfac

logger = logging.getLogger(f'{Config.app_name}.{__package__}')


class DailyUpdater():
    """for daily update"""
    @classmethod
    def update_all(cls):
        logger.info(f"START UPDATING....")
        datetoday = datetime.now()
        if TradingDate.is_holiday():
            logger.info(f"Today is holiday, no data to update.")
            return

        morningOnetime = False
        if datetoday.hour < 12:
            morningOnetime = True
            logger.info(f"update in the morning at {datetoday.hour}")

        if morningOnetime:
            # 只在早上执行的任务
            logger.info("update in the morning...")
        else:
            # 只在晚上执行的任务
            logger.info("update in the afternoon")
            # 涨跌停数据，可以间隔，早晚都合适
            cls.fetch_zdt_stocks()
            #
            cls.update_selectors()
        # 早上也执行的任务，以防前一晚上没执行
        cls.update_twice_selectors()

    @classmethod
    def fetch_zdt_stocks(cls):
        logger.info('update ST bk stocks')

        logger.info('update zt info')
        ztinfo = sfac.get('StockZtDaily')
        ztinfo.update_pickups()

        # logger.info('update zt concepts')
        # ztcpt = StockZtConcepts()
        # ztcpt.getNext()

        # logger.info('update dt info')
        # dtinfo = StockDtInfo()
        # dtinfo.getNext()

    @classmethod
    def update_selectors(cls):
        selectors = [
        'StockZt1WbSelector',
        # 'StockZtLeadingSelector',
        'StockHotStocksRetryZt0Selector',
        ]

        for s in selectors:
            sel = sfac.get(s)
            logger.info(f'update {s}')
            try:
                sel.update_pickups()
            except Exception as e:
                logger.info(e)
                logger.debug(traceback.format_exc())

    @classmethod
    def update_twice_selectors(cls):
        pass

    @classmethod
    def update_fixzdt(self):
        self.fetch_zdt_stocks()
        self.update_selectors()
        self.update_twice_selectors()

if __name__ == '__main__':
    DailyUpdater.update_all()
