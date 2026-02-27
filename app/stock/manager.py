import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.lofig import Config, logger


class StockManager:
    """股票管理类 - 管理用户关注股票、成交记录和策略配置"""
    
    @staticmethod
    def _get_user_id(user) -> str:
        """获取用户ID"""
        if user is None:
            return "default"
        return str(user.get('id', 'default'))
    
    # ==================== 用户股票 (关注列表) ====================
    
    @staticmethod
    def _load_user_stocks() -> Dict[str, Any]:
        """加载用户股票数据"""
        try:
            with open(Config.user_stocks_file(), 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    @staticmethod
    def _save_user_stocks(data: Dict[str, Any]):
        """保存用户股票数据"""
        with open(Config.user_stocks_file(), 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def watch_stock(user, code: str):
        """关注股票"""
        user_id = StockManager._get_user_id(user)
        stocks = StockManager._load_user_stocks()
        
        if user_id not in stocks:
            stocks[user_id] = {}
        
        if code not in stocks[user_id]:
            stocks[user_id][code] = {}
        
        StockManager._save_user_stocks(stocks)
        logger.info(f"User {user_id} watched stock {code}")
    
    @staticmethod
    def forget_stock(user, code: str):
        """取消关注股票"""
        user_id = StockManager._get_user_id(user)
        stocks = StockManager._load_user_stocks()
        
        if user_id in stocks and code in stocks[user_id]:
            del stocks[user_id][code]
            StockManager._save_user_stocks(stocks)
            logger.info(f"User {user_id} forgot stock {code}")
    
    @staticmethod
    def get_watchings(user) -> Dict[str, Any]:
        """获取用户关注的股票"""
        user_id = StockManager._get_user_id(user)
        stocks = StockManager._load_user_stocks()
        return stocks.get(user_id, {})
    
    # ==================== 成交记录 ====================
    
    @staticmethod
    def _load_user_deals() -> Dict[str, List[Dict[str, Any]]]:
        """加载用户成交记录"""
        try:
            with open(Config.user_deals_file(), 'r') as f:
                data = json.load(f)
                # 兼容旧格式 (数组)
                if isinstance(data, list):
                    return {}
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    @staticmethod
    def _save_user_deals(data: Dict[str, List[Dict[str, Any]]]):
        """保存用户成交记录"""
        with open(Config.user_deals_file(), 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    async def add_deals(user, data: str):
        """添加成交记录"""
        user_id = StockManager._get_user_id(user)
        
        # 解析JSON数据
        try:
            if isinstance(data, str):
                deals = json.loads(data)
            else:
                deals = data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse deals data: {e}")
            return
        
        if not isinstance(deals, list):
            deals = [deals]
        
        # 加载现有数据
        all_deals = StockManager._load_user_deals()
        
        if user_id not in all_deals:
            all_deals[user_id] = []
        
        udeals = all_deals[user_id]
        
        # 添加或更新记录：若存在则更新，否则追加
        added_count = 0
        updated_count = 0
        for deal in deals:
            bs = deal.get('tradeType', '')
            code = deal.get('code', '')
            sid = deal.get('sid', '')
            dtime = deal.get('time', '').split(' ')[0]

            found_index = None
            for idx, d in enumerate(udeals):
                if (
                    d.get('sid') == sid and
                    d.get('code') == code and
                    d.get('tradeType') == bs and
                    d.get('time', '').split(' ')[0] == dtime
                ):
                    found_index = idx
                    break

            if found_index is not None:
                udeals[found_index].update(deal)
                updated_count += 1
            else:
                udeals.append(deal)
                added_count += 1
        
        all_deals[user_id] = udeals
        StockManager._save_user_deals(all_deals)
        logger.info(f"User {user_id} added {added_count} deals, updated {updated_count} deals")
    
    @staticmethod
    async def fix_deals(user, data: str):
        """修复成交记录"""
        user_id = StockManager._get_user_id(user)
        
        try:
            if isinstance(data, str):
                fix_data = json.loads(data)
            else:
                fix_data = data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse fix data: {e}")
            return
        
        all_deals = StockManager._load_user_deals()
        
        if user_id not in all_deals:
            logger.warning(f"User {user_id} has no deals to fix")
            return
        
        udeals = all_deals[user_id]
        
        # 根据 sid 查找并修复记录
        if 'sid' in fix_data:
            for deal in udeals:
                if deal.get('sid') == fix_data.get('sid'):
                    deal.update(fix_data)
                    break
        
        all_deals[user_id] = udeals
        StockManager._save_user_deals(all_deals)
        logger.info(f"User {user_id} fixed deals")
    
    @staticmethod
    def remove_deals(user, code: str, bsid: List[str], ssid: List[str]):
        """删除指定成交记录"""
        user_id = StockManager._get_user_id(user)
        all_deals = StockManager._load_user_deals()
        
        if user_id not in all_deals:
            logger.warning(f"User {user_id} has no deals to remove")
            return
        
        udeals = all_deals[user_id]
        
        # 过滤掉要删除的记录
        sids_to_remove = set(bsid + ssid)
        original_count = len(udeals)
        
        udeals = [
            d for d in udeals 
            if not (d.get('code', '').endswith(code) and d.get('sid') in sids_to_remove)
        ]
        
        removed_count = original_count - len(udeals)
        
        all_deals[user_id] = udeals
        StockManager._save_user_deals(all_deals)
        logger.info(f"User {user_id} removed {removed_count} deals for {code}")
    
    @staticmethod
    def get_deals(user) -> List[Dict[str, Any]]:
        """获取用户的成交记录"""
        user_id = StockManager._get_user_id(user)
        all_deals = StockManager._load_user_deals()
        return all_deals.get(user_id, [])

    # ==================== 策略配置 ====================
    
    @staticmethod
    def save_strategy(user, code: str, data: str):
        """保存股票策略配置"""
        user_id = StockManager._get_user_id(user)
        stocks = StockManager._load_user_stocks()
        
        if user_id not in stocks:
            stocks[user_id] = {}
        
        if code not in stocks[user_id]:
            stocks[user_id][code] = {}
        
        # 解析策略数据
        try:
            if isinstance(data, str):
                strategy = json.loads(data)
            else:
                strategy = data
        except json.JSONDecodeError:
            strategy = data
        
        stocks[user_id][code]['strategies'] = strategy
        
        StockManager._save_user_stocks(stocks)
        logger.info(f"User {user_id} saved strategy for {code}")
    
    @staticmethod
    def remove_strategy(user, code: str):
        """删除股票策略配置"""
        user_id = StockManager._get_user_id(user)
        stocks = StockManager._load_user_stocks()
        
        if user_id in stocks and code in stocks[user_id]:
            if 'strategies' in stocks[user_id][code]:
                del stocks[user_id][code]['strategies']
                StockManager._save_user_stocks(stocks)
                logger.info(f"User {user_id} removed strategy for {code}")
    
    @staticmethod
    def get_strategy(user, code: str) -> Optional[Dict[str, Any]]:
        """获取股票策略配置"""
        user_id = StockManager._get_user_id(user)
        stocks = StockManager._load_user_stocks()
        
        if user_id in stocks and code in stocks[user_id]:
            return stocks[user_id][code].get('strategies')
        return None

