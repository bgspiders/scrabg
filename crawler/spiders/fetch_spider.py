import os
import json

# 加载 .env 文件
from crawler.utils.env_loader import load_env_file
load_env_file()

import scrapy
from scrapy_redis.spiders import RedisSpider
from crawler.utils.redis_manager import RedisManager


class FetchSpider(RedisSpider):
    name = "fetch_spider"
    redis_key = "fetch_spider:start_urls"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        success_key = kwargs.get("success_key") or os.getenv("SUCCESS_QUEUE_KEY", "fetch_spider:success")
        self.success_key = success_key
        self.redis_manager = RedisManager.from_env(decode_responses=False)

    def make_request_from_data(self, data):
        payload = json.loads(data)
        return scrapy.Request(
            url=payload["url"],
            method=payload.get("method", "GET"),
            headers=payload.get("headers"),
            meta=payload.get("meta") or {},
            callback=self.parse,
            dont_filter=payload.get("dont_filter", False),
        )

    def parse(self, response):
        def _to_str(val):
            # 安全转换，避免对非 bytes 对象调用 decode
            if isinstance(val, (bytes, bytearray, memoryview)):
                return bytes(val).decode(errors="ignore")
            if isinstance(val, (list, tuple)) and val:
                head = val[0]
                if isinstance(head, (bytes, bytearray, memoryview)):
                    return bytes(head).decode(errors="ignore")
                return str(head)
            return str(val)

        headers = {}
        for k, v in response.headers.items():
            key = k.decode() if isinstance(k, bytes) else str(k)
            headers[key] = _to_str(v)

        requested_at = _to_str(response.headers.get("Date", b""))

        record = {
            "url": response.url,
            "status": response.status,
            "headers": headers,
            "body": response.text,
            "meta": response.meta,
            "requested_at": requested_at,
        }
        self.redis_manager.lpush(self.success_key, json.dumps(record, ensure_ascii=False))

