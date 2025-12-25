"""
Scrapy 代理中间件
支持固定代理和动态代理
"""
from typing import Optional
from scrapy import Request, Spider
from scrapy.http import Response
from crawler.utils.proxy_manager import ProxyManager


class ProxyMiddleware:
    """代理中间件，为 Scrapy 请求设置代理"""
    
    def __init__(self):
        self.proxy_manager: Optional[ProxyManager] = None
    
    @classmethod
    def from_crawler(cls, crawler):
        """从 crawler 创建中间件实例"""
        middleware = cls()
        return middleware
    
    def spider_opened(self, spider: Spider):
        """爬虫启动时初始化代理管理器"""
        self.proxy_manager = ProxyManager.from_env()
        
        if self.proxy_manager.is_enabled():
            spider.logger.info(f"代理已启用，模式: {self.proxy_manager.mode}")
            if self.proxy_manager.mode == "dynamic":
                spider.logger.info(f"动态代理API: {self.proxy_manager.dynamic_api}")
                spider.logger.info(f"刷新间隔: {self.proxy_manager.refresh_interval}秒")
        else:
            spider.logger.info("不使用代理")
    
    def process_request(self, request: Request, spider: Spider):
        """处理请求，设置代理"""
        if not self.proxy_manager or not self.proxy_manager.is_enabled():
            return None
        
        # 获取代理配置
        proxies = self.proxy_manager.get_proxies()
        
        if proxies:
            # Scrapy 使用 request.meta['proxy'] 设置代理
            # 优先使用 https 代理，如果没有则使用 http 代理
            proxy = proxies.get("https") or proxies.get("http")
            
            if proxy:
                request.meta["proxy"] = proxy
                # 如果是第一次设置代理，记录日志
                if not hasattr(spider, "_proxy_logged"):
                    spider.logger.info(f"使用代理: {self._mask_proxy(proxy)}")
                    spider._proxy_logged = True
        
        return None
    
    def _mask_proxy(self, proxy: str) -> str:
        """脱敏显示代理地址"""
        if "@" in proxy:
            # 格式: http://user:pass@host:port
            parts = proxy.split("@")
            if len(parts) == 2:
                auth_part = parts[0]
                if ":" in auth_part:
                    scheme_user = auth_part.rsplit(":", 1)[0]
                    return f"{scheme_user}:****@{parts[1]}"
        
        return proxy
