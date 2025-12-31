"""数据库管理工具：统一管理 MySQL 连接和配置"""
import os
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from crawler.utils.timezone_helper import TimezoneHelper



class DatabaseManager:
    """MySQL 数据库管理器，提供统一的连接和操作接口"""
    
    _instance: Optional['DatabaseManager'] = None
    _engine: Optional[Engine] = None
    
    def __init__(
        self,
        user: Optional[str] = None,
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        charset: str = "utf8mb4",
        pool_size: int = 5,
        max_overflow: int = 5,
        auto_create: bool = True,
    ):
        """
        初始化数据库管理器
        
        Args:
            user: MySQL 用户名（默认从环境变量 MYSQL_USER 读取）
            password: MySQL 密码（默认从环境变量 MYSQL_PASSWORD 读取）
            host: MySQL 主机（默认从环境变量 MYSQL_HOST 读取，默认值 localhost）
            port: MySQL 端口（默认从环境变量 MYSQL_PORT 读取，默认值 3306）
            database: 数据库名（默认从环境变量 MYSQL_DB 读取）
            charset: 字符集（默认 utf8mb4）
            pool_size: 连接池大小（默认 5）
            max_overflow: 最大溢出连接数（默认 5）
            auto_create: 是否自动创建引擎（默认 True）
        """
        self.user = user or os.getenv("MYSQL_USER")
        self.password = password or os.getenv("MYSQL_PASSWORD")
        self.host = host or os.getenv("MYSQL_HOST", "localhost")
        self.port = port or int(os.getenv("MYSQL_PORT", "3306"))
        self.database = database or os.getenv("MYSQL_DB")
        self.charset = charset or os.getenv("MYSQL_CHARSET", "utf8mb4")
        self.pool_size = pool_size or int(os.getenv("MYSQL_POOL_SIZE", "5"))
        self.max_overflow = max_overflow or int(os.getenv("MYSQL_POOL_MAX_OVERFLOW", "5"))
        
        if auto_create:
            self._engine = self._create_engine()
    
    def _create_engine(self) -> Optional[Engine]:
        """创建数据库引擎"""
        if not all([self.user, self.password, self.database]):
            return None
        
        try:
            engine = create_engine(
                f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?charset={self.charset}",
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
            return engine
        except Exception as e:
            raise RuntimeError(f"Failed to create database engine: {e}")
    
    @property
    def engine(self) -> Optional[Engine]:
        """获取数据库引擎"""
        return self._engine
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接数据库"""
        if not self._engine:
            return False
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            if not self._engine:
                return False
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"[DatabaseManager] 连接测试失败: {e}")
            return False
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None):
        """
        执行查询语句
        
        Args:
            query: SQL 查询语句
            params: 查询参数
            
        Returns:
            查询结果
        """
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        with self._engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            return result
    
    def execute_insert(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """
        执行插入语句
        
        Args:
            query: SQL 插入语句
            params: 插入参数
            
        Returns:
            插入的行 ID
        """
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        with self._engine.begin() as conn:
            result = conn.execute(text(query), params or {})
            return result.lastrowid
    
    def save_article(
        self,
        task_id: str,
        title: str = "",
        link: str = "",
        content: str = "",
        source_url: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        保存文章到数据库（文章主表 + 内容表）
        使用链接哈希和内容哈希进行去重判断
        
        Args:
            task_id: 任务 ID
            title: 文章标题
            link: 文章链接
            content: 文章内容
            source_url: 来源 URL
            extra: 额外数据（JSON 格式）
            
        Returns:
            插入的文章 ID（如果已存在则返回现有 ID）
        """
        import json
        from crawler.utils.hash_helper import HashHelper
        
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        # 计算链接哈希和内容哈希
        link_hash = HashHelper.get_link_hash(link)
        content_hash = HashHelper.get_content_hash(content)
        
        # 使用事务保证数据一致性
        with self._engine.begin() as conn:
            # 1. 检查链接是否已存在（去重）
            if link_hash:
                check_query = "SELECT id FROM articles WHERE link_hash = :link_hash LIMIT 1"
                result = conn.execute(text(check_query), {"link_hash": link_hash})
                existing = result.fetchone()
                if existing:
                    print(f"[DatabaseManager] 链接已存在，跳过保存: {link}")
                    return existing[0]
            
            # 2. 插入文章主表
            article_query = """
                INSERT INTO articles(task_id, title, link, link_hash, source_url, extra, created_at)
                VALUES (:task_id, :title, :link, :link_hash, :source_url, :extra, :created_at)
            """
            article_params = {
                "task_id": str(task_id),
                "title": title or "",
                "link": link or "",
                "link_hash": link_hash,
                "source_url": source_url or "",
                "extra": json.dumps(extra or {}, ensure_ascii=False),
                "created_at": TimezoneHelper.get_now(with_tz=False),
            }
            
            result = conn.execute(text(article_query), article_params)
            article_id = result.lastrowid
            
            # 3. 如果有内容，插入到 article_contents 表（带内容哈希）
            if content:
                content_query = """
                    INSERT INTO article_contents(article_id, content, content_hash, created_at)
                    VALUES (:article_id, :content, :content_hash, :created_at)
                """
                content_params = {
                    "article_id": article_id,
                    "content": content,
                    "content_hash": content_hash,
                    "created_at": TimezoneHelper.get_now(with_tz=False),
                }
                conn.execute(text(content_query), content_params)
            
            return article_id
    
    def get_article_by_id(self, article_id: int, include_content: bool = True) -> Optional[Dict[str, Any]]:
        """
        根据文章 ID 获取文章详情
        
        Args:
            article_id: 文章 ID
            include_content: 是否包含文章内容（默认 True）
            
        Returns:
            文章数据字典，如果不存在返回 None
        """
        import json
        
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        with self._engine.connect() as conn:
            # 查询文章主表
            article_query = """
                SELECT id, task_id, title, link, source_url, extra, created_at
                FROM articles
                WHERE id = :article_id
            """
            result = conn.execute(text(article_query), {"article_id": article_id})
            row = result.fetchone()
            
            if not row:
                return None
            
            article = {
                "id": row[0],
                "task_id": row[1],
                "title": row[2],
                "link": row[3],
                "source_url": row[4],
                "extra": json.loads(row[5]) if row[5] else {},
                "created_at": row[6],
            }
            
            # 如果需要，查询文章内容
            if include_content:
                content_query = """
                    SELECT content
                    FROM article_contents
                    WHERE article_id = :article_id
                """
                content_result = conn.execute(text(content_query), {"article_id": article_id})
                content_row = content_result.fetchone()
                article["content"] = content_row[0] if content_row else ""
            
            return article
    
    def get_articles_by_task_id(
        self,
        task_id: str,
        include_content: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Dict[str, Any]]:
        """
        根据任务 ID 获取文章列表
        
        Args:
            task_id: 任务 ID
            include_content: 是否包含文章内容（默认 False，避免数据量过大）
            limit: 返回数量限制（默认 100）
            offset: 偏移量（默认 0）
            
        Returns:
            文章列表
        """
        import json
        
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        with self._engine.connect() as conn:
            # 查询文章列表
            query = """
                SELECT id, task_id, title, link, source_url, extra, created_at
                FROM articles
                WHERE task_id = :task_id
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """
            result = conn.execute(text(query), {
                "task_id": str(task_id),
                "limit": limit,
                "offset": offset,
            })
            
            articles = []
            for row in result:
                article = {
                    "id": row[0],
                    "task_id": row[1],
                    "title": row[2],
                    "link": row[3],
                    "source_url": row[4],
                    "extra": json.loads(row[5]) if row[5] else {},
                    "created_at": row[6],
                }
                
                # 如果需要，查询文章内容
                if include_content:
                    content_query = """
                        SELECT content
                        FROM article_contents
                        WHERE article_id = :article_id
                    """
                    content_result = conn.execute(text(content_query), {"article_id": article["id"]})
                    content_row = content_result.fetchone()
                    article["content"] = content_row[0] if content_row else ""
                
                articles.append(article)
            
            return articles
    
    def count_articles_by_task_id(self, task_id: str) -> int:
        """
        统计指定任务的文章数量
        
        Args:
            task_id: 任务 ID
            
        Returns:
            文章数量
        """
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        with self._engine.connect() as conn:
            query = """
                SELECT COUNT(*) as total
                FROM articles
                WHERE task_id = :task_id
            """
            result = conn.execute(text(query), {"task_id": str(task_id)})
            row = result.fetchone()
            return row[0] if row else 0
    
    def get_all_articles(
        self,
        include_content: bool = False,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        order_direction: str = "DESC",
    ) -> list[Dict[str, Any]]:
        """
        获取所有文章列表
        
        Args:
            include_content: 是否包含文章内容（默认 False）
            limit: 返回数量限制（默认 100）
            offset: 偏移量（默认 0）
            order_by: 排序字段（默认 created_at）
            order_direction: 排序方向（ASC/DESC，默认 DESC）
            
        Returns:
            文章列表
        """
        import json
        
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        # 验证排序字段和方向
        allowed_order_fields = ["id", "task_id", "title", "created_at"]
        if order_by not in allowed_order_fields:
            order_by = "created_at"
        
        if order_direction.upper() not in ["ASC", "DESC"]:
            order_direction = "DESC"
        
        with self._engine.connect() as conn:
            query = f"""
                SELECT id, task_id, title, link, source_url, extra, created_at
                FROM articles
                ORDER BY {order_by} {order_direction}
                LIMIT :limit OFFSET :offset
            """
            result = conn.execute(text(query), {
                "limit": limit,
                "offset": offset,
            })
            
            articles = []
            for row in result:
                article = {
                    "id": row[0],
                    "task_id": row[1],
                    "title": row[2],
                    "link": row[3],
                    "source_url": row[4],
                    "extra": json.loads(row[5]) if row[5] else {},
                    "created_at": row[6],
                }
                
                # 如果需要，查询文章内容
                if include_content:
                    content_query = """
                        SELECT content
                        FROM article_contents
                        WHERE article_id = :article_id
                    """
                    content_result = conn.execute(text(content_query), {"article_id": article["id"]})
                    content_row = content_result.fetchone()
                    article["content"] = content_row[0] if content_row else ""
                
                articles.append(article)
            
            return articles
    
    def count_all_articles(self) -> int:
        """
        统计所有文章总数
        
        Returns:
            文章总数
        """
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        with self._engine.connect() as conn:
            query = "SELECT COUNT(*) as total FROM articles"
            result = conn.execute(text(query))
            row = result.fetchone()
            return row[0] if row else 0
    
    def delete_article(self, article_id: int) -> bool:
        """
        删除指定文章（包括文章内容）
        
        Args:
            article_id: 文章 ID
            
        Returns:
            是否删除成功
        """
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        try:
            with self._engine.begin() as conn:
                # 1. 删除文章内容
                content_query = """
                    DELETE FROM article_contents
                    WHERE article_id = :article_id
                """
                conn.execute(text(content_query), {"article_id": article_id})
                
                # 2. 删除文章主表
                article_query = """
                    DELETE FROM articles
                    WHERE id = :article_id
                """
                result = conn.execute(text(article_query), {"article_id": article_id})
                
                return result.rowcount > 0
        except Exception as e:
            print(f"[DatabaseManager] 删除文章失败: {e}")
            return False
    
    def delete_articles_by_task_id(self, task_id: str) -> int:
        """
        删除指定任务的所有文章
        
        Args:
            task_id: 任务 ID
            
        Returns:
            删除的文章数量
        """
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        try:
            with self._engine.begin() as conn:
                # 1. 获取该任务下的所有文章 ID
                get_ids_query = """
                    SELECT id FROM articles WHERE task_id = :task_id
                """
                result = conn.execute(text(get_ids_query), {"task_id": str(task_id)})
                article_ids = [row[0] for row in result]
                
                if not article_ids:
                    return 0
                
                # 2. 删除文章内容
                content_query = """
                    DELETE FROM article_contents
                    WHERE article_id IN :article_ids
                """
                conn.execute(text(content_query), {"article_ids": tuple(article_ids)})
                
                # 3. 删除文章主表
                article_query = """
                    DELETE FROM articles
                    WHERE task_id = :task_id
                """
                result = conn.execute(text(article_query), {"task_id": str(task_id)})
                
                return result.rowcount
        except Exception as e:
            print(f"[DatabaseManager] 批量删除文章失败: {e}")
            return 0
    
    def get_task_statistics(self) -> list[Dict[str, Any]]:
        """
        获取各任务的文章统计信息
        
        Returns:
            统计信息列表，每项包含 task_id, article_count, latest_created_at
        """
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        with self._engine.connect() as conn:
            query = """
                SELECT 
                    task_id,
                    COUNT(*) as article_count,
                    MAX(created_at) as latest_created_at
                FROM articles
                GROUP BY task_id
                ORDER BY latest_created_at DESC
            """
            result = conn.execute(text(query))
            
            statistics = []
            for row in result:
                statistics.append({
                    "task_id": row[0],
                    "article_count": row[1],
                    "latest_created_at": row[2],
                })
            
            return statistics
    
    def close(self):
        """关闭数据库连接"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
    
    @classmethod
    def get_instance(cls, **kwargs) -> 'DatabaseManager':
        """
        获取单例实例
        
        Args:
            **kwargs: 数据库配置参数
            
        Returns:
            DatabaseManager 实例
        """
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance
    
    @classmethod
    def from_env(cls) -> 'DatabaseManager':
        """从环境变量创建数据库管理器"""
        return cls()
    
    @classmethod
    def from_settings(cls, settings) -> 'DatabaseManager':
        """
        从 Scrapy settings 创建数据库管理器
        
        Args:
            settings: Scrapy settings 对象
            
        Returns:
            DatabaseManager 实例
        """
        return cls(
            user=settings.get("MYSQL_USER"),
            password=settings.get("MYSQL_PASSWORD"),
            host=settings.get("MYSQL_HOST", "localhost"),
            port=settings.getint("MYSQL_PORT", 3306),
            database=settings.get("MYSQL_DB"),
            charset=settings.get("MYSQL_CHARSET", "utf8mb4"),
            pool_size=settings.getint("MYSQL_POOL_SIZE", 5),
            max_overflow=settings.getint("MYSQL_POOL_MAX_OVERFLOW", 5),
        )
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        # 不关闭连接池，因为可能在其他地方使用
        pass
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<DatabaseManager(host={self.host}, port={self.port}, database={self.database})>"
