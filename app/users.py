import json
from cachetools import lru_cache
from app.lofig import Config, logger


class UserManager:
    """用户管理类"""

    @lru_cache(maxsize=1)
    @staticmethod
    def get_users():
        """获取用户列表"""
        with open(Config.users_file(), 'r') as f:
            users = json.load(f)
        return [u for u in users if u.get('parent_id', 0) == 1]

    @staticmethod
    def get_user_by(acc=None, accid=None):
        """获取用户绑定的账户列表"""
        users = UserManager.get_users()
        for user in users:
            if accid is not None and int(user.get('id')) == int(accid):
                return user
            if acc is not None and user.get('username').endswith(acc):
                return user
        return None