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
from sqlalchemy import create_engine, text


def get_mysql_engine():
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    db = os.getenv("MYSQL_DB")
    charset = os.getenv("MYSQL_CHARSET", "utf8mb4")
    if not all([user, password, db]):
        raise RuntimeError("请设置 MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB")
    return create_engine(f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset={charset}")


def get_redis_client():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return Redis.from_url(redis_url)


def fetch_pending_requests(engine) -> Iterable[Dict[str, Any]]:
    sql = text("SELECT id, url, method, headers_json, params_json, meta_json FROM pending_requests")
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    for row in rows:
        yield {
            "id": row["id"],
            "url": row["url"],
            "method": row.get("method") or "GET",
            "headers": json.loads(row["headers_json"]) if row.get("headers_json") else None,
            "params": json.loads(row["params_json"]) if row.get("params_json") else None,
            "meta": json.loads(row["meta_json"]) if row.get("meta_json") else None,
        }


def push_to_redis(redis_cli: Redis, key: str, reqs: Iterable[Dict[str, Any]]):
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
        redis_cli.lpush(key, json.dumps(payload, ensure_ascii=False))


def main():
    redis_key = os.getenv("SCRAPY_START_KEY", "fetch_spider:start_urls")
    engine = get_mysql_engine()
    redis_cli = get_redis_client()
    reqs = list(fetch_pending_requests(engine))
    if not reqs:
        print("no pending requests")
        return
    push_to_redis(redis_cli, redis_key, reqs)
    print(f"pushed {len(reqs)} requests to redis list {redis_key}")


if __name__ == "__main__":
    main()

