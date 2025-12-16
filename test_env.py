#!/usr/bin/env python
"""
测试 .env 文件加载和 Redis 连接
"""
import os
from pathlib import Path

# 加载 .env 文件
from crawler.utils.env_loader import load_env_file

print("=" * 60)
print("测试 .env 文件加载和 Redis 配置")
print("=" * 60)
print()

# 检查 .env 文件是否存在
project_root = Path(__file__).parent
env_file = project_root / ".env"
print(f"1. 检查 .env 文件:")
print(f"   路径: {env_file}")
print(f"   存在: {'✓' if env_file.exists() else '✗'}")
if env_file.exists():
    print(f"   大小: {env_file.stat().st_size} 字节")
print()

# 加载 .env 文件
print("2. 加载 .env 文件:")
load_result = load_env_file()
print(f"   结果: {'✓ 成功' if load_result else '✗ 失败'}")
print()

# 读取 REDIS_URL
print("3. 读取 REDIS_URL:")
redis_url = os.getenv("REDIS_URL")
if redis_url:
    # 隐藏密码
    if "@" in redis_url:
        parts = redis_url.split("@")
        if "://:" in parts[0]:
            masked = parts[0].split("://")[0] + "://:***@" + parts[1]
        elif "://" in parts[0] and ":" in parts[0].split("://")[1]:
            user_pass = parts[0].split("://")[1]
            user = user_pass.split(":")[0]
            masked = parts[0].split("://")[0] + f"://{user}:***@" + parts[1]
        else:
            masked = redis_url
    else:
        masked = redis_url
    print(f"   值: {masked}")
    print(f"   原始长度: {len(redis_url)} 字符")
    
    # 检查格式
    if redis_url.startswith("redis://"):
        print(f"   格式: ✓ 正确")
    else:
        print(f"   格式: ✗ 错误（应以 redis:// 开头）")
    
    # 检查是否包含密码
    if "@" in redis_url and "://:" in redis_url:
        print(f"   密码: ✓ 已配置（格式: redis://:password@host）")
    elif "@" in redis_url and "://" in redis_url:
        if ":" in redis_url.split("://")[1].split("@")[0]:
            print(f"   密码: ✓ 已配置（格式: redis://user:password@host）")
        else:
            print(f"   密码: ✗ 未配置（只有用户名）")
    else:
        print(f"   密码: ✗ 未配置")
else:
    print(f"   值: ✗ 未设置")
print()

# 测试 Redis 连接
if redis_url:
    print("4. 测试 Redis 连接:")
    try:
        from redis import Redis
        redis_cli = Redis.from_url(redis_url, decode_responses=False)
        redis_cli.ping()
        print(f"   连接: ✓ 成功")
        
        # 测试基本操作
        test_key = "test_env:ping"
        redis_cli.set(test_key, "test", ex=10)
        value = redis_cli.get(test_key)
        redis_cli.delete(test_key)
        if value and value.decode() == "test":
            print(f"   读写: ✓ 正常")
        else:
            print(f"   读写: ✗ 异常")
    except Exception as e:
        error_msg = str(e)
        print(f"   连接: ✗ 失败")
        print(f"   错误: {error_msg}")
        if "Authentication required" in error_msg or "NOAUTH" in error_msg:
            print()
            print("   ⚠️  认证失败！可能的原因：")
            print("      1. Redis 密码配置错误")
            print("      2. REDIS_URL 格式不正确")
            print("      3. Redis 服务器需要认证但未提供密码")
            print()
            print("   正确的格式示例：")
            print("      redis://:password@localhost:6379/0")
            print("      redis://username:password@localhost:6379/0")
else:
    print("4. 测试 Redis 连接:")
    print("   跳过（REDIS_URL 未设置）")
print()

print("=" * 60)
print("测试完成")
print("=" * 60)

