import csv
import os
import json
import re
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from traceback import format_exc
from concurrent.futures import ThreadPoolExecutor

import requests
import stockrt as srt
from app.lofig import Config, logger
from app.stock import zdf_from_code, zt_priceby
from app.stock.date import TradingDate


class KNode(BaseModel):
    time: str
    open: float
    close: float
    high: float
    low: float
    volume: Optional[float] = 0
    amount: Optional[float] = 0
    change: Optional[float] = 0
    change_px: Optional[float] = 0
    amplitude: Optional[float] = 0
    turnover: Optional[float] = 0


class Network:
    @property
    def session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(self.headers)
        return session

    @property
    def headers(self) -> dict:
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:138.0) Gecko/20100101 Firefox/138.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }


network = Network()

class EmRequest():
    def __init__(self) -> None:
        self.headers = network.headers.copy()

    def getRequest(self, headers=None):
        rsp = network.session.get(self.getUrl(), headers=headers)
        rsp.raise_for_status()
        return rsp.text

    def getUrl(self):
        pass

    def getNext(self, headers=None):
        pass

    def saveFetched(self):
        pass


class StockZtInfo10jqka(EmRequest):
    '''涨停
    ref: http://data.10jqka.com.cn/datacenterph/limitup/limtupInfo.html
    '''
    def __init__(self) -> None:
        super().__init__()
        self.date = None
        self.pageSize = 15
        self.headers['Referer'] = 'http://data.10jqka.com.cn/datacenterph/limitup/limtupInfo.html'
        self.headers['Host'] = 'data.10jqka.com.cn'
        self.headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'

    def getUrl(self):
        if self.date is None:
            self.date = TradingDate.today()
        url = f'http://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool?page={self.page}&limit={self.pageSize}&field=199112,330329,9001,330325,9002,133971,133970,1968584&filter=HS,GEM2STAR,ST&order_field=199112&order_type=0&date={self.date.replace("-", "")}'
        return url

    def getNext(self, date=None):
        self.date = date
        self.page = 1
        ztdata = []
        while True:
            jqkback = json.loads(self.getRequest(self.headers))
            if jqkback is None or jqkback['status_code'] != 0 or jqkback['data'] is None:
                logger.info('StockZtInfo invalid response! %s', jqkback)
                return

            rdate = jqkback['data']['date']
            rdate = rdate[0:4] + '-' + rdate[4:6] + '-' + rdate[6:8]
            for ztobj in jqkback['data']['info']:
                mt = ztobj['market_type']
                code = ztobj['code']
                code = srt.get_fullcode(code) # code
                hsl = ztobj['turnover_rate'] / 100 # 换手率 %
                fund = ztobj['order_amount'] # 封单金额
                zbc = 0 if ztobj['open_num'] is None else ztobj['open_num'] # 炸板次数
                lbc = 1 if ztobj['high_days'] is None or ztobj['high_days'] == '首板' else int(re.findall(r'\d+', ztobj['high_days'])[-1])
                days = 1 if ztobj['high_days'] is None or ztobj['high_days'] == '首板' else int(re.findall(r'\d+', ztobj['high_days'])[0])
                zdf = ztobj['change_rate']
                cpt = ztobj['reason_type'] # 涨停原因

                rzdf = round(zdf)
                mkt = 0
                if rzdf == 30:
                    mkt = 2
                elif rzdf == 20:
                    mkt = 1
                elif rzdf == 5:
                    mkt = 3
                ztdata.append([code, rdate, fund, hsl, lbc, days, zbc, '', cpt, mkt])
            # fields:
            # 199112(change_rate涨跌幅),330329(high_days几天几板),9001(reason_type涨停原因),330325(limit_up_type涨停形态),
            # 9002(open_num开板次数),133971(order_volume封单量),133970(order_amount封单额),1968584(turnover_rate换手率),
            # 330323(first_limit_up_time首次涨停时间),330324(last_limit_up_time最后涨停时间),3475914(currency_value流通市值),
            # 10(latest最新价),9003(limit_up_suc_rate近一年涨停封板率),9004(time_preview)

            if jqkback['data']['page']['count'] == jqkback['data']['page']['page']:
                break
            self.page += 1

        return ztdata


