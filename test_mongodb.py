"""
测试 MongoDB 连接和数据存储
"""
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawler.utils.env_loader import load_env_file
from crawler.utils.mongodb_manager import MongoDBManager

# 加载环境变量
load_env_file()


def test_mongodb_connection():
    """测试 MongoDB 连接"""
    print("=" * 60)
    print("测试 MongoDB 连接")
    print("=" * 60)
    
    try:
        manager = MongoDBManager.from_env()
        
        if not manager.uri:
            print("❌ 未配置 MONGODB_URI")
            print("请在 .env 文件中添加:")
            print("  MONGODB_URI=mongodb://localhost:27017")
            print("  MONGODB_DB=scra")
            print("  MONGODB_COLLECTION=articles")
            return False
        
        if not manager.database_name:
            print("❌ 未配置 MONGODB_DB")
            return False
        
        print(f"✓ 连接 URI: {manager.get_masked_uri()}")
        print(f"✓ 数据库: {manager.database_name}")
        print(f"✓ 集合: {manager.collection_name}")
        
        # 测试连接
        if manager.test_connection():
            print("✓ MongoDB 连接成功！")
            return True
        else:
            print("❌ MongoDB 连接失败")
            return False
            
    except Exception as e:
        print(f"❌ MongoDB 连接异常: {e}")
        return False


def test_mongodb_save():
    """测试 MongoDB 数据保存"""
    print("\n" + "=" * 60)
    print("测试 MongoDB 数据保存")
    print("=" * 60)
    
    try:
        manager = MongoDBManager.from_env()
        
        if not manager.test_connection():
            print("❌ MongoDB 未连接，跳过测试")
            return False
        
        # 测试数据
        test_article = {
            "task_id": "test_task_001",
            "title": "测试文章标题",
            "link": "https://example.com/test",
            "content": "这是一篇测试文章的内容...",
            "source_url": "https://example.com/source",
            "extra": {
                "author": "测试作者",
                "tags": ["测试", "MongoDB"]
            }
        }
        
        # 保存数据
        print("正在保存测试数据...")
        article_id = manager.save_article(**test_article)
        
        if article_id:
            print(f"✓ 数据保存成功！文档 ID: {article_id}")
            
            # 读取数据验证
            print("正在读取数据验证...")
            saved_article = manager.get_article_by_id(article_id)
            
            if saved_article:
                print("✓ 数据读取成功！")
                print(f"  - 标题: {saved_article.get('title')}")
                print(f"  - 链接: {saved_article.get('link')}")
                print(f"  - 任务ID: {saved_article.get('task_id')}")
                
                # 删除测试数据
                print("正在清理测试数据...")
                if manager.delete_article(article_id):
                    print("✓ 测试数据已清理")
                
                return True
            else:
                print("❌ 数据读取失败")
                return False
        else:
            print("❌ 数据保存失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n🔍 开始测试 MongoDB 功能\n")
    
    # 测试连接
    connection_ok = test_mongodb_connection()
    
    if connection_ok:
        # 测试数据保存
        save_ok = test_mongodb_save()
        
        if save_ok:
            print("\n" + "=" * 60)
            print("✅ 所有测试通过！MongoDB 配置正确")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("⚠️  连接成功，但数据操作失败")
            print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ MongoDB 连接失败，请检查配置")
        print("=" * 60)
        print("\n配置说明：")
        print("1. 确保 MongoDB 服务已启动")
        print("2. 检查 .env 文件中的 MONGODB_URI 配置")
        print("3. 确认网络连接和防火墙设置")


if __name__ == "__main__":
    main()
