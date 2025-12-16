"""
数据库管理工具：统一管理 MySQL 连接和配置
"""
import os
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


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
        
        Args:
            task_id: 任务 ID
            title: 文章标题
            link: 文章链接
            content: 文章内容
            source_url: 来源 URL
            extra: 额外数据（JSON 格式）
            
        Returns:
            插入的文章 ID
        """
        import json
        
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        
        # 使用事务保证数据一致性
        with self._engine.begin() as conn:
            # 1. 插入文章主表（不包含 content）
            article_query = """
                INSERT INTO articles(task_id, title, link, source_url, extra, created_at)
                VALUES (:task_id, :title, :link, :source_url, :extra, :created_at)
            """
            article_params = {
                "task_id": str(task_id),
                "title": title or "",
                "link": link or "",
                "source_url": source_url or "",
                "extra": json.dumps(extra or {}, ensure_ascii=False),
                "created_at": datetime.utcnow(),
            }
            
            result = conn.execute(text(article_query), article_params)
            article_id = result.lastrowid
            
            # 2. 如果有内容，插入到 article_contents 表
            if content:
                content_query = """
                    INSERT INTO article_contents(article_id, content, created_at)
                    VALUES (:article_id, :content, :created_at)
                """
                content_params = {
                    "article_id": article_id,
                    "content": content,
                    "created_at": datetime.utcnow(),
                }
                conn.execute(text(content_query), content_params)
            
            return article_id
    
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
