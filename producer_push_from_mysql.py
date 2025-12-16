"""
从 MySQL 读取待抓取请求，解析后推送到 Redis 队列，供 Scrapy-Redis 消费。
示例表结构:
CREATE TABLE pending_requests (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  url TEXT NOT NULL,
  method VARCHAR(10) DEFAULT 'GET',
  headers_json TEXT,
  params_json TEXT,
  meta_json TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
import json
import os
from typing import Any, Dict, Iterable

# 加载 .env 文件
from crawler.utils.env_loader import load_env_file
load_env_file()

from redis import Redis
from sqlalchemy import text
from crawler.utils.db_manager import DatabaseManager
from crawler.utils.redis_manager import RedisManager


def get_mysql_manager() -> DatabaseManager:
    """获取数据库管理器"""
    db_manager = DatabaseManager.from_env()
    if not db_manager.engine:
        raise RuntimeError("请设置 MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB")
    return db_manager


def get_redis_manager() -> RedisManager:
    """获取 Redis 管理器"""
    redis_manager = RedisManager.from_env(decode_responses=False)
    if not redis_manager.test_connection():
        raise RuntimeError("Redis 连接失败")
    return redis_manager


def fetch_pending_requests(db_manager: DatabaseManager) -> Iterable[Dict[str, Any]]:
    """从数据库获取待处理请求"""
    sql = text("SELECT id, url, method, headers_json, params_json, meta_json FROM pending_requests")
    result = db_manager.execute_query(sql)
    rows = result.mappings().all()
    for row in rows:
        yield {
            "id": row["id"],
            "url": row["url"],
            "method": row.get("method") or "GET",
            "headers": json.loads(row["headers_json"]) if row.get("headers_json") else None,
            "params": json.loads(row["params_json"]) if row.get("params_json") else None,
            "meta": json.loads(row["meta_json"]) if row.get("meta_json") else None,
        }


def push_to_redis(redis_manager: RedisManager, key: str, reqs: Iterable[Dict[str, Any]]):
    """推送请求到 Redis 队列"""
    for r in reqs:
        payload = {
            "url": r["url"],
            "method": r["method"],
            "headers": r["headers"],
            "meta": r["meta"] or {},
            "dont_filter": False,
        }
        if r.get("params"):
            payload["meta"]["params"] = r["params"]
        redis_manager.lpush(key, json.dumps(payload, ensure_ascii=False))


def main():
    redis_key = os.getenv("SCRAPY_START_KEY", "fetch_spider:start_urls")
    db_manager = get_mysql_manager()
    redis_manager = get_redis_manager()
    reqs = list(fetch_pending_requests(db_manager))
    if not reqs:
        print("no pending requests")
        return
    push_to_redis(redis_manager, redis_key, reqs)
    print(f"pushed {len(reqs)} requests to redis list {redis_key}")


if __name__ == "__main__":
    main()

