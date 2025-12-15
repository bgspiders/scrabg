#!/usr/bin/env python
"""
测试脚本：验证项目环境配置是否正确
"""
import os
import sys
import json
from typing import List, Tuple

# 加载 .env 文件
from crawler.utils.env_loader import load_env_file
load_env_file()


def test_imports() -> Tuple[bool, str]:
    """测试必要的 Python 包是否已安装"""
    try:
        import scrapy
        import scrapy_redis
        import redis
        import sqlalchemy
        import pymysql
        return True, "所有依赖包已安装"
    except ImportError as e:
        return False, f"缺少依赖包: {e}"


def test_redis_connection() -> Tuple[bool, str]:
    """测试 Redis 连接"""
    try:
        from redis import Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = Redis.from_url(redis_url)
        result = r.ping()
        if result:
            return True, f"Redis 连接成功 ({redis_url})"
        return False, "Redis 连接失败"
    except Exception as e:
        return False, f"Redis 连接错误: {e}"


def test_mysql_connection() -> Tuple[bool, str]:
    """测试 MySQL 连接"""
    try:
        from sqlalchemy import create_engine, text
        
        user = os.getenv("MYSQL_USER")
        password = os.getenv("MYSQL_PASSWORD")
        host = os.getenv("MYSQL_HOST", "localhost")
        port = os.getenv("MYSQL_PORT", "3306")
        db = os.getenv("MYSQL_DB")
        
        if not all([user, password, db]):
            return False, "请设置环境变量: MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB"
        
        engine = create_engine(
            f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4"
        )
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return True, f"MySQL 连接成功 ({user}@{host}:{port}/{db})"
    except Exception as e:
        return False, f"MySQL 连接错误: {e}"


def test_config_file() -> Tuple[bool, str]:
    """测试配置文件加载"""
    try:
        from crawler.utils.config_loader import load_config
        config_path = os.getenv("CONFIG_PATH", "demo.json")
        config = load_config(config_path)
        
        if "taskInfo" not in config or "workflowSteps" not in config:
            return False, "配置文件格式不正确"
        
        task_name = config.get("taskInfo", {}).get("name", "未知")
        steps_count = len(config.get("workflowSteps", []))
        return True, f"配置文件加载成功 (任务: {task_name}, 步骤数: {steps_count})"
    except Exception as e:
        return False, f"配置文件加载错误: {e}"


def test_redis_queues() -> Tuple[bool, str]:
    """测试 Redis 队列是否可访问"""
    try:
        from redis import Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = Redis.from_url(redis_url)
        
        # 测试写入和读取
        test_key = "test_setup:ping"
        r.set(test_key, "test", ex=10)
        value = r.get(test_key)
        r.delete(test_key)
        
        if value and value.decode() == "test":
            return True, "Redis 队列读写正常"
        return False, "Redis 队列读写异常"
    except Exception as e:
        return False, f"Redis 队列测试错误: {e}"


def run_tests() -> List[Tuple[str, bool, str]]:
    """运行所有测试"""
    tests = [
        ("依赖包检查", test_imports),
        ("Redis 连接", test_redis_connection),
        ("MySQL 连接", test_mysql_connection),
        ("配置文件加载", test_config_file),
        ("Redis 队列测试", test_redis_queues),
    ]
    
    results = []
    for name, test_func in tests:
        success, message = test_func()
        results.append((name, success, message))
    
    return results


def main():
    """主函数"""
    print("=" * 60)
    print("Scrapy-Redis 分布式爬虫系统 - 环境测试")
    print("=" * 60)
    print()
    
    results = run_tests()
    
    # 显示结果
    passed = 0
    failed = 0
    
    for name, success, message in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} | {name}")
        print(f"      {message}")
        print()
        
        if success:
            passed += 1
        else:
            failed += 1
    
    # 总结
    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 所有测试通过！环境配置正确，可以开始使用爬虫系统。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查环境配置。")
        print("\n提示:")
        print("1. 确保已安装所有依赖: pip install -r requirements.txt")
        print("2. 确保 Redis 服务正在运行")
        print("3. 设置正确的 MySQL 环境变量")
        print("4. 确保数据库表已创建（参考 README.md）")
        return 1


if __name__ == "__main__":
    sys.exit(main())

