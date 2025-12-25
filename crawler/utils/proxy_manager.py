"""
代理管理器
支持固定代理和动态代理两种模式
"""
import json
import os
import time
from typing import Dict, Optional, Any
import requests


class ProxyManager:
    """代理管理器，支持固定代理和动态代理"""
    
    def __init__(
        self,
        mode: str = "static",
        http_proxy: Optional[str] = None,
        https_proxy: Optional[str] = None,
        socks_proxy: Optional[str] = None,
        dynamic_api: Optional[str] = None,
        dynamic_api_method: str = "GET",
        dynamic_api_headers: Optional[Dict[str, str]] = None,
        refresh_interval: int = 0,
    ):
        """
        初始化代理管理器
        
        Args:
            mode: 代理模式，static（固定代理）或 dynamic（动态代理）
            http_proxy: HTTP 代理地址
            https_proxy: HTTPS 代理地址
            socks_proxy: SOCKS5 代理地址
            dynamic_api: 动态代理 API 地址
            dynamic_api_method: 动态代理 API 请求方法
            dynamic_api_headers: 动态代理 API 请求头
            refresh_interval: 动态代理刷新间隔（秒），0 表示每次都获取新代理
        """
        self.mode = mode.lower()
        self.http_proxy = http_proxy
        self.https_proxy = https_proxy
        self.socks_proxy = socks_proxy
        self.dynamic_api = dynamic_api
        self.dynamic_api_method = dynamic_api_method.upper()
        self.dynamic_api_headers = dynamic_api_headers or {}
        self.refresh_interval = refresh_interval
        
        # 动态代理缓存
        self._cached_proxy: Optional[Dict[str, str]] = None
        self._last_fetch_time: float = 0
        
    @classmethod
    def from_env(cls) -> "ProxyManager":
        """从环境变量创建代理管理器"""
        mode = os.getenv("PROXY_MODE", "static")
        
        # 固定代理配置
        http_proxy = os.getenv("HTTP_PROXY", "")
        https_proxy = os.getenv("HTTPS_PROXY", "")
        socks_proxy = os.getenv("SOCKS_PROXY", "")
        
        # 动态代理配置
        dynamic_api = os.getenv("DYNAMIC_PROXY_API", "")
        dynamic_api_method = os.getenv("DYNAMIC_PROXY_API_METHOD", "GET")
        dynamic_api_headers_str = os.getenv("DYNAMIC_PROXY_API_HEADERS", "")
        refresh_interval = int(os.getenv("DYNAMIC_PROXY_REFRESH_INTERVAL", "0"))
        
        # 解析动态代理请求头
        dynamic_api_headers = None
        if dynamic_api_headers_str:
            try:
                dynamic_api_headers = json.loads(dynamic_api_headers_str)
            except json.JSONDecodeError:
                print(f"[ProxyManager] 警告: DYNAMIC_PROXY_API_HEADERS 格式错误，忽略")
        
        return cls(
            mode=mode,
            http_proxy=http_proxy or None,
            https_proxy=https_proxy or None,
            socks_proxy=socks_proxy or None,
            dynamic_api=dynamic_api or None,
            dynamic_api_method=dynamic_api_method,
            dynamic_api_headers=dynamic_api_headers,
            refresh_interval=refresh_interval,
        )
    
    def get_proxies(self) -> Optional[Dict[str, str]]:
        """
        获取代理配置
        
        Returns:
            代理字典，格式: {"http": "http://...", "https": "https://..."}
            如果不使用代理，返回 None
        """
        if self.mode == "static":
            return self._get_static_proxies()
        elif self.mode == "dynamic":
            return self._get_dynamic_proxies()
        else:
            print(f"[ProxyManager] 警告: 未知的代理模式 '{self.mode}'，不使用代理")
            return None
    
    def _get_static_proxies(self) -> Optional[Dict[str, str]]:
        """获取固定代理配置"""
        proxies = {}
        
        if self.http_proxy:
            proxies["http"] = self.http_proxy
        if self.https_proxy:
            proxies["https"] = self.https_proxy
        
        # 如果配置了 SOCKS 代理，覆盖 HTTP/HTTPS
        if self.socks_proxy:
            proxies["http"] = self.socks_proxy
            proxies["https"] = self.socks_proxy
        
        return proxies if proxies else None
    
    def _get_dynamic_proxies(self) -> Optional[Dict[str, str]]:
        """获取动态代理配置"""
        if not self.dynamic_api:
            print(f"[ProxyManager] 警告: 动态代理模式已启用，但未配置 DYNAMIC_PROXY_API")
            return None
        
        # 检查缓存是否有效
        current_time = time.time()
        if (
            self._cached_proxy
            and self.refresh_interval > 0
            and (current_time - self._last_fetch_time) < self.refresh_interval
        ):
            return self._cached_proxy
        
        # 从 API 获取新代理
        try:
            if self.dynamic_api_method == "GET":
                response = requests.get(
                    self.dynamic_api,
                    headers=self.dynamic_api_headers,
                    timeout=10,
                )
            elif self.dynamic_api_method == "POST":
                response = requests.post(
                    self.dynamic_api,
                    headers=self.dynamic_api_headers,
                    timeout=10,
                )
            else:
                print(f"[ProxyManager] 错误: 不支持的请求方法 '{self.dynamic_api_method}'")
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # 解析代理数据
            proxies = self._parse_proxy_response(data)
            
            if proxies:
                self._cached_proxy = proxies
                self._last_fetch_time = current_time
                print(f"[ProxyManager] ✓ 获取动态代理成功: {self._mask_proxy(proxies)}")
                return proxies
            else:
                print(f"[ProxyManager] 警告: 无法从响应中解析代理信息")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"[ProxyManager] 错误: 获取动态代理失败: {e}")
            # 如果有缓存的代理，继续使用
            if self._cached_proxy:
                print(f"[ProxyManager] 使用缓存的代理")
                return self._cached_proxy
            return None
        except json.JSONDecodeError as e:
            print(f"[ProxyManager] 错误: 代理 API 返回的不是有效的 JSON: {e}")
            return None
    
    def _parse_proxy_response(self, data: Any) -> Optional[Dict[str, str]]:
        """
        解析代理 API 响应
        
        支持的响应格式：
        1. {"proxy": "http://host:port"}
        2. {"http": "http://...", "https": "https://..."}
        3. {"host": "1.2.3.4", "port": 8080}
        4. "http://host:port" (纯字符串)
        """
        if isinstance(data, str):
            # 格式 4: 纯字符串
            return {"http": data, "https": data}
        
        if not isinstance(data, dict):
            return None
        
        # 格式 2: 直接包含 http/https 键
        if "http" in data or "https" in data:
            proxies = {}
            if "http" in data:
                proxies["http"] = data["http"]
            if "https" in data:
                proxies["https"] = data["https"]
            return proxies
        
        # 格式 1: 包含 proxy 键
        if "proxy" in data:
            proxy = data["proxy"]
            return {"http": proxy, "https": proxy}
        
        # 格式 3: 包含 host 和 port
        if "host" in data and "port" in data:
            proxy = f"http://{data['host']}:{data['port']}"
            return {"http": proxy, "https": proxy}
        
        return None
    
    def _mask_proxy(self, proxies: Dict[str, str]) -> str:
        """脱敏显示代理地址"""
        if not proxies:
            return "None"
        
        proxy_str = proxies.get("http") or proxies.get("https", "")
        
        # 隐藏密码部分
        if "@" in proxy_str:
            # 格式: http://user:pass@host:port
            parts = proxy_str.split("@")
            if len(parts) == 2:
                auth_part = parts[0]
                if ":" in auth_part:
                    scheme_user = auth_part.rsplit(":", 1)[0]
                    return f"{scheme_user}:****@{parts[1]}"
        
        return proxy_str
    
    def is_enabled(self) -> bool:
        """检查是否启用了代理"""
        proxies = self.get_proxies()
        return proxies is not None and len(proxies) > 0
