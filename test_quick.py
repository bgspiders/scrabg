#!/usr/bin/env python3
"""
快速测试脚本 - 验证测试接口服务是否正常工作
"""
import json
import requests
import sys


def test_health():
    """测试健康检查接口"""
    print("=" * 60)
    print("1. 测试健康检查接口")
    print("=" * 60)
    
    try:
        response = requests.get("http://localhost:5001/health", timeout=5)
        data = response.json()
        
        if data.get('status') == 'ok':
            print("✅ 健康检查通过")
            print(f"   服务: {data.get('service')}")
            print(f"   版本: {data.get('version')}")
            return True
        else:
            print("❌ 健康检查失败")
            return False
    except requests.ConnectionError:
        print("❌ 无法连接到服务，请确保测试服务已启动:")
        print("   ./start_test_api.sh 或 python test_api_server.py")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_workflow():
    """测试工作流接口"""
    print("\n" + "=" * 60)
    print("2. 测试工作流接口")
    print("=" * 60)
    
    # 读取 demo.json 配置
    try:
        with open('demo.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ 找不到 demo.json 文件")
        return False
    
    # 构建测试请求
    test_url = config.get('taskInfo', {}).get('baseUrl', 'https://httpbin.org/html')
    request_data = {
        'test_url': test_url,
        'config': config
    }
    
    print(f"测试 URL: {test_url}")
    print(f"工作流步骤: {len(config.get('workflowSteps', []))} 个")
    
    try:
        response = requests.post(
            "http://localhost:5001/api/test-workflow",
            json=request_data,
            timeout=30
        )
        data = response.json()
        
        if data.get('success'):
            print("✅ 工作流测试通过")
            result = data.get('data', {})
            print(f"   URL: {result.get('url')}")
            print(f"   状态码: {result.get('status_code')}")
            print(f"   内容长度: {result.get('content_length')} 字节")
            print(f"   执行时间: {result.get('execution_time'):.2f} ms")
            
            # 显示步骤结果
            steps_results = result.get('steps_results', {})
            print(f"\n   步骤结果:")
            for step_key, step_data in steps_results.items():
                step_type = step_data.get('type')
                step_name = step_data.get('name')
                step_result = step_data.get('result', {})
                
                if 'error' in step_result:
                    print(f"   ❌ {step_name} ({step_type}): {step_result['error']}")
                else:
                    print(f"   ✅ {step_name} ({step_type})")
                    
                    # 显示提取的数据摘要
                    if step_type == 'link_extraction':
                        for field, values in step_result.items():
                            if isinstance(values, list):
                                print(f"      - {field}: {len(values)} 条数据")
                    elif step_type == 'data_extraction':
                        for field, value in step_result.items():
                            if value and not field.startswith('_'):
                                preview = str(value)[:50] + '...' if len(str(value)) > 50 else value
                                print(f"      - {field}: {preview}")
            
            return True
        else:
            print("❌ 工作流测试失败")
            print(f"   错误: {data.get('message')}")
            if 'error_trace' in data.get('data', {}):
                print(f"\n   详细信息:\n{data['data']['error_trace']}")
            return False
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def main():
    """主函数"""
    print("\n🧪 测试接口服务验证")
    print("=" * 60)
    
    # 测试健康检查
    if not test_health():
        print("\n❌ 测试失败: 服务未启动")
        sys.exit(1)
    
    # 测试工作流
    if not test_workflow():
        print("\n❌ 测试失败: 工作流测试不通过")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
    print("\n提示:")
    print("1. 测试服务运行正常")
    print("2. 可以在前端使用测试功能了")
    print("3. 确保后端配置了 TEST_API_URL=http://localhost:5001")
    print()
    
    sys.exit(0)


if __name__ == '__main__':
    main()
