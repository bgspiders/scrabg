from datetime import datetime
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy import create_engine


class MySQLStorePipeline:
    def __init__(self, settings):
        user = settings.get("MYSQL_USER")
        password = settings.get("MYSQL_PASSWORD")
        host = settings.get("MYSQL_HOST", "localhost")
        port = settings.get("MYSQL_PORT", 3306)
        db = settings.get("MYSQL_DB")
        charset = settings.get("MYSQL_CHARSET", "utf8mb4")

        if not all([user, password, db]):
            raise ValueError("MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB 均为必填配置")

        self.engine: Engine = create_engine(
            f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset={charset}",
            pool_size=settings.getint("MYSQL_POOL_SIZE", 5),
            max_overflow=settings.getint("MYSQL_POOL_MAX_OVERFLOW", 5),
            pool_pre_ping=True,
            pool_recycle=3600,
        )

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)

    def process_item(self, item: Dict[str, Any], spider):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO articles(task_id, title, link, content, source_url, extra, created_at)
                    VALUES (:task_id, :title, :link, :content, :source_url, :extra, :created_at)
                    """
                ),
                {
                    "task_id": item.get("task_id"),
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "content": item.get("content"),
                    "source_url": item.get("source_url"),
                    "extra": item.get("extra"),
                    "created_at": datetime.utcnow(),
                },
            )
        return item

