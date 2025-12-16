"""
Redis 管理工具：统一管理 Redis 连接和配置
"""
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from redis import Redis


class RedisManager:
    """Redis 管理器，提供统一的连接和操作接口"""
    
    _instance: Optional['RedisManager'] = None
    _client: Optional[Redis] = None
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        password: Optional[str] = None,
        decode_responses: bool = False,
        auto_connect: bool = True,
    ):
        """
        初始化 Redis 管理器
        
        Args:
            redis_url: Redis 连接 URL（格式: redis://[:password@]host:port/db）
            host: Redis 主机（当 redis_url 为 None 时使用）
            port: Redis 端口（当 redis_url 为 None 时使用）
            db: Redis 数据库编号（当 redis_url 为 None 时使用）
            password: Redis 密码（当 redis_url 为 None 时使用）
            decode_responses: 是否自动解码响应为字符串（默认 False，返回 bytes）
            auto_connect: 是否自动创建连接（默认 True）
        """
        # 优先使用 redis_url
        if redis_url is None:
            redis_url = os.getenv("REDIS_URL")
        
        # 如果没有提供 redis_url，从其他参数或环境变量构建
        if redis_url:
            self.redis_url = redis_url
            # 解析 URL 获取连接信息
            parsed = urlparse(redis_url)
            self.host = parsed.hostname or "localhost"
            self.port = parsed.port or 6379
            self.db = int(parsed.path.lstrip('/')) if parsed.path and parsed.path != '/' else 0
            self.password = parsed.password
        else:
            self.host = host or os.getenv("REDIS_HOST", "localhost")
            self.port = port or int(os.getenv("REDIS_PORT", "6379"))
            self.db = db if db is not None else int(os.getenv("REDIS_DB", "0"))
            self.password = password or os.getenv("REDIS_PASSWORD")
            # 构建 redis_url
            if self.password:
                self.redis_url = f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
            else:
                self.redis_url = f"redis://{self.host}:{self.port}/{self.db}"
        
        self.decode_responses = decode_responses
        
        if auto_connect:
            self._client = self._create_client()
    
    def _create_client(self) -> Optional[Redis]:
        """创建 Redis 客户端"""
        try:
            client = Redis.from_url(
                self.redis_url,
                decode_responses=self.decode_responses,
            )
            return client
        except Exception as e:
            raise RuntimeError(f"Failed to create Redis client: {e}")
    
    @property
    def client(self) -> Optional[Redis]:
        """获取 Redis 客户端"""
        return self._client
    
    @property
    def is_connected(self) -> bool:
        """检查是否已连接 Redis"""
        if not self._client:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            return False
    
    def test_connection(self) -> bool:
        """测试 Redis 连接"""
        try:
            if not self._client:
                return False
            self._client.ping()
            return True
        except Exception as e:
            print(f"[RedisManager] 连接测试失败: {e}")
            return False
    
    def ping(self) -> bool:
        """
        Ping Redis 服务器
        
        Returns:
            bool: 连接是否正常
        """
        return self.test_connection()
    
    def lpush(self, key: str, *values: Any) -> int:
        """
        将值推入列表左侧
        
        Args:
            key: 列表键
            *values: 要推入的值
            
        Returns:
            int: 推入后列表的长度
        """
        if not self._client:
            raise RuntimeError("Redis client not initialized")
        return self._client.lpush(key, *values)
    
    def rpush(self, key: str, *values: Any) -> int:
        """
        将值推入列表右侧
        
        Args:
            key: 列表键
            *values: 要推入的值
            
        Returns:
            int: 推入后列表的长度
        """
        if not self._client:
            raise RuntimeError("Redis client not initialized")
        return self._client.rpush(key, *values)
    
    def brpop(self, keys: List[str], timeout: int = 0):
        """
        阻塞式从列表右侧弹出元素
        
        Args:
            keys: 列表键（可以是多个）
            timeout: 超时时间（秒），0 表示永久阻塞
            
        Returns:
            tuple: (key, value) 或 None（超时）
        """
        if not self._client:
            raise RuntimeError("Redis client not initialized")
        return self._client.brpop(keys, timeout=timeout)
    
    def blpop(self, keys: List[str], timeout: int = 0):
        """
        阻塞式从列表左侧弹出元素
        
        Args:
            keys: 列表键（可以是多个）
            timeout: 超时时间（秒），0 表示永久阻塞
            
        Returns:
            tuple: (key, value) 或 None（超时）
        """
        if not self._client:
            raise RuntimeError("Redis client not initialized")
        return self._client.blpop(keys, timeout=timeout)
    
    def get(self, key: str) -> Any:
        """获取键的值"""
        if not self._client:
            raise RuntimeError("Redis client not initialized")
        return self._client.get(key)
    
    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """
        设置键的值
        
        Args:
            key: 键
            value: 值
            ex: 过期时间（秒）
            
        Returns:
            bool: 是否设置成功
        """
        if not self._client:
            raise RuntimeError("Redis client not initialized")
        return self._client.set(key, value, ex=ex)
    
    def delete(self, *keys: str) -> int:
        """
        删除一个或多个键
        
        Args:
            *keys: 要删除的键
            
        Returns:
            int: 删除的键数量
        """
        if not self._client:
            raise RuntimeError("Redis client not initialized")
        return self._client.delete(*keys)
    
    def exists(self, *keys: str) -> int:
        """
        检查键是否存在
        
        Args:
            *keys: 要检查的键
            
        Returns:
            int: 存在的键数量
        """
        if not self._client:
            raise RuntimeError("Redis client not initialized")
        return self._client.exists(*keys)
    
    def llen(self, key: str) -> int:
        """
        获取列表长度
        
        Args:
            key: 列表键
            
        Returns:
            int: 列表长度
        """
        if not self._client:
            raise RuntimeError("Redis client not initialized")
        return self._client.llen(key)
    
    def keys(self, pattern: str = "*") -> List[str]:
        """
        获取匹配模式的所有键
        
        Args:
            pattern: 匹配模式（默认 * 表示所有键）
            
        Returns:
            List[str]: 匹配的键列表
        """
        if not self._client:
            raise RuntimeError("Redis client not initialized")
        return self._client.keys(pattern)
    
    def flushdb(self) -> bool:
        """清空当前数据库"""
        if not self._client:
            raise RuntimeError("Redis client not initialized")
        return self._client.flushdb()
    
    def close(self):
        """关闭 Redis 连接"""
        if self._client:
            self._client.close()
            self._client = None
    
    @classmethod
    def get_instance(cls, **kwargs) -> 'RedisManager':
        """
        获取单例实例
        
        Args:
            **kwargs: Redis 配置参数
            
        Returns:
            RedisManager 实例
        """
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance
    
    @classmethod
    def from_env(cls, decode_responses: bool = False) -> 'RedisManager':
        """
        从环境变量创建 Redis 管理器
        
        Args:
            decode_responses: 是否自动解码响应为字符串
            
        Returns:
            RedisManager 实例
        """
        return cls(decode_responses=decode_responses)
    
    @classmethod
    def from_url(cls, redis_url: str, decode_responses: bool = False) -> 'RedisManager':
        """
        从 URL 创建 Redis 管理器
        
        Args:
            redis_url: Redis 连接 URL
            decode_responses: 是否自动解码响应为字符串
            
        Returns:
            RedisManager 实例
        """
        return cls(redis_url=redis_url, decode_responses=decode_responses)
    
    @classmethod
    def from_settings(cls, settings, decode_responses: bool = False) -> 'RedisManager':
        """
        从 Scrapy settings 创建 Redis 管理器
        
        Args:
            settings: Scrapy settings 对象
            decode_responses: 是否自动解码响应为字符串
            
        Returns:
            RedisManager 实例
        """
        redis_url = settings.get("REDIS_URL")
        return cls(redis_url=redis_url, decode_responses=decode_responses)
    
    def get_masked_url(self) -> str:
        """
        获取隐藏密码的 Redis URL（用于日志显示）
        
        Returns:
            str: 隐藏密码后的 URL
        """
        if self.password:
            return f"redis://:***@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        # 不关闭连接，因为可能在其他地方使用
        pass
    
    def __repr__(self) -> str:
        """字符串表示"""
        return f"<RedisManager(host={self.host}, port={self.port}, db={self.db})>"
