import os
import json

# 加载 .env 文件
from crawler.utils.env_loader import load_env_file
load_env_file()

import scrapy
from scrapy_redis.spiders import RedisSpider
from crawler.utils.redis_manager import RedisManager
from crawler.utils.encoding_handler import EncodingHandler


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
        # 处理响应编码
        headers_dict = {}
        for k, v in response.headers.items():
            key = k.decode() if isinstance(k, bytes) else str(k)
            val = v.decode() if isinstance(v, bytes) else str(v)
            headers_dict[key] = val
        
        # 检查是否在 meta 中指定了编码
        custom_encoding = response.meta.get("encoding") if response.meta else None
        
        # 处理响应编码
        if custom_encoding:
            # 使用手动指定的编码
            try:
                response_text = response.body.decode(custom_encoding, errors='replace')
                encoding_info = {
                    'encoding': custom_encoding,
                    'confidence': 1.0,
                    'source': 'manual',
                    'methods': ['manual_config']
                }
            except (UnicodeDecodeError, LookupError):
                # 如果指定的编码失败，回退到自动检测
                response_text = EncodingHandler.decode_content(response.body, headers_dict)
                encoding_info = EncodingHandler.get_encoding_info(response.body, headers_dict)
        else:
            # 自动检测编码
            response_text = EncodingHandler.decode_content(response.body, headers_dict)
            encoding_info = EncodingHandler.get_encoding_info(response.body, headers_dict)
        
        # ... existing code ...
        
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
            val = v.decode() if isinstance(v, bytes) else str(v)
            headers[key] = val
        
        requested_at = _to_str(response.headers.get("Date", b""))

        record = {
            "url": response.url,
            "status": response.status,
            "headers": headers,
            "body": response_text,  # 使用正确解码后的内容
            "encoding": encoding_info.get('encoding'),  # 记录使用的编码
            "encoding_confidence": encoding_info.get('confidence'),  # 记录编码置信度
            "meta": response.meta,
            "requested_at": requested_at,
        }
        self.redis_manager.lpush(self.success_key, json.dumps(record, ensure_ascii=False))