class StockZtInfo(EmRequest):
    '''涨停
    ref: http://quote.eastmoney.com/ztb/detail#type=ztgc
    '''
    def __init__(self) -> None:
        super().__init__()
        self.urlroot = f'http://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989&sort=fbt%3Aasc&Pageindex=0&dpt=wz.ztzt&date='
        self.date = None

    def getUrl(self):
        if self.date is None:
            self.date = TradingDate.max_trading_date()
        return self.urlroot + self.date.replace('-', '')

    def getNext(self, date=None):
        self.date = date

        self.headers['Referer'] = f'http://quote.eastmoney.com/ztb/detail'
        self.headers['Host'] = 'push2ex.eastmoney.com'
        emback = json.loads(self.getRequest(self.headers))
        if emback is None or emback['data'] is None:
            logger.info('StockZtInfo invalid response! %s', emback)
            return []

        qdate = f"{emback['data']['qdate']}"
        if 'qdate' in emback['data'] and qdate != self.date.replace('-', ''):
            self.date = qdate[0:4] + '-' + qdate[4:6] + '-' + qdate[6:8]
            return []

        ztdata = []
        date = qdate[0:4] + '-' + qdate[4:6] + '-' + qdate[6:8]
        for ztobj in emback['data']['pool']:
            code = srt.get_fullcode(ztobj['c']) # code
            hsl = ztobj['hs']/100 # 换手率 %
            fund = ztobj['fund'] # 封单金额
            zbc = ztobj['zbc'] # 炸板次数
            lbc = ztobj['lbc']
            zdf = ztobj['zdp']
            mkt = 0
            if code.startswith('bj'):
                mkt = 2
            elif round(zdf) == 5:
                mkt = 3
            elif round(zdf) == 20:
                mkt = 1
            zdf = zdf / 100.0
            hybk = ztobj['hybk'] # 行业板块
            days = ztobj['zttj']['days']
            # other sections: c->code, n->name, m->market(0=SZ,1=SH), p->涨停价*1000, zdp->涨跌幅,
            # amount->成交额, ltsz->流通市值, tshare->总市值, lbc->连板次数, fbt->首次封板时间, lbt->最后封板时间
            # zttj->涨停统计 {days->天数, ct->涨停次数}
            ztdata.append([code, date, fund, hsl, lbc, days, zbc, hybk, '', mkt])

        return ztdata


