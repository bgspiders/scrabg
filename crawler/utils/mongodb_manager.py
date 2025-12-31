"""
MongoDB 数据库管理工具：统一管理 MongoDB 连接和配置
"""
import os
from datetime import datetime
from typing import Any, Dict, Optional

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

from crawler.utils.timezone_helper import TimezoneHelper


class MongoDBManager:
    """MongoDB 数据库管理器，提供统一的连接和操作接口"""
    
    _instance: Optional['MongoDBManager'] = None
    _client: Optional[MongoClient] = None
    
    def __init__(
        self,
        uri: Optional[str] = None,
        database: Optional[str] = None,
        collection: str = "articles",
        connect_timeout: int = 5000,
        server_selection_timeout: int = 5000,
    ):
        """
        初始化 MongoDB 管理器
        
        Args:
            uri: MongoDB 连接 URI（默认从环境变量 MONGODB_URI 读取）
            database: 数据库名（默认从环境变量 MONGODB_DB 读取）
            collection: 集合名（默认 articles）
            connect_timeout: 连接超时时间（毫秒，默认 5000）
            server_selection_timeout: 服务器选择超时时间（毫秒，默认 5000）
        """
        self.uri = uri or os.getenv("MONGODB_URI")
        self.database_name = database or os.getenv("MONGODB_DB")
        self.collection_name = collection
        self.connect_timeout = connect_timeout
        self.server_selection_timeout = server_selection_timeout
        
        if self.uri and self.database_name:
            self._create_client()
    
    def _create_client(self):
        """创建 MongoDB 客户端连接"""
        try:
            self._client = MongoClient(
                self.uri,
                connectTimeoutMS=self.connect_timeout,
                serverSelectionTimeoutMS=self.server_selection_timeout,
            )
            # 测试连接
            self._client.admin.command('ping')
        except Exception as e:
            print(f"[MongoDB] 创建连接失败: {e}")
            self._client = None
    
    @property
    def client(self) -> Optional[MongoClient]:
        """获取 MongoDB 客户端"""
        return self._client
    
    @property
    def db(self):
        """获取数据库对象"""
        if self._client is not None and self.database_name:
            return self._client[self.database_name]
        return None
    
    @property
    def collection(self):
        """获取集合对象"""
        db = self.db
        if db is not None:
            return db[self.collection_name]
        return None
    
    @classmethod
    def from_env(cls) -> 'MongoDBManager':
        """
        从环境变量创建 MongoDB 管理器实例
        
        环境变量：
            MONGODB_URI: MongoDB 连接 URI
            MONGODB_DB: 数据库名
            MONGODB_COLLECTION: 集合名（可选，默认 articles）
        """
        return cls(
            uri=os.getenv("MONGODB_URI"),
            database=os.getenv("MONGODB_DB"),
            collection=os.getenv("MONGODB_COLLECTION", "articles"),
        )
    
    def test_connection(self) -> bool:
        """
        测试 MongoDB 连接是否可用
        
        Returns:
            连接是否成功
        """
        if not self._client:
            return False
        
        try:
            self._client.admin.command('ping')
            return True
        except (ConnectionFailure, OperationFailure) as e:
            print(f"[MongoDB] 连接测试失败: {e}")
            return False
    
    def get_masked_uri(self) -> str:
        """
        获取脱敏后的连接 URI（隐藏密码）
        
        Returns:
            脱敏后的 URI
        """
        if not self.uri:
            return "未配置"
        
        # 简单脱敏：隐藏密码部分
        if "@" in self.uri:
            parts = self.uri.split("@")
            if ":" in parts[0]:
                user_pass = parts[0].split("://")
                if len(user_pass) > 1:
                    user = user_pass[1].split(":")[0]
                    return f"{user_pass[0]}://{user}:****@{parts[1]}"
        return self.uri
    
    def save_article(
        self,
        task_id: str,
        title: str = "",
        link: str = "",
        content: str = "",
        source_url: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        保存文章到 MongoDB，使用链接哈希进行去重判断
        
        Args:
            task_id: 任务 ID
            title: 文章标题
            link: 文章链接
            content: 文章内容
            source_url: 来源 URL
            extra: 额外数据（字典格式）
            
        Returns:
            插入的文档 ID（字符串格式），失败返回 None；如果已存在则返回现有 ID
        """
        from crawler.utils.hash_helper import HashHelper
        
        if self.collection is None:
            raise RuntimeError("MongoDB collection not initialized")
        
        # 计算链接哈希和内容哈希
        link_hash = HashHelper.get_link_hash(link)
        content_hash = HashHelper.get_content_hash(content)
        
        try:
            # 1. 检查链接是否已存在（去重）
            if link_hash:
                existing = self.collection.find_one({"link_hash": link_hash})
                if existing:
                    print(f"[MongoDB] 链接已存在，跳过保存: {link}")
                    return str(existing["_id"])
            
            # 2. 构建文档（包含哈希值）
            document = {
                "task_id": str(task_id),
                "title": title or "",
                "link": link or "",
                "link_hash": link_hash,
                "content": content or "",
                "content_hash": content_hash,
                "source_url": source_url or "",
                "extra": extra or {},
                "created_at": TimezoneHelper.get_now(with_tz=False),
                "updated_at": TimezoneHelper.get_now(with_tz=False),
            }
            
            # 3. 插入文档
            result = self.collection.insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            print(f"[MongoDB] 保存文章失败: {e}")
            return None
    
    def get_article_by_id(self, article_id: str) -> Optional[Dict[str, Any]]:
        """
        根据文章 ID 获取文章详情
        
        Args:
            article_id: 文章 ID（MongoDB ObjectId 的字符串形式）
            
        Returns:
            文章数据字典，如果不存在返回 None
        """
        if self.collection is None:
            return None
        
        from bson.objectid import ObjectId
        
        try:
            oid = ObjectId(article_id)
            document = self.collection.find_one({"_id": oid})
            if document:
                document["id"] = str(document["_id"])
                del document["_id"]
            return document
        except Exception as e:
            print(f"[MongoDB] 查询文章失败: {e}")
            return None
    
    def get_articles_by_task_id(
        self,
        task_id: str,
        limit: int = 100,
        skip: int = 0,
    ) -> list:
        """
        根据任务 ID 获取文章列表
        
        Args:
            task_id: 任务 ID
            limit: 返回数量限制
            skip: 跳过数量
            
        Returns:
            文章列表
        """
        if self.collection is None:
            return []
        
        try:
            cursor = self.collection.find(
                {"task_id": str(task_id)}
            ).sort("created_at", -1).skip(skip).limit(limit)
            
            articles = []
            for doc in cursor:
                doc["id"] = str(doc["_id"])
                del doc["_id"]
                articles.append(doc)
            return articles
        except Exception as e:
            print(f"[MongoDB] 查询文章列表失败: {e}")
            return []
    
    def count_articles_by_task_id(self, task_id: str) -> int:
        """
        统计指定任务的文章数量
        
        Args:
            task_id: 任务 ID
            
        Returns:
            文章数量
        """
        if self.collection is None:
            return 0
        
        try:
            return self.collection.count_documents({"task_id": str(task_id)})
        except Exception as e:
            print(f"[MongoDB] 统计文章数量失败: {e}")
            return 0
    
    def delete_article(self, article_id: str) -> bool:
        """
        删除指定文章
        
        Args:
            article_id: 文章 ID
            
        Returns:
            是否删除成功
        """
        if self.collection is None:
            return False
        
        from bson.objectid import ObjectId
        
        try:
            oid = ObjectId(article_id)
            result = self.collection.delete_one({"_id": oid})
            return result.deleted_count > 0
        except Exception as e:
            print(f"[MongoDB] 删除文章失败: {e}")
            return False
    
    def delete_articles_by_task_id(self, task_id: str) -> int:
        """
        删除指定任务的所有文章
        
        Args:
            task_id: 任务 ID
            
        Returns:
            删除的文章数量
        """
        if self.collection is None:
            return 0
        
        try:
            result = self.collection.delete_many({"task_id": str(task_id)})
            return result.deleted_count
        except Exception as e:
            print(f"[MongoDB] 删除任务文章失败: {e}")
            return 0
    
    def close(self):
        """关闭 MongoDB 连接"""
        if self._client is not None:
            self._client.close()
            self._client = None
