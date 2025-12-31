from typing import Any, Dict, Optional

from crawler.utils.db_manager import DatabaseManager
from crawler.utils.mongodb_manager import MongoDBManager


class MySQLStorePipeline:
    """数据存储管道：支持 MongoDB 和 MySQL 的优先级切换
    
    优先级：MongoDB > MySQL
    - 如果 MongoDB 可用，优先保存到 MongoDB
    - 否则保存到 MySQL
    - 如果都不可用，则跳过保存
    """
    
    def __init__(self, settings):
        self.db_manager: Optional[DatabaseManager] = None
        self.mongodb_manager: Optional[MongoDBManager] = None
        
        # 初始化 MySQL 数据库管理器
        try:
            db_manager = DatabaseManager.from_settings(settings)
            if db_manager.engine and db_manager.test_connection():
                self.db_manager = db_manager
                print(f"[Pipeline] ✓ MySQL 连接成功: {db_manager.host}:{db_manager.port}/{db_manager.database}")
            else:
                print(f"[Pipeline] ⚠️  MySQL 配置不完整或连接失败")
        except Exception as e:
            print(f"[Pipeline] ⚠️  MySQL 初始化失败: {e}")
        
        # 初始化 MongoDB 数据库管理器
        try:
            mongodb_manager = MongoDBManager.from_env()
            if mongodb_manager.client is not None and mongodb_manager.test_connection():
                self.mongodb_manager = mongodb_manager
                print(f"[Pipeline] ✓ MongoDB 连接成功: {mongodb_manager.get_masked_uri()}")
            else:
                print(f"[Pipeline] ⚠️  MongoDB 配置不完整或连接失败")
        except Exception as e:
            print(f"[Pipeline] ⚠️  MongoDB 初始化失败: {e}")
        
        # 检查至少有一个数据库可用
        if not self.db_manager and not self.mongodb_manager:
            print(f"[Pipeline] ⚠️  警告：MySQL 和 MongoDB 都不可用，数据将不被保存！")

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)

    def process_item(self, item: Dict[str, Any], spider):
        """处理数据项，优先保存到 MongoDB，其次保存到 MySQL"""
        title = item.get('title', '未命名')
        link = item.get('link', '')
        
        print(f"[Pipeline] 处理数据项: {title} -> {link}")
        
        # 优先保存到 MongoDB
        if self.mongodb_manager is not None and self.mongodb_manager.client is not None:
            try:
                article_id = self._save_to_mongodb(item)
                if article_id:
                    print(f"[Pipeline] ✓ 数据已保存到 MongoDB (ID: {article_id}): {title}")
                    return item
            except Exception as e:
                print(f"[Pipeline] ✗ 保存到 MongoDB 失败: {e}")
        
        # 回退保存到 MySQL
        if self.db_manager is not None and self.db_manager.engine is not None:
            try:
                self._save_to_mysql(item)
                print(f"[Pipeline] ✓ 数据已保存到 MySQL: {title}")
                return item
            except Exception as e:
                print(f"[Pipeline] ✗ 保存到 MySQL 失败: {e}")
        
        # 都不可用时跳过
        print(f"[Pipeline] ⚠️  跳过数据保存（无可用数据库）: {title}")
        return item
    
    def _save_to_mysql(self, item: Dict[str, Any]):
        """保存数据到 MySQL"""
        self.db_manager.save_article(
            task_id=item.get("task_id"),
            title=item.get("title"),
            link=item.get("link"),
            content=item.get("content"),
            source_url=item.get("source_url"),
            extra=item.get("extra"),
        )
    
    def _save_to_mongodb(self, item: Dict[str, Any]) -> Optional[str]:
        """保存数据到 MongoDB，返回插入的文档 ID"""
        article_id = self.mongodb_manager.save_article(
            task_id=item.get("task_id"),
            title=item.get("title"),
            link=item.get("link"),
            content=item.get("content"),
            source_url=item.get("source_url"),
            extra=item.get("extra"),
        )
        if not article_id:
            raise Exception("MongoDB 保存返回空 ID")
        return article_id

