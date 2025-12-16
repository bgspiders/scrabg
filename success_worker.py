"""
持续消费 fetch_spider 成功队列，根据 demo.json 的 workflowSteps 决定下一步请求或产出数据。
"""
import json
import os
import time
from types import MappingProxyType
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from parsel import Selector
from redis import Redis

from crawler.utils.config_loader import load_config
from crawler.utils.db_manager import DatabaseManager
from crawler.utils.env_loader import load_env_file
from crawler.utils.redis_manager import RedisManager

load_env_file()


class WorkflowProcessor:
    def __init__(self, config: Dict[str, Any], redis_manager: RedisManager, db_manager: Optional[DatabaseManager] = None):
        self.config = config
        self.redis_manager = redis_manager
        self.db_manager = db_manager
        self.steps = config.get("workflowSteps", [])
        self.task_info = config.get("taskInfo", {})
        self.start_key = os.getenv("SCRAPY_START_KEY", "fetch_spider:start_urls")
        self.success_key = os.getenv("SUCCESS_QUEUE_KEY", "fetch_spider:success")
        self.data_key = os.getenv("SUCCESS_ITEM_KEY", "fetch_spider:data_items")
        self.error_key = os.getenv("SUCCESS_ERROR_KEY", "fetch_spider:errors")
        self.default_headers = self._parse_headers()

    def run_forever(self, sleep_seconds: float = 1.0):
        print(f"[worker] Listening on redis list {self.success_key}")
        while True:
            result = self.redis_manager.brpop([self.success_key], timeout=5)
            if not result:
                time.sleep(sleep_seconds)
                continue
            _, data = result
            try:
                record = json.loads(data)
                self.process_record(record)
            except Exception as exc:
                print(f"[worker] 处理失败: {exc}")
                self.redis_manager.lpush(
                    self.error_key,
                    json.dumps({"error": str(exc), "payload": data.decode("utf-8")}, ensure_ascii=False),
                )

    def process_record(self, record: Dict[str, Any]):
        meta = record.get("meta") or {}
        workflow_index = meta.get("workflow_index", 0)
        context = meta.get("context") or {}

        selector = Selector(text=record.get("body", ""))
        response = {
            "selector": selector,
            "url": record.get("url"),
            "body": record.get("body", ""),
            "context": context,
        }

        self._advance(response, workflow_index)

    def _advance(self, response: Dict[str, Any], index: int):
        while index < len(self.steps):
            step = self.steps[index]
            step_type = step.get("type")
            if step_type == "request":
                index += 1
                continue
            if step_type == "link_extraction":
                self._handle_link_extraction(step, response, index)
                return
            if step_type == "data_extraction":
                self._handle_data_extraction(step, response, index)
                return
            index += 1

    def _handle_link_extraction(self, step: Dict[str, Any], response: Dict[str, Any], index: int):
        rules = step.get("config", {}).get("linkExtractionRules", [])
        if not rules:
            return

        link_rule = next((r for r in rules if r.get("fieldName") == "link"), None)
        if not link_rule:
            print("[worker] 未找到 link 字段的提取规则，跳过")
            return

        selector: Selector = response["selector"]
        link_values = self._extract(selector, link_rule, multiple=True)
        other_values = {
            rule.get("fieldName"): self._extract(selector, rule, multiple=True)
            for rule in rules
            if rule.get("fieldName") != "link"
        }

        max_links = link_rule.get("maxLinks")
        if max_links:
            link_values = link_values[:max_links]

        next_index = index + 1
        for idx, raw_link in enumerate(link_values):
            absolute_url = urljoin(response["url"], raw_link)
            next_context = dict(response["context"])
            for field, values in other_values.items():
                if not values:
                    continue
                value = values[idx] if idx < len(values) else values[-1]
                next_context[field] = value

            payload = {
                "url": absolute_url,
                "method": "GET",
                "headers": self.default_headers,
                "meta": {
                    "workflow_index": next_index,
                    "context": next_context,
                },
                "dont_filter": False,
            }
            self.redis_manager.lpush(self.start_key, json.dumps(payload, ensure_ascii=False))
            print(f"[worker] 推送下级请求 -> {absolute_url}")

    def _handle_data_extraction(self, step: Dict[str, Any], response: Dict[str, Any], index: int):
        rules = step.get("config", {}).get("extractionRules", [])
        selector: Selector = response["selector"]
        data: Dict[str, Any] = {}
        for rule in rules:
            field = rule.get("fieldName")
            values = self._extract(selector, rule, multiple=rule.get("multiple", False))
            data[field] = values

        item = {
            "task_id": self.task_info.get("id"),
            "task_name": self.task_info.get("name"),
            "source_url": response["url"],
            "context": response["context"],
            "data": data,
        }
        
        # Check if this is the last workflow step
        is_last_step = (index == len(self.steps) - 1)
        custom_code = step.get("config", {}).get("nextRequestCustomCode")
        has_next_request = bool(custom_code)
        
        if is_last_step and not has_next_request:
            # Save to database if it's the last step and no custom code to generate next requests
            if self.db_manager and self.db_manager.engine:
                self._save_to_database(item)
            else:
                # Fallback to Redis if database is not configured
                self.redis_manager.lpush(self.data_key, json.dumps(item, ensure_ascii=False))
                print(f"[worker] 数据已写入 Redis {self.data_key}: {response['url']}")
        else:
            # Not the last step or has custom code, save to Redis
            self.redis_manager.lpush(self.data_key, json.dumps(item, ensure_ascii=False))
            print(f"[worker] 数据已写入 Redis {self.data_key}: {response['url']}")

        if custom_code:
            for req in self._run_custom_code(custom_code, response, index + 1, data):
                self.redis_manager.lpush(self.start_key, json.dumps(req, ensure_ascii=False))
                print(f"[worker] 自定义代码推送请求 -> {req['url']}")

    def _extract(self, selector: Selector, rule: Dict[str, Any], multiple: bool) -> Any:
        expression = rule.get("expression")
        extract_type = rule.get("extractType", "xpath")
        if not expression:
            return [] if multiple else ""

        if extract_type == "css":
            sel = selector.css(expression)
        else:
            sel = selector.xpath(expression)

        if multiple:
            return [value.strip() if isinstance(value, str) else value for value in sel.getall()]
        value = sel.get()
        return value.strip() if isinstance(value, str) else value

    def _parse_headers(self) -> Dict[str, str]:
        for step in self.steps:
            if step.get("type") == "request":
                cfg = step.get("config", {})
                if cfg.get("headersMode") == "json" and cfg.get("headersJson"):
                    try:
                        return json.loads(cfg["headersJson"])
                    except json.JSONDecodeError:
                        return {}
        return {}

    def _save_to_database(self, item: Dict[str, Any]):
        """Save extracted data to MySQL database"""
        try:
            data = item.get("data", {})
            context = item.get("context", {})
            source_url = item.get("source_url", "")
            
            # Merge context and data for extra field
            extra = {**context}
            
            # link defaults to source_url if not provided
            link = context.get("link") or source_url
            
            # Use DatabaseManager to save article
            self.db_manager.save_article(
                task_id=item.get("task_id"),
                title=data.get("title") or context.get("title") or "",
                link=link,
                content=data.get("content") or "",
                source_url=source_url,
                extra=extra,
            )
            print(f"[worker] ✓ 数据已保存到数据库: {source_url}")
        except Exception as e:
            print(f"[worker] ✗ 保存到数据库失败: {e}")
            # Fallback: save to Redis error queue
            self.redis_manager.lpush(
                self.error_key,
                json.dumps({"error": f"Database save failed: {str(e)}", "item": item}, ensure_ascii=False),
            )

    def _run_custom_code(
        self,
        code: str,
        response: Dict[str, Any],
        next_index: int,
        extracted_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        safe_globals = {
            "__builtins__": MappingProxyType(
                {
                    "range": range,
                    "len": len,
                    "enumerate": enumerate,
                    "json": json,
                }
            ),
            "urljoin": urljoin,
        }
        local_vars: Dict[str, Any] = {}
        exec(code, safe_globals, local_vars)
        process_request = local_vars.get("process_request")
        if not callable(process_request):
            return []

        results = process_request(response["body"], response["url"], extracted_data)
        requests: List[Dict[str, Any]] = []
        for item in results or []:
            meta = item.get("meta") or {}
            meta.setdefault("workflow_index", next_index)
            requests.append(
                {
                    "url": item.get("url"),
                    "method": item.get("method", "GET"),
                    "headers": item.get("headers") or self.default_headers,
                    "meta": meta,
                    "dont_filter": item.get("dont_filter", False),
                }
            )
        return requests


def main():
    config_path = os.getenv("CONFIG_PATH", "demo.json")
    config = load_config(config_path)
    
    # Create Redis manager
    redis_manager = None
    try:
        redis_manager = RedisManager.from_env(decode_responses=False)
        if redis_manager.test_connection():
            print(f"[success_worker] ✓ Redis 连接成功: {redis_manager.get_masked_url()}")
        else:
            raise RuntimeError("Redis connection test failed")
    except Exception as e:
        error_msg = str(e)
        if "Authentication required" in error_msg or "NOAUTH" in error_msg:
            print(f"[success_worker] ✗ Redis 认证失败！")
            print(f"[success_worker] 请检查 .env 文件中的 REDIS_URL 配置")
            print(f"[success_worker] 格式: redis://:password@host:port/db")
        else:
            print(f"[success_worker] ✗ Redis 连接失败: {error_msg}")
        raise
    
    # Create database manager (optional)
    db_manager = None
    try:
        db_manager = DatabaseManager.from_env()
        if db_manager.engine and db_manager.test_connection():
            print(f"[success_worker] ✓ MySQL 连接成功: {db_manager.host}:{db_manager.port}/{db_manager.database}")
        else:
            print(f"[success_worker] ⚠️  MySQL 配置不完整，将使用 Redis 队列存储数据")
            db_manager = None
    except Exception as e:
        print(f"[success_worker] ⚠️  MySQL 连接失败: {e}")
        print(f"[success_worker] 将使用 Redis 队列存储数据")
        db_manager = None

    processor = WorkflowProcessor(config, redis_manager, db_manager)
    processor.run_forever()


if __name__ == "__main__":
    main()

