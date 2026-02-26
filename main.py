import json
from fastapi import FastAPI, Query, Header
from typing import Optional, List, Dict, Any
from app.lofig import Config, logging, logger
from app.router import router as stk_router
from app.api import router as api_router

cfg = Config.client_config()
app = FastAPI(title=cfg.get('app_name', 'pyswee'))

app.include_router(api_router)
app.include_router(stk_router)


@app.get("/userbind")
def get_userbind(
    onlystock: Optional[int] = Query(1, description="仅返回股票账户"),
) -> List[Dict[str, Any]]:
    """
    获取用户绑定的交易账户
    
    GET /userbind?onlystock=1
    
    - onlystock: 1 表示仅返回股票账户 deprecated，暂不使用
    - 返回: 账户数组，每个账户包含 name, username, realcash 等字段
    """
    with open(Config.users_file(), 'r') as f:
        users = json.load(f)
    return [u for u in users if u.get('parent_id', 0) == 1]


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=cfg.get('port', 8000), log_config=None, access_log=True)
