from typing import Any, Dict

from crawler.utils.db_manager import DatabaseManager


class MySQLStorePipeline:
    def __init__(self, settings):
        self.db_manager = DatabaseManager.from_settings(settings)
        if not self.db_manager.engine:
            raise ValueError("MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB 均为必填配置")

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)

    def process_item(self, item: Dict[str, Any], spider):
        self.db_manager.save_article(
            task_id=item.get("task_id"),
            title=item.get("title"),
            link=item.get("link"),
            content=item.get("content"),
            source_url=item.get("source_url"),
            extra=item.get("extra"),
        )
        return item

