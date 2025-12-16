"""
根据 demo.json 配置生成初始请求并推送到 Redis 队列，供 fetch_spider 消费。
"""
import json
import os
from typing import Any, Dict

from redis import Redis

from crawler.utils.config_loader import load_config
from crawler.utils.env_loader import load_env_file

load_env_file()


def build_initial_request(config: Dict[str, Any]) -> Dict[str, Any]:
    task_info = config.get("taskInfo", {})
    base_url = task_info.get("baseUrl")
    steps = config.get("workflowSteps", [])
    if not steps:
        raise ValueError("workflowSteps 为空，无法生成请求")

    first_step = steps[0]
    if first_step.get("type") != "request":
        raise ValueError("第一个 workflow step 必须是 request 类型")

    request_cfg = first_step.get("config", {})
    headers = {}
    if request_cfg.get("headersMode") == "json" and request_cfg.get("headersJson"):
        headers = json.loads(request_cfg["headersJson"])

    url = request_cfg.get("url") or base_url
    if not url:
        raise ValueError("请在 taskInfo.baseUrl 或 request.config.url 中提供初始 URL")

    payload = {
        "url": url,
        "method": request_cfg.get("method", "GET"),
        "headers": headers,
        "meta": {
            "workflow_index": 0,
            "context": {"task_id": task_info.get("id"), "task_name": task_info.get("name")},
        },
        "dont_filter": False,
    }
    return payload


def main():
    config_path = os.getenv("CONFIG_PATH", "demo.json")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    start_key = os.getenv("SCRAPY_START_KEY", "fetch_spider:start_urls")

    config = load_config(config_path)
    payload = build_initial_request(config)

    try:
        redis_cli = Redis.from_url(redis_url, decode_responses=False)
        redis_cli.ping()
        redis_cli.lpush(start_key, json.dumps(payload, ensure_ascii=False))
        print(f"[producer] 已推送初始请求到 {start_key}: {payload['url']}")
    except Exception as e:
        error_msg = str(e)
        if "Authentication required" in error_msg or "NOAUTH" in error_msg:
            print(f"[producer] ❌ Redis 认证失败！")
            print(f"[producer] 请检查 .env 文件中的 REDIS_URL 配置")
            print(f"[producer] 格式: redis://:password@host:port/db")
        else:
            print(f"[producer] ❌ Redis 连接失败: {error_msg}")
        raise


if __name__ == "__main__":
    main()

