import json
import os

import scrapy
from scrapy_redis.spiders import RedisSpider

from crawler.utils.config_loader import load_config
from crawler.utils.workflow import WorkflowRunner


class ConfigSpider(RedisSpider):
    name = "config_spider"
    redis_key = "config_spider:start_urls"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config_path = kwargs.get("config_path") or os.getenv(
            "CONFIG_PATH", "/Users/bgspider/websites/scrabg/demo.json"
        )
        self.config = load_config(config_path)
        task_info = self.config.get("taskInfo", {})
        # 覆盖并发/延时
        if task_info.get("concurrency"):
            self.crawler.settings.set("CONCURRENT_REQUESTS", task_info["concurrency"], priority="cmdline")
        if task_info.get("requestInterval") is not None:
            self.crawler.settings.set("DOWNLOAD_DELAY", task_info["requestInterval"], priority="cmdline")
        self.runner = WorkflowRunner(self.config)

    def make_request_from_data(self, data):
        payload = json.loads(data)
        return scrapy.Request(
            url=payload["url"],
            method=payload.get("method", "GET"),
            headers=payload.get("headers"),
            meta=payload.get("meta") or {"workflow_index": 0},
            callback=self.runner.handle_response,
            dont_filter=payload.get("dont_filter", False),
        )

    def start_requests(self):
        # 当未通过 redis 提供启动 URL 时，使用配置中的 baseUrl
        for req in self.runner.initial_requests():
            yield req

