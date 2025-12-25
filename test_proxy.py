"""
测试代理配置
验证代理管理器是否正常工作
"""
import os
import sys

from crawler.utils.env_loader import load_env_file
from crawler.utils.proxy_manager import ProxyManager

# 加载环境变量
load_env_file()


def test_proxy_config():
    """测试代理配置"""
    print("=" * 60)
    print("代理配置测试")
    print("=" * 60)
    
    # 创建代理管理器
    proxy_manager = ProxyManager.from_env()
    
    # 显示配置信息
    print(f"\n代理模式: {proxy_manager.mode}")
    
    if proxy_manager.mode == "static":
        print("\n固定代理配置:")
        print(f"  HTTP_PROXY:  {proxy_manager.http_proxy or '(未配置)'}")
        print(f"  HTTPS_PROXY: {proxy_manager.https_proxy or '(未配置)'}")
        print(f"  SOCKS_PROXY: {proxy_manager.socks_proxy or '(未配置)'}")
    
    elif proxy_manager.mode == "dynamic":
        print("\n动态代理配置:")
        print(f"  API地址:    {proxy_manager.dynamic_api or '(未配置)'}")
        print(f"  请求方法:   {proxy_manager.dynamic_api_method}")
        print(f"  请求头:     {proxy_manager.dynamic_api_headers or '(未配置)'}")
        print(f"  刷新间隔:   {proxy_manager.refresh_interval}秒")
    
    # 测试获取代理
    print("\n" + "-" * 60)
    print("测试获取代理...")
    print("-" * 60)
    
    try:
        proxies = proxy_manager.get_proxies()
        
        if proxies:
            print("✓ 成功获取代理配置:")
            for key, value in proxies.items():
                # 脱敏显示
                masked_value = proxy_manager._mask_proxy({key: value})
                print(f"  {key}: {masked_value}")
            
            # 如果是动态代理，测试多次获取
            if proxy_manager.mode == "dynamic":
                print("\n测试动态代理刷新...")
                import time
                for i in range(3):
                    time.sleep(1)
                    proxies = proxy_manager.get_proxies()
                    if proxies:
                        proxy = proxies.get("http") or proxies.get("https")
                        print(f"  第 {i+1} 次: {proxy_manager._mask_proxy({'p': proxy})}")
        else:
            print("⚠ 未配置代理或代理已禁用")
            print("\n提示:")
            print("  1. 检查 .env 文件中的 PROXY_MODE 设置")
            print("  2. 如果使用固定代理，配置 HTTP_PROXY 或 HTTPS_PROXY")
            print("  3. 如果使用动态代理，配置 DYNAMIC_PROXY_API")
    
    except Exception as e:
        print(f"✗ 获取代理失败: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    return True


def main():
    """主函数"""
    try:
        success = test_proxy_config()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
