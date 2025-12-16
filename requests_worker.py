"""
使用 requests 库的请求工作器
从 Redis 读取待请求任务，发送 HTTP 请求，将结果保存到 Redis
"""
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional

import requests
from redis import Redis

from crawler.utils.env_loader import load_env_file

load_env_file()


class RequestsWorker:
    def __init__(
        self,
        redis_url: Optional[str] = None,
        start_key: Optional[str] = None,
        success_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        初始化请求工作器
        
        Args:
            redis_url: Redis 连接 URL
            start_key: 待请求任务队列键
            success_key: 成功结果队列键
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.start_key = start_key or os.getenv("SCRAPY_START_KEY", "fetch_spider:start_urls")
        self.success_key = success_key or os.getenv("SUCCESS_QUEUE_KEY", "fetch_spider:success")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # 调试信息：显示读取到的 REDIS_URL（隐藏密码）
        def _mask_password(url: str) -> str:
            """隐藏 Redis URL 中的密码"""
            if "@" in url:
                parts = url.split("@")
                if "://" in parts[0]:
                    protocol_part = parts[0]
                    if "://:" in protocol_part:
                        # redis://:password@host
                        return protocol_part.split("://")[0] + "://:***@" + parts[1]
                    elif "://" in protocol_part and ":" in protocol_part.split("://")[1]:
                        # redis://user:password@host
                        user_pass = protocol_part.split("://")[1]
                        user = user_pass.split(":")[0]
                        return protocol_part.split("://")[0] + f"://{user}:***@" + parts[1]
            return url
        
        print(f"[requests_worker] 读取 REDIS_URL: {_mask_password(redis_url)}")
        
        # 初始化 Redis 连接并测试
        try:
            self.redis_cli = Redis.from_url(redis_url, decode_responses=False)
            # 测试连接
            self.redis_cli.ping()
            print(f"[requests_worker] ✓ Redis 连接成功")
        except Exception as e:
            error_msg = str(e)
            if "Authentication required" in error_msg or "NOAUTH" in error_msg:
                print(f"[requests_worker] ❌ Redis 认证失败！")
                print(f"[requests_worker] 使用的 REDIS_URL: {_mask_password(redis_url)}")
                print(f"[requests_worker] 请检查：")
                print(f"[requests_worker]   1. .env 文件是否在项目根目录")
                print(f"[requests_worker]   2. REDIS_URL 格式是否正确")
                print(f"[requests_worker]   3. 密码是否正确（格式: redis://:password@host:port/db）")
                # 检查环境变量
                env_redis_url = os.getenv("REDIS_URL")
                if env_redis_url and env_redis_url != redis_url:
                    print(f"[requests_worker]   注意: 系统环境变量 REDIS_URL 与读取的值不同")
                    print(f"[requests_worker]   环境变量: {_mask_password(env_redis_url)}")
                    print(f"[requests_worker]   实际使用: {_mask_password(redis_url)}")
            else:
                print(f"[requests_worker] ❌ Redis 连接失败: {error_msg}")
                print(f"[requests_worker] 请检查 Redis 服务是否运行，以及 REDIS_URL 配置是否正确")
            raise
        
        # 创建 requests Session 以复用连接
        self.session = requests.Session()
        # 设置默认 User-Agent
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
        })

    def run_forever(self, sleep_seconds: float = 1.0):
        """
        持续运行，从 Redis 队列读取任务并处理
        
        Args:
            sleep_seconds: 队列为空时的休眠时间（秒）
        """
        print(f"[requests_worker] 启动，监听队列: {self.start_key}")
        print(f"[requests_worker] 结果保存到: {self.success_key}")
        print(f"[requests_worker] 超时设置: {self.timeout}秒")
        print(f"[requests_worker] 最大重试: {self.max_retries}次")
        print("-" * 60)
        
        while True:
            try:
                # 从 Redis 队列阻塞读取任务（超时 5 秒）
                result = self.redis_cli.brpop(self.start_key, timeout=5)
                if not result:
                    time.sleep(sleep_seconds)
                    continue
                
                _, data = result
                payload = json.loads(data)
                self._process_request(payload)
                
            except KeyboardInterrupt:
                print("\n[requests_worker] 收到中断信号，正在退出...")
                break
            except Exception as exc:
                error_msg = str(exc)
                if "Authentication required" in error_msg or "NOAUTH" in error_msg:
                    print(f"[requests_worker] ❌ Redis 认证失败！")
                    print(f"[requests_worker] 请检查 .env 文件中的 REDIS_URL 配置")
                    print(f"[requests_worker] 格式: redis://:password@host:port/db")
                    print(f"[requests_worker] 错误详情: {error_msg}")
                    print(f"[requests_worker] 程序退出")
                    break
                else:
                    print(f"[requests_worker] 处理任务时出错: {error_msg}")
                    time.sleep(sleep_seconds)

    def _process_request(self, payload: Dict[str, Any]):
        """
        处理单个请求任务
        
        Args:
            payload: 请求任务数据，包含 url, method, headers, meta 等
        """
        url = payload.get("url")
        method = payload.get("method", "GET").upper()
        headers = payload.get("headers") or {}
        meta = payload.get("meta") or {}
        params = payload.get("params")
        
        if not url:
            print(f"[requests_worker] 跳过无效任务（缺少 URL）: {payload}")
            return
        
        print(f"[requests_worker] 处理请求: {method} {url}")
        
        # 发送请求（带重试）
        response = None
        error = None
        
        for attempt in range(self.max_retries):
            try:
                # 合并 headers
                request_headers = {**self.session.headers, **headers}
                
                # 发送请求
                if method == "GET":
                    response = self.session.get(
                        url,
                        headers=request_headers,
                        params=params,
                        timeout=self.timeout,
                        allow_redirects=True,
                    )
                elif method == "POST":
                    data = payload.get("data")
                    json_data = payload.get("json")
                    response = self.session.post(
                        url,
                        headers=request_headers,
                        params=params,
                        data=data,
                        json=json_data,
                        timeout=self.timeout,
                        allow_redirects=True,
                    )
                else:
                    # 支持其他方法
                    response = self.session.request(
                        method,
                        url,
                        headers=request_headers,
                        params=params,
                        data=payload.get("data"),
                        json=payload.get("json"),
                        timeout=self.timeout,
                        allow_redirects=True,
                    )
                
                # 请求成功，跳出重试循环
                break
                
            except requests.exceptions.Timeout:
                error = f"请求超时（{self.timeout}秒）"
                if attempt < self.max_retries - 1:
                    print(f"[requests_worker] {error}，{self.retry_delay}秒后重试 ({attempt + 1}/{self.max_retries})")
                    time.sleep(self.retry_delay)
                else:
                    print(f"[requests_worker] {error}，已达最大重试次数")
            except requests.exceptions.RequestException as e:
                error = f"请求异常: {str(e)}"
                if attempt < self.max_retries - 1:
                    print(f"[requests_worker] {error}，{self.retry_delay}秒后重试 ({attempt + 1}/{self.max_retries})")
                    time.sleep(self.retry_delay)
                else:
                    print(f"[requests_worker] {error}，已达最大重试次数")
            except Exception as e:
                error = f"未知错误: {str(e)}"
                print(f"[requests_worker] {error}")
                break
        
        # 构建结果记录
        record = {
            "url": url,
            "status": response.status_code if response else 0,
            "headers": dict(response.headers) if response else {},
            "body": response.text if response else "",
            "meta": meta,
            "requested_at": datetime.utcnow().isoformat(),
            "error": error if error else None,
        }
        
        # 保存到 Redis 成功队列
        self.redis_cli.lpush(self.success_key, json.dumps(record, ensure_ascii=False))
        
        if response:
            print(f"[requests_worker] ✓ 请求成功: {url} (状态码: {response.status_code}, 长度: {len(response.text)} 字节)")
        else:
            print(f"[requests_worker] ✗ 请求失败: {url} ({error})")

    def close(self):
        """关闭 Session"""
        self.session.close()


def main():
    """主函数：直接从 .env 文件读取配置"""
    # 从环境变量读取配置（.env 文件已自动加载）
    timeout = int(os.getenv("REQUESTS_TIMEOUT", "30"))
    max_retries = int(os.getenv("REQUESTS_MAX_RETRIES", "3"))
    retry_delay = float(os.getenv("REQUESTS_RETRY_DELAY", "1.0"))
    sleep_seconds = float(os.getenv("REQUESTS_SLEEP", "1.0"))
    
    worker = RequestsWorker(
        redis_url=None,  # 使用环境变量中的 REDIS_URL
        start_key=None,  # 使用环境变量中的 SCRAPY_START_KEY
        success_key=None,  # 使用环境变量中的 SUCCESS_QUEUE_KEY
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay,
    )
    
    try:
        worker.run_forever(sleep_seconds=sleep_seconds)
    finally:
        worker.close()


if __name__ == "__main__":
    main()

