import json
import os
from types import MappingProxyType
from urllib.parse import urljoin

import scrapy
from scrapy_redis.spiders import RedisSpider

from crawler.utils.config_loader import load_config
from crawler.utils.workflow import WorkflowRunner
from crawler.utils.encoding_handler import EncodingHandler
from crawler.items import ArticleItem


class ConfigSpider(RedisSpider):
    name = "config_spider"
    redis_key = "config_spider:start_urls"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config_path = kwargs.get("config_path") or os.getenv(
            "CONFIG_PATH", "./demo.json"
        )
        self.config = load_config(config_path)
        self.task_info = self.config.get("taskInfo", {})
        self.workflow_steps = self.config.get("workflowSteps", [])

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        task_info = spider.task_info
        # 覆盖并发/延时
        if task_info.get("concurrency"):
            crawler.settings.set("CONCURRENT_REQUESTS", task_info["concurrency"], priority="cmdline")
        if task_info.get("requestInterval") is not None:
            crawler.settings.set("DOWNLOAD_DELAY", task_info["requestInterval"], priority="cmdline")
        return spider

    def make_request_from_data(self, data):
        payload = json.loads(data)
        return scrapy.Request(
            url=payload["url"],
            method=payload.get("method", "GET"),
            headers=payload.get("headers"),
            meta=payload.get("meta") or {"workflow_index": 0},
            callback=self.handle_response,
            dont_filter=payload.get("dont_filter", False),
        )

    def start_requests(self):
        # 当未通过 redis 提供启动 URL 时，使用配置中的 baseUrl
        base_url = self.task_info.get("baseUrl")
        headers = self._parse_headers()
        if base_url:
            yield scrapy.Request(
                url=base_url,
                headers=headers,
                callback=self.handle_response,
                meta={"workflow_index": 0},
                dont_filter=False,
            )

    def handle_response(self, response: scrapy.http.Response):
        # 处理响应编码
        response_text = self._handle_response_encoding(response)
        
        index = response.meta.get("workflow_index", 0)
        if index >= len(self.workflow_steps):
            return

        step = self.workflow_steps[index]
        step_type = step.get("type")
        next_index = index + 1

        if step_type == "link_extraction":
            for req in self._handle_link_extraction(step, response, next_index, response_text):
                yield req
        elif step_type == "data_extraction":
            for obj in self._handle_data_extraction(step, response, next_index, response_text):
                yield obj
        elif step_type == "request":
            # 直接进入下一个步骤
            response.meta["workflow_index"] = next_index
            yield from self.handle_response(response)

    def _handle_link_extraction(self, step, response, next_index: int, response_text: str = None):
        """处理链接提取步骤
        
        参考 success_worker.py 的逻辑：
        - 链接字段强制以列表方式提取（multiple=True）
        - 其他字段对应提取，自动处理索引匹配
        """
        if response_text is None:
            response_text = response.text
        
        config = step.get("config", {})
        rules = config.get("linkExtractionRules", [])
        if not rules:
            return
        
        # 找到 link 字段的规则
        link_rule = next((r for r in rules if r.get("fieldName") == "link"), None)
        if not link_rule:
            return
        
        # 强制以列表方式提取链接
        link_values = self._extract(response_text, link_rule.get("expression"), link_rule.get("extractType", "xpath"), multiple=True)
        if not isinstance(link_values, list):
            link_values = [link_values] if link_values else []
        
        # 提取其他字段（title 等）的值，用于配对
        other_values = {}
        for rule in rules:
            if rule.get("fieldName") != "link":
                field_name = rule.get("fieldName")
                values = self._extract(response_text, rule.get("expression"), rule.get("extractType", "xpath"), multiple=True)
                if not isinstance(values, list):
                    values = [values] if values else []
                other_values[field_name] = values
        
        # 限制链接数量
        max_links = link_rule.get("maxLinks")
        if max_links:
            link_values = link_values[:max_links]
        
        # 处理每条链接
        base = str(response.url)
        for idx, raw_link in enumerate(link_values):
            # 处理空值
            if not raw_link:
                continue
            
            # 清理链接值（去除空白）
            raw_link = raw_link.strip() if isinstance(raw_link, str) else raw_link
            if not raw_link:
                continue
            
            # 生成绝对 URL
            absolute_url = urljoin(base, raw_link)
            
            # 准备 meta 信息，包含其他字段的值
            next_context = {}
            for field, values in other_values.items():
                if values:
                    # 如果有足够的值，取对应索引；否则取最后一个
                    value = values[idx] if idx < len(values) else values[-1]
                    if value:
                        value = value.strip() if isinstance(value, str) else value
                        next_context[field] = value
            
            # 生成请求
            yield scrapy.Request(
                url=absolute_url,
                callback=self.handle_response,
                meta={"workflow_index": next_index, **next_context},
                dont_filter=True,
            )
            print(f"[config_spider] 链接提取 -> {absolute_url}")

    def _handle_data_extraction(self, step, response, next_index: int, response_text: str = None):
        if response_text is None:
            response_text = response.text
        
        rules = step.get("config", {}).get("extractionRules", [])
        data = {}
        for rule in rules:
            field = rule.get("fieldName")
            expr = rule.get("expression")
            extract_type = rule.get("extractType", "xpath")
            multiple = rule.get("multiple", False)
            # 使用处理过编码的 response_text 来提取数据
            value = self._extract(response_text, expr, extract_type, multiple)
            data[field] = value

        item = ArticleItem()
        item["task_id"] = self.task_info.get("id")
        item["title"] = response.meta.get("title") or data.get("title")
        item["link"] = response.meta.get("link") or response.url
        item["content"] = data.get("content")
        item["source_url"] = response.url
        item["extra"] = data
        yield item

        custom_code = step.get("config", {}).get("nextRequestCustomCode")
        if custom_code:
            for req in self._run_custom_code(custom_code, response_text, response.url, data, next_index):
                yield req

    def _parse_headers(self):
        for step in self.workflow_steps:
            if step.get("type") == "request":
                cfg = step.get("config", {})
                if cfg.get("headersMode") == "json" and cfg.get("headersJson"):
                    try:
                        return json.loads(cfg.get("headersJson"))
                    except json.JSONDecodeError:
                        return {}
        return {}

    @staticmethod
    def _extract(response, expr: str, extract_type: str, multiple: bool):
        """
        提取数据，参考 success_worker.py 的逻辑
        - 自动处理字符串 text 和 Selector 对象
        - 自动对提取结果进行 .strip() 处理
        """
        # 如果传入的是字符串（response_text），需要创建 Selector
        if isinstance(response, str):
            from parsel import Selector
            selector_obj = Selector(text=response)
            selector = selector_obj.xpath if extract_type == "xpath" else selector_obj.css
        else:
            selector = response.xpath if extract_type == "xpath" else response.css
        
        if not expr:
            return [] if multiple else ""
        
        if multiple:
            # 多值提取，返回列表，并对每个值进行 strip()
            values = selector(expr).getall()
            return [value.strip() if isinstance(value, str) else value for value in (values or [])]
        else:
            # 单值提取
            value = selector(expr).get()
            return value.strip() if isinstance(value, str) else value

    def _handle_response_encoding(self, response: scrapy.http.Response) -> str:
        """
        处理响应编码，自动识别并正确解码
        支持从 demo.json 配置中读取编码设置
        
        Args:
            response: Scrapy 响应对象
        
        Returns:
            正确编码后的响应文本
        """
        # 获取原始二进制内容
        body = response.body
        
        # 准备响应头字典
        headers = dict(response.headers) if response.headers else {}
        headers_dict = {}
        for k, v in headers.items():
            key = k.decode() if isinstance(k, bytes) else k
            # 处理值可能是列表的情况
            if isinstance(v, list):
                val = v[0].decode() if isinstance(v[0], bytes) else v[0] if v else ''
            elif isinstance(v, bytes):
                val = v.decode('utf-8', errors='ignore')
            else:
                val = v
            headers_dict[key] = val
        
        # 从当前工作流步骤获取编码配置
        index = response.meta.get("workflow_index", 0)
        custom_encoding = None
        if index < len(self.workflow_steps):
            step = self.workflow_steps[index]
            config = step.get("config", {})
            encoding_mode = config.get("encodingMode", "auto")
            
            # 如果配置为手动编码，使用指定的编码
            if encoding_mode == "manual" and config.get("encoding"):
                custom_encoding = config.get("encoding")
        
        # 使用编码处理器解码内容
        if custom_encoding:
            # 使用手动指定的编码
            try:
                decoded_text = body.decode(custom_encoding, errors='replace')
                encoding_info = {
                    'encoding': custom_encoding,
                    'confidence': 1.0,
                    'source': 'manual',
                    'methods': ['manual_config']
                }
            except (UnicodeDecodeError, LookupError):
                # 如果指定的编码失败，回退到自动检测
                decoded_text = EncodingHandler.decode_content(body, headers_dict)
                encoding_info = EncodingHandler.get_encoding_info(body, headers_dict)
        else:
            # 自动检测编码
            decoded_text = EncodingHandler.decode_content(body, headers_dict)
            encoding_info = EncodingHandler.get_encoding_info(body, headers_dict)
        
        # 记录编码信息到响应元数据
        response.meta['encoding_info'] = encoding_info
        
        return decoded_text

    def _run_custom_code(self, code: str, response_text: str, current_url: str, extracted_data, next_index: int):
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
        local_vars = {}
        exec(code, safe_globals, local_vars)
        process_request = local_vars.get("process_request")
        if not callable(process_request):
            return []

        results = process_request(response_text, current_url, extracted_data)
        requests = []
        for r in results or []:
            req = scrapy.Request(
                url=r.get("url"),
                method=r.get("method", "GET"),
                headers=r.get("headers"),
                body=r.get("data"),
                callback=self.handle_response,
                meta={"workflow_index": next_index},
                dont_filter=False,
            )
            requests.append(req)
        return requests