class StockSelectorBase:
    """股票选择器基类，定义接口和通用方法"""

    def __init__(self, max_workers: int = 2) -> None:
        self.max_workers = max_workers
        self.wkstocks = []
        self.wkselected = []
        self.column_names = None
        self.save_file = 'selector_output.csv'

    @property
    def full_path(self):
        return os.path.join(os.path.realpath(Config.data_dir()), self.save_file)

    def max_date(self):
        if os.path.isfile(self.full_path):
            with open(self.full_path, 'r') as f:
                reader = csv.DictReader(f)
                col = 'time' if 'time' in reader.fieldnames else 'date'
                dates = [row[col] for row in reader if col in row]
                if dates:
                    return max(dates)
        return ''

    def query_values(self, fields, *conditions):
        """查询数据库，子类需要实现"""
        if not os.path.isfile(self.full_path):
            return []
        with open(self.full_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            results = []
            for row in reader:
                if all(cond(row) for cond in conditions):
                    results.append([row[field] for field in fields] if fields else list(row.values()))
            return results

    def delete_records(self, conditions):
        """删除记录，子类需要实现"""
        with open(self.full_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            records = [row for row in reader if not all(cond(row) for cond in conditions)]

        with open(self.full_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.column_names)
            writer.writeheader()
            writer.writerows(records)

    def upsert_one(self, record, unique_fields):
        """插入或更新一条记录，子类需要实现"""
        records = []
        updated = False
        if os.path.isfile(self.full_path):
            with open(self.full_path, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if all(row[field] == record[field] for field in unique_fields):
                        row.update(record)
                        records.append(row)
                        updated = True
                    else:
                        records.append(row)

        if not updated:
            records.append(record)

        with open(self.full_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.column_names)
            writer.writeheader()
            writer.writerows(records)

    def dumpDataByDate(self, date: Optional[str] = None):
        """根据日期获取数据，子类需要实现"""
        raise NotImplementedError("Subclasses must implement dumpDataByDate()")

    def task_prepare(self, date: Optional[str] = None) -> None:
        """准备任务"""
        self.wkstocks = []
        self.wkselected = []

    def post_process(self, update=False) -> None:
        """后处理"""
        if len(self.wkselected) == 0:
            return

        if update and os.path.isfile(self.full_path):
            # 读取现有数据
            existing_data = {}
            with open(self.full_path, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 使用 code+date 或 code+time 作为唯一键
                    key_parts = []
                    if 'code' in row:
                        key_parts.append(row['code'])
                    if 'time' in row:
                        key_parts.append(row['time'])
                    elif 'date' in row:
                        key_parts.append(row['date'])
                    key = '_'.join(key_parts)
                    existing_data[key] = row

            # 更新或添加新数据
            for row_data in self.wkselected:
                row_dict = dict(zip(self.column_names, row_data))
                key_parts = []
                if 'code' in row_dict:
                    key_parts.append(row_dict['code'])
                if 'time' in row_dict:
                    key_parts.append(row_dict['time'])
                elif 'date' in row_dict:
                    key_parts.append(row_dict['date'])
                key = '_'.join(key_parts)
                existing_data[key] = row_dict

            # 写入合并后的数据
            with open(self.full_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.column_names)
                writer.writeheader()
                for row in existing_data.values():
                    writer.writerow(row)
        else:
            # 追加写入新数据
            file_exists = os.path.isfile(self.full_path)
            mode = 'a' if file_exists else 'w'
            with open(self.full_path, mode, newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.column_names)
                if not file_exists:
                    writer.writeheader()
                for row_data in self.wkselected:
                    # row_data 是列表，按 column_names 顺序映射
                    row_dict = dict(zip(self.column_names, row_data))
                    writer.writerow(row_dict)

    def task_processing(self, item) -> None:
        """任务处理逻辑"""
        pass

    def start_multi_task(self, date: Optional[str] = None) -> None:
        """
        启动多线程任务

        Args:
            date: 可选日期参数
        """
        # 准备阶段
        self.task_prepare(date)

        ctime = datetime.now()

        if self.max_workers <= 1:
            for item in self.wkstocks:
                self.task_processing(item)
        else:
            def safe_task_processing(item):
                try:
                    self.task_processing(item)
                except Exception:
                    logger.error('error in task_processing %s', format_exc())

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                executor.map(safe_task_processing, self.wkstocks)

        # 记录执行时间
        elapsed = datetime.now() - ctime
        logger.info(f'多线程任务完成，工作线程数: {self.max_workers}，耗时: {elapsed}')

        # 后处理
        self.post_process()

    def update_pickups(self):
        mdate = self.max_date()
        if mdate == TradingDate.max_trading_date():
            logger.info('%s update_pickups already updated to latest!', self.__class__.__name__)
            return
        self.start_multi_task(mdate)

    def get_kd_data(self, code:str, start:str, fqt:int=0):
        if not TradingDate.is_trading_date(start):
            start = TradingDate.next_trading_date(start)
        length = TradingDate.calc_trading_days(start, TradingDate.today())
        ofmt = srt.set_array_format('json')
        kd = srt.klines(code, 'd', length=length, fq=fqt)
        srt.set_array_format(ofmt)
        kd = kd[code] if code in kd else None
        if kd is None or len(kd) == 0:
            return None
        def safe_get(record, field_name, default=0.0):
            val = record.get(field_name, default)
            return type(default)(val)
        def get_date(record):
            dtime = record[0] if isinstance(record, list) else record.get('time', '')
            return dtime.split(' ')[0] if ' ' in dtime else dtime

        return [KNode(
            time=get_date(kl),
            open=safe_get(kl, 'open', 0.0),
            close=safe_get(kl, 'close', 0.0),
            high=safe_get(kl, 'high', 0.0),
            low=safe_get(kl, 'low', 0.0),
            volume=safe_get(kl, 'volume', 0.0),
            amount=safe_get(kl, 'amount', 0.0),
            amplitude=safe_get(kl, 'amplitude', 0.0),
            change=safe_get(kl, 'change', 0.0),
            change_px=safe_get(kl, 'change_px', 0.0),
            turnover=safe_get(kl, 'turnover', 0.0)
        ) for kl in kd]

    def check_lbc(self, allkl, zdf=10):
        lbc, fid, lid = 0, 0, 0
        mxlbc, mxfid, mxlid = 0, 0, 0
        for i in range(0, len(allkl)):
            if round(allkl[i].change, 2) >= zdf/100 and allkl[i].high == allkl[i].close:
                if lbc == 0:
                    fid = i
                lbc += 1
                lid = i
            if i - lid >= 3:
                if lbc >= mxlbc:
                    mxlbc = lbc
                    mxfid = fid
                    mxlid = lid
                lbc = 0
        if lbc >= mxlbc:
            mxlbc = lbc
            mxfid = fid
            mxlid = lid
        return mxlbc, allkl[mxfid].time, allkl[mxlid].time


class StockZtDaily(StockSelectorBase):
    def __init__(self):
        super().__init__(5)
        self.save_file = 'day_zt_stocks.csv'
        self.column_names = ['code', 'time', 'fund', 'hsl', 'lbc', 'days', 'zbc', 'bk', 'cpt', 'mkt']

    @property
    def ztinfo(self):
        return StockZtInfo()

    @property
    def jqkinfo(self):
        return StockZtInfo10jqka()

    def is_st_stock(self, code):
        if hasattr(self, 'ststocoks'):
            return code in self.ststocoks
        return False

    def task_prepare(self, date: Optional[str] = None):
        onlycalc = date is None
        if date is None:
            super().task_prepare(date)
        else:
            if date == '':
                date = TradingDate.max_trading_date()
            else:
                date = TradingDate.next_trading_date(date)
            self.wkstocks = []
            self.wkselected = []

        while not onlycalc:
            ztdata = self.ztinfo.getNext(date)
            jqkztdata = self.jqkinfo.getNext(date)
            for ztobj in jqkztdata:
                zdata = next((t for t in ztdata if t[0] == ztobj[0] and t[1] == ztobj[1]), None)
                if zdata:
                    zdata[-2] = ztobj[-2]
                else:
                    ztdata.append(ztobj)
            self.ststocoks = [t[0] for t in ztdata if t[9] == 3]
            self.wkselected.extend(ztdata)
            for zobj in ztdata:
                self.wkstocks.append([zobj[0], date, self.last_zt_date(zobj[0])])
            if date == TradingDate.max_trading_date():
                break
            date = TradingDate.next_trading_date(date)

    def last_zt_date(self, code):
        if not os.path.isfile(self.full_path):
            return ''
        with open(self.full_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            cval = [row['time'] for row in reader if row['code'] == code and row['lbc'] == 1]
            return cval[-1] if cval else ''

    def _last_col_of(self, code, col):
        if not os.path.isfile(self.full_path):
            return ''
        with open(self.full_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            cval = [row[col] for row in reader if 'code' in row and row['code'] == code and col in row and row[col] != '']
            return cval[-1] if cval else ''

    def get_bk(self, code):
        return self._last_col_of(code, 'bk')

    def get_concept(self, code):
        return self._last_col_of(code, 'cpt')

    def merge_selected(self, sel):
        osel = next((s for s in self.wkselected if s[0] == sel[0] and s[1] == sel[1]), None)
        if not osel:
            sel[7] = self.get_bk(sel[0])
            sel[8] = self.get_concept(sel[0])
            self.wkselected.append(sel)
            return
        if osel[7] == '':
            osel[7] = self.get_bk(sel[0])
        if osel[8] == '':
            osel[8] = self.get_concept(sel[0])
        if osel[4] != sel[4]:
            osel[4] = sel[4]
        if osel[5] != sel[5]:
            osel[5] = sel[5]
        if osel[4] == 1 and osel[5] > 1:
            logger.error(f'error lbc and days: {osel}')

    def task_processing(self, item):
        c, zdate, sdate = item
        if sdate == '':
            sdate = TradingDate.prev_trading_date(zdate, 50)
        allkl = self.get_kd_data(c, start=sdate)
        if allkl is None or len(allkl) == 0:
            return

        zdf = zdf_from_code(c)
        if zdf == 10 and self.is_st_stock(c):
            zdf = 5

        i = 0
        while i < len(allkl):
            if allkl[i].time < zdate:
                i += 1
                continue
            if i == 0 and allkl[i].close == allkl[i].high and allkl[i].change * 100 >= zdf - 0.1:
                self.merge_selected([c, allkl[i].time, 0, 0, 1, 1, 0, "", ""])
                i += 1
                continue

            c0 = allkl[i-1].close
            zt_prc = zt_priceby(c0, zdf=zdf)
            if allkl[i].close == allkl[i].high and (allkl[i].close >= zt_prc or c0 + allkl[i].change_px >= zt_prc):
                while True:
                    lbc, fdate, ldate = self.check_lbc(allkl, zdf=zdf)
                    if TradingDate.calc_trading_days(ldate, zdate) > 4:
                        allkl = [d for d in allkl if d.time > ldate]
                        continue
                    break
                days = len([d for d in allkl if d.time >= fdate and d.time <= ldate])
                if lbc == 1 and days != 1:
                    logger.warning(f'consider wrong lbc: {lbc}, {days}, {item}')
                    days = 1
                self.merge_selected([c, ldate, 0, 0, lbc, days, 0, "", ""])
            i += 1

    def dump_main_stocks_zt0(self, date):
        if date is None or date == '':
            date = self.max_date()

        return self.query_values(['code', 'bk', 'cpt'], lambda row: row['time'] == date and row['lbc'] == '1' and row['days'] == '1' and row['mkt'] == '0')

    def dumpDataByDate(self, date: Optional[str] = None):
        if date is None or date == '':
            date = self.max_date()

        return self.query_values([], lambda row: row['time'] == date)


class StockZt1WbSelector(StockSelectorBase):
    def __init__(self):
        super().__init__(5)
        self.save_file = 'stock_zt1wb_pickup.csv'
        self.column_names = ['code', 'date']

    def task_prepare(self, date: Optional[str] = None) -> None:
        """准备任务"""
        szi = StockZtDaily()
        if date is None or date == '':
            date = self.max_date()
        else:
            date = TradingDate.next_trading_date(date)
        zt = szi.dump_main_stocks_zt0(date)
        self.wkstocks = [c for c, *_ in zt]
        self.wkdate = szi.max_date() if date is None or date == '' else date

    def start_multi_task(self, date = None):
        self.task_prepare(date)
        if len(self.wkstocks) == 0:
            return

        tlines = srt.tlines(self.wkstocks)
        picked = []
        for c, tls in tlines.items():
            high = max([tl[1] if isinstance(tl, (list, tuple)) else tl.get('price', 0) for tl in tls])
            firstidx = next((idx for idx, tl in enumerate(tls) if tl[1] == high), None)
            countless = len([tl for tl in tls[firstidx + 1:] if tl[1] < high])
            if firstidx > 215 or countless > 5:
                picked.append(c)

        if len(picked) == 0:
            return
        self.wkselected = [[c, self.wkdate] for c in picked]
        self.post_process(update=True)

    def dumpDataByDate(self, date: Optional[str] = None):
        if date is None or date == '':
            date = self.max_date()

        return self.query_values(['code', 'date'], lambda row: row['date'] == date)


class StockHotStocksRetryZt0Selector(StockSelectorBase):
    def __init__(self):
        super().__init__(1)
        self.save_file = 'stock_day_hotstks_retry_zt0.csv'
        self.column_names = ['date', 'code', 'days', 'step', 'remdays', 'dropdate']

    def task_prepare(self, date=None):
        self.wkselected = []
        szd = StockZtDaily()
        hsos = szd.dumpDataByDate(date)
        ssel = {}
        for c,zd,_f,_h,step,days,*_ in hsos:
            if int(step) < 4:
                continue
            if c not in ssel:
                ssel[c] = [(zd,days,step)]
                continue
            ld,ldays,lstep = ssel[c][-1]
            if ld == zd:
                continue
            if TradingDate.calc_trading_days(ld, zd) > 4:
                ssel[c].append((zd,days,step))
                continue
            ssel[c][-1] = (zd,days,step)

        self.wkstocks = []
        if date is None:
            for c in ssel:
                for zd,days,step in ssel[c]:
                    self.wkstocks.append((c,zd,days,step,66))
        else:
            orecs = self.query_values(['date', 'code', 'days', 'step', 'remdays'], lambda row: int(row['remdays']) > 0)
            for d,c,days,step,rd in orecs:
                if c in ssel:
                    del ssel[c]
                days = int(days)
                step = int(step)
                allkl = self.get_kd_data(c, TradingDate.prev_trading_date(d, days*2), fqt=1)
                lbc, fdate, ldate = self.check_lbc(allkl)
                if lbc >= step and ldate != d and fdate < d:
                    days = len([d for x in allkl if x.time >= fdate and x.time <= ldate])
                    self.delete_records([lambda row: row['code'] == c and row['date'] == d])
                    self.upsert_one({'code': c, 'date': ldate, 'days': days, 'step': lbc, 'remdays': 66}, ['code', 'date'])
                    self.wkstocks.append((c,ldate,days,lbc,66))
                    continue
                if lbc >= 3 and ldate != d:
                    self.upsert_one({'code': c, 'date': d, 'remdays': 0, 'dropdate': fdate}, ['code', 'date'])
                    days = len([d for x in allkl if x.time >= fdate and x.time <= ldate])
                    self.wkstocks.append((c,ldate,days,lbc,66))
                    logger.info(f'lbc >= 3, drop old record and add new record {c} {lbc} {fdate} {ldate}')
                    continue
                self.wkstocks.append((c,d,days,step,rd))
            for c in ssel:
                for zd,days,step in ssel[c]:
                    self.wkstocks.append((c,zd,days,step, 66))
        self.wkstocks = sorted(self.wkstocks, key=lambda x: (x[0], x[1]))

    def task_processing(self, item):
        c,d,days,step,rdays = item
        days = int(days)
        step = int(step)
        allkl = self.get_kd_data(c, TradingDate.prev_trading_date(d, days), fqt=1)
        post_days = len([x for x in allkl if x.time > d])
        if post_days < 66:
            self.wkselected.append([d,c,days,step,66-post_days,''])
            return
        i = 0
        while i < len(allkl) and allkl[i].time < d:
            i += 1
        if not any([round(x.change, 2) >= 0.1 and x.high == x.close for x in allkl if x.time > d and allkl.index(x) - i < 66]):
            self.wkselected.append([d,c,days,step,0,allkl[i+66].time])
            return
        last_zid = i + 66
        while last_zid > i:
            if round(allkl[last_zid].change, 2) >= 0.1 and allkl[last_zid].high == allkl[last_zid].close:
                break
            last_zid -= 1
        fianal_zid = max(last_zid + 22, i + 66)
        while fianal_zid < len(allkl):
            while fianal_zid > last_zid:
                if round(allkl[fianal_zid].change, 2) >= 0.1 and allkl[fianal_zid].high == allkl[fianal_zid].close:
                    break
                fianal_zid -= 1
            if fianal_zid > last_zid:
                last_zid = fianal_zid
                fianal_zid += 22
            else:
                break
        fianal_zid = max(fianal_zid, i + 66)
        if fianal_zid >= len(allkl):
            self.wkselected.append([d,c,days,step,fianal_zid - len(allkl) + 1, ''])
        else:
            self.wkselected.append([d,c,days,step,0,allkl[fianal_zid].time])

    def post_process(self, update=False):
        return super().post_process(True)

    def dumpDataByDate(self, date=None):
        if date is None or date == '':
            date = self.max_date()
            if date is None:
                return []
        ldate = TradingDate.prev_trading_date(date, 2)
        return self.query_values(['date', 'code', 'days', 'step'], lambda row: row['date'] < ldate and int(row['remdays']) > 0)


class SelectorsFactory:
    @staticmethod
    def get(selector_name: str):
        selectors = {
            'StockZtDaily': StockZtDaily,
            'StockZt1WbSelector': StockZt1WbSelector,
            'StockHotStocksRetryZt0Selector': StockHotStocksRetryZt0Selector,
            # 'StockDtMap': StockDtMap,
            # 'StockDt3Selector': StockDt3Selector,
            # 'StockZdtEmotion': StockZdtEmotion,
            # 'StockHotStocksOpenSelector': StockHotStocksOpenSelector,
            # 'StockZtLeadingSelector': StockZtLeadingSelector,
            # 'StockTrippleBullSelector': StockTrippleBullSelector,
        }
        selector_class = selectors.get(selector_name)
        if selector_class:
            return selector_class()
        else:
            raise ValueError(f"Selector '{selector_name}' not found.")
