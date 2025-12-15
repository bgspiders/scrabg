import json
from types import MappingProxyType
from urllib.parse import urljoin
from typing import Any, Dict, Iterable, List

import scrapy

from crawler.items import ArticleItem


class WorkflowRunner:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.task_info = config.get("taskInfo", {})
        self.steps = config.get("workflowSteps", [])

    def initial_requests(self) -> Iterable[scrapy.Request]:
        base_url = self.task_info.get("baseUrl")
        headers = self._parse_headers(self.steps)
        if base_url:
            yield scrapy.Request(
                url=base_url,
                headers=headers,
                callback=self.handle_response,
                meta={"workflow_index": 0},
                dont_filter=False,
            )

    def handle_response(self, response: scrapy.http.Response):
        index = response.meta.get("workflow_index", 0)
        if index >= len(self.steps):
            return

        step = self.steps[index]
        step_type = step.get("type")
        next_index = index + 1

        if step_type == "link_extraction":
            for req in self._handle_link_extraction(step, response, next_index):
                yield req
        elif step_type == "data_extraction":
            for obj in self._handle_data_extraction(step, response, next_index):
                yield obj
        elif step_type == "request":
            # 直接进入下一个步骤
            response.meta["workflow_index"] = next_index
            yield from self.handle_response(response)

    def _handle_link_extraction(self, step: Dict[str, Any], response, next_index: int):
        rules = step.get("config", {}).get("linkExtractionRules", [])
        base = str(response.url)
        for rule in rules:
            field = rule.get("fieldName") or "link"
            expr = rule.get("expression")
            extract_type = rule.get("extractType", "xpath")
            multiple = rule.get("multiple", False)
            max_links = rule.get("maxLinks")

            values = self._extract(response, expr, extract_type, multiple)
            if max_links:
                values = values[:max_links]

            for val in values:
                link = urljoin(base, val) if field == "link" else val
                yield scrapy.Request(
                    url=link,
                    callback=self.handle_response,
                    meta={"workflow_index": next_index, "title": response.meta.get("title"), field: val},
                    dont_filter=True,
                )

    def _handle_data_extraction(self, step: Dict[str, Any], response, next_index: int):
        rules = step.get("config", {}).get("extractionRules", [])
        data: Dict[str, Any] = {}
        for rule in rules:
            field = rule.get("fieldName")
            expr = rule.get("expression")
            extract_type = rule.get("extractType", "xpath")
            multiple = rule.get("multiple", False)
            value = self._extract(response, expr, extract_type, multiple)
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
            for req in self._run_custom_code(custom_code, response.text, response.url, data, next_index):
                yield req

    @staticmethod
    def _parse_headers(steps: List[Dict[str, Any]]) -> Dict[str, str]:
        for step in steps:
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
        selector = response.xpath if extract_type == "xpath" else response.css
        values = selector(expr).getall() if multiple else selector(expr).get()
        if values is None:
            return [] if multiple else ""
        return values

    def _run_custom_code(
        self,
        code: str,
        response_text: str,
        current_url: str,
        extracted_data: Dict[str, Any],
        next_index: int,
    ):
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

