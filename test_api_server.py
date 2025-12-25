"""
测试接口服务 (FastAPI)
提供独立的HTTP API用于测试爬虫工作流配置
使用与 success_worker.py 完全相同的解析逻辑
"""
import json
import os
import sys
import time
import traceback
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from success_worker import WorkflowProcessor
from crawler.utils.env_loader import load_env_file
from crawler.utils.redis_manager import RedisManager

# 加载环境变量
load_env_file()

# 创建FastAPI应用
app = FastAPI(
    title="爬虫测试接口服务",
    description="提供独立的HTTP API用于测试爬虫工作流配置",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic 模型定义
class TaskInfo(BaseModel):
    """任务信息"""
    id: int
    name: str
    baseUrl: str


class WorkflowConfig(BaseModel):
    """工作流配置"""
    taskInfo: TaskInfo
    workflowSteps: list
    previous_html: Optional[str] = Field(None, description="上一步骤的响应HTML内容")
    previous_extracted_data: Optional[dict] = Field(None, description="上一步提取的数据")
    test_link_index: Optional[int] = Field(0, description="要测试的链接索引")


class TestWorkflowRequest(BaseModel):
    """测试工作流请求"""
    test_url: str = Field(..., description="测试URL")
    config: WorkflowConfig = Field(..., description="工作流配置")


class TestStepRequest(BaseModel):
    """测试单个步骤请求"""
    test_url: str = Field(..., description="测试URL")
    step: dict = Field(..., description="步骤配置")
    html_content: Optional[str] = Field(None, description="HTML内容（可选）")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    service: str
    version: str


class ApiResponse(BaseModel):
    """通用API响应"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: str
    execution_time: Optional[float] = None
    error_trace: Optional[str] = None


class TestWorkflowProcessor(WorkflowProcessor):
    """测试用的工作流处理器，不依赖Redis"""
    
    def __init__(self, config: Dict[str, Any]):
        """初始化处理器，使用None替代redis_manager"""
        self.config = config
        self.steps = config.get("workflowSteps", [])
        self.task_info = config.get("taskInfo", {})
        self.default_headers = self._parse_headers()
        # 测试模式不需要 Redis 和数据库
        self.redis_manager = None
        self.db_manager = None
    
    def test_workflow(self, test_url: str, previous_html: Optional[str] = None, previous_extracted_data: Optional[dict] = None, test_link_index: int = 0) -> Dict[str, Any]:
        """
        测试完整工作流
        
        Args:
            test_url: 测试URL
            previous_html: 上一步骤的响应HTML内容（可选）
            previous_extracted_data: 上一步提取的数据（可选）
            test_link_index: 要测试的链接索引（默认0）
            
        Returns:
            测试结果字典
        """
        import requests
        from urllib.parse import urljoin
        
        start_time = time.time()
        results = {}
        
        try:
            # 检查是否有步骤配置
            if not self.steps:
                return {
                    'success': False,
                    'error': '没有配置工作流步骤',
                    'execution_time': (time.time() - start_time) * 1000
                }
            
            # 检查第一个步骤类型
            first_step = self.steps[0]
            first_step_type = first_step.get('type')
            
            # 初始化响应对象
            response = None
            response_html = None  # 用于返回给前端
            
            # 如果提供了previous_html，使用它作为响应内容
            if previous_html:
                from parsel import Selector
                response = {
                    'selector': Selector(text=previous_html),
                    'url': test_url,
                    'body': previous_html,
                    'status_code': 200,
                    'context': {}
                }
                response_html = previous_html
                
                # 如果提供了previous_extracted_data，保存到context
                if previous_extracted_data:
                    if 'link' in previous_extracted_data:
                        response['context']['extracted_links'] = previous_extracted_data['link']
                    # 保存其他提取字段
                    for field, values in previous_extracted_data.items():
                        if field != 'link':
                            response['context'][field] = values
                # 保存要测试的链接索引
                response['context']['test_link_index'] = test_link_index
            # 只有第一个步骤是request类型时，才发起初始请求
            elif first_step_type == 'request':
                # 发起初始请求
                response_data = requests.get(
                    test_url, 
                    headers=self.default_headers, 
                    timeout=30
                )
                
                if response_data.status_code >= 400:
                    return {
                        'success': False,
                        'error': f'HTTP {response_data.status_code}',
                        'url': test_url,
                        'status_code': response_data.status_code,
                        'execution_time': (time.time() - start_time) * 1000
                    }
                
                # 构建响应对象
                from parsel import Selector
                response = {
                    'selector': Selector(text=response_data.text),
                    'url': test_url,
                    'body': response_data.text,
                    'status_code': response_data.status_code,
                    'context': {}
                }
                response_html = response_data.text  # 保存HTML用于返回
            else:
                # 如果第一个步骤不是request，返回提示
                return {
                    'success': False,
                    'error': f'测试步骤{first_step_type}需要先测试步骤1（请求配置），请添加步骤1或从步骤1开始测试',
                    'execution_time': (time.time() - start_time) * 1000
                }
            
            # 处理工作流步骤
            index = 0
            while index < len(self.steps):
                step = self.steps[index]
                step_id = step.get('id', index + 1)
                step_type = step.get('type')
                step_name = step.get('name', f'Step {step_id}')
                
                if step_type == 'request':
                    # 记录请求步骤结果
                    results[f'step_{step_id}'] = {
                        'type': step_type,
                        'name': step_name,
                        'result': {
                            'url': response['url'],
                            'method': step.get('config', {}).get('method', 'GET'),
                            'status_code': response['status_code'],
                            'content_length': len(response['body'])
                        }
                    }
                    index += 1
                    continue
                
                elif step_type == 'link_extraction':
                    # 使用 success_worker.py 的链接提取逻辑
                    extracted = self._test_link_extraction(step, response)
                    results[f'step_{step_id}'] = {
                        'type': step_type,
                        'name': step_name,
                        'result': extracted
                    }
                    
                    # 步骤2只做链接提取，不发起请求
                    # 将提取的链接保存到context中，供后续步骤使用
                    if 'link' in extracted and isinstance(extracted['link'], list) and extracted['link']:
                        response['context']['extracted_links'] = extracted['link']
                        # 保存其他提取字段到context
                        for field, values in extracted.items():
                            if field != 'link' and isinstance(values, list) and values:
                                response['context'][field] = values
                    
                    index += 1
                    continue
                
                elif step_type == 'data_extraction':
                    # 步骤3：如果context中没有链接，尝试从当前响应中提取
                    if 'extracted_links' not in response.get('context', {}):
                        # 查找前面是否有链接提取步骤
                        for prev_step in self.steps[:index]:
                            if prev_step.get('type') == 'link_extraction':
                                # 重新执行链接提取
                                link_extracted = self._test_link_extraction(prev_step, response)
                                if 'link' in link_extracted and isinstance(link_extracted['link'], list) and link_extracted['link']:
                                    response['context']['extracted_links'] = link_extracted['link']
                                    # 保存其他提取字段
                                    for field, values in link_extracted.items():
                                        if field != 'link' and isinstance(values, list) and values:
                                            response['context'][field] = values
                                break
                    
                    # 步骤3：如果context中有链接，先请求指定的链接
                    if 'extracted_links' in response.get('context', {}):
                        links = response['context']['extracted_links']
                        link_index = response['context'].get('test_link_index', 0)  # 获取要测试的链接索引
                        
                        if links and 0 <= link_index < len(links):
                            target_link = links[link_index]
                            absolute_url = urljoin(response['url'], target_link)
                            
                            # 发起请求获取详情页
                            try:
                                detail_resp = requests.get(
                                    absolute_url,
                                    headers=self.default_headers,
                                    timeout=30
                                )
                                
                                if detail_resp.status_code < 400:
                                    # 更新响应对象为详情页内容
                                    response = {
                                        'selector': Selector(text=detail_resp.text),
                                        'url': absolute_url,
                                        'body': detail_resp.text,
                                        'status_code': detail_resp.status_code,
                                        'context': response.get('context', {})
                                    }
                                    response_html = detail_resp.text  # 更新response_html
                                else:
                                    # 请求失败，记录错误
                                    results[f'step_{step_id}'] = {
                                        'type': step_type,
                                        'name': step_name,
                                        'result': {'error': f'请求详情页失败: HTTP {detail_resp.status_code} ({absolute_url})'}
                                    }
                                    index += 1
                                    continue
                            except Exception as e:
                                # 请求异常
                                results[f'step_{step_id}'] = {
                                    'type': step_type,
                                    'name': step_name,
                                    'result': {'error': f'请求详情页异常: {str(e)}'}
                                }
                                index += 1
                                continue
                        elif links:
                            # 链接索引超出范围
                            results[f'step_{step_id}'] = {
                                'type': step_type,
                                'name': step_name,
                                'result': {'error': f'链接索引 {link_index} 超出范围 (0-{len(links)-1})'}
                            }
                            index += 1
                            continue
                    
                    # 使用 success_worker.py 的数据提取逻辑
                    extracted = self._test_data_extraction(step, response)
                    results[f'step_{step_id}'] = {
                        'type': step_type,
                        'name': step_name,
                        'result': extracted
                    }
                    index += 1
                    continue
                
                else:
                    # 未知步骤类型
                    results[f'step_{step_id}'] = {
                        'type': step_type,
                        'name': step_name,
                        'result': {'warning': f'Unknown step type: {step_type}'}
                    }
                    index += 1
            
            execution_time = (time.time() - start_time) * 1000
            
            return {
                'success': True,
                'url': response.get('url', test_url) if response else test_url,
                'status_code': response.get('status_code', 200) if response else 200,
                'content_length': len(response.get('body', '')) if response else 0,
                'steps_results': results,
                'execution_time': execution_time,
                'response_html': response_html  # 返回响应HTML供前端保存
            }
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            import traceback
            return {
                'success': False,
                'error': str(e),
                'error_trace': traceback.format_exc(),
                'url': test_url,
                'execution_time': execution_time
            }
    
    def _test_link_extraction(self, step: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        """测试链接提取 - 使用与 success_worker.py 相同的逻辑"""
        rules = step.get("config", {}).get("linkExtractionRules", [])
        if not rules:
            return {'warning': 'No link extraction rules configured'}
        
        selector = response['selector']
        extracted_data = {}
        
        for rule in rules:
            field_name = rule.get("fieldName")
            if not field_name:
                continue
            
            # 使用 success_worker.py 的 _extract 方法
            values = self._extract(selector, rule, multiple=True)
            
            # 应用 maxLinks 限制
            max_links = rule.get("maxLinks")
            if max_links and isinstance(values, list):
                values = values[:max_links]
            
            extracted_data[field_name] = values
        
        return extracted_data
    
    def _test_data_extraction(self, step: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        """测试数据提取 - 使用与 success_worker.py 相同的逻辑"""
        rules = step.get("config", {}).get("extractionRules", [])
        if not rules:
            return {'warning': 'No extraction rules configured'}
        
        selector = response['selector']
        extracted_data = {}
        
        for rule in rules:
            field_name = rule.get("fieldName")
            if not field_name:
                continue
            
            # 使用 success_worker.py 的 _extract 方法
            multiple = rule.get("multiple", False)
            values = self._extract(selector, rule, multiple=multiple)
            extracted_data[field_name] = values
        
        return extracted_data


@app.get('/health', response_model=HealthResponse)
async def health_check():
    """健康检查接口"""
    return HealthResponse(
        status='ok',
        service='test-api-server',
        version='1.0.0'
    )


@app.post('/api/test-workflow', response_model=ApiResponse)
async def test_workflow(request: TestWorkflowRequest):
    """
    测试工作流配置接口
    
    - **test_url**: 测试URL
    - **config**: 工作流配置，包含 taskInfo 和 workflowSteps
    - **previous_html**: 上一步骤的响应HTML内容（可选）
    - **previous_extracted_data**: 上一步提取的数据（可选）
    - **test_link_index**: 要测试的链接索引（可选）
    """
    try:
        # 转换为字典格式
        config_dict = request.config.model_dump()
        
        # 提取参数（如果有）
        previous_html = config_dict.pop('previous_html', None)
        previous_extracted_data = config_dict.pop('previous_extracted_data', None)
        test_link_index = config_dict.pop('test_link_index', 0)
        
        # 创建测试处理器
        processor = TestWorkflowProcessor(config_dict)
        
        # 执行测试，传递所有参数
        result = processor.test_workflow(
            request.test_url, 
            previous_html=previous_html,
            previous_extracted_data=previous_extracted_data,
            test_link_index=test_link_index
        )
        
        if result.get('success'):
            return ApiResponse(
                success=True,
                data=result,
                message='配置测试成功',
                execution_time=result.get('execution_time', 0)
            )
        else:
            return ApiResponse(
                success=False,
                data=result,
                message=result.get('error', '配置测试失败'),
                execution_time=result.get('execution_time', 0)
            )
    
    except Exception as e:
        error_trace = traceback.format_exc()
        return ApiResponse(
            success=False,
            message=f'服务器错误: {str(e)}',
            error_trace=error_trace
        )


@app.post('/api/test-step', response_model=ApiResponse)
async def test_single_step(request: TestStepRequest):
    """
    测试单个步骤接口
    
    - **test_url**: 测试URL
    - **step**: 步骤配置
    - **html_content**: HTML内容（可选，如果提供则不发起请求）
    """
    try:
        # 构建最小配置
        config = {
            'taskInfo': {'id': 1, 'name': 'Test'},
            'workflowSteps': [request.step]
        }
        
        processor = TestWorkflowProcessor(config)
        
        # 如果提供了html_content，直接使用；否则发起请求
        if request.html_content:
            from parsel import Selector
            response = {
                'selector': Selector(text=request.html_content),
                'url': request.test_url,
                'body': request.html_content,
                'context': {}
            }
        else:
            import requests as req
            resp = req.get(request.test_url, headers=processor.default_headers, timeout=30)
            from parsel import Selector
            response = {
                'selector': Selector(text=resp.text),
                'url': request.test_url,
                'body': resp.text,
                'context': {}
            }
        
        # 根据步骤类型执行测试
        step_type = request.step.get('type')
        if step_type == 'link_extraction':
            result = processor._test_link_extraction(request.step, response)
        elif step_type == 'data_extraction':
            result = processor._test_data_extraction(request.step, response)
        else:
            result = {'warning': f'Unsupported step type: {step_type}'}
        
        return ApiResponse(
            success=True,
            data=result,
            message='步骤测试成功'
        )
    
    except Exception as e:
        error_trace = traceback.format_exc()
        return ApiResponse(
            success=False,
            message=f'测试失败: {str(e)}',
            error_trace=error_trace
        )


def main():
    """启动测试API服务"""
    port = int(os.getenv('TEST_API_PORT', 5001))
    host = os.getenv('TEST_API_HOST', '0.0.0.0')
    reload = os.getenv('TEST_API_DEBUG', 'true').lower() == 'true'
    
    print(f"")
    print(f"{'='*60}")
    print(f"  测试接口服务启动中... (FastAPI)")
    print(f"{'='*60}")
    print(f"  地址: http://{host}:{port}")
    print(f"  API文档: http://{host}:{port}/docs")
    print(f"  健康检查: http://{host}:{port}/health")
    print(f"  测试接口: http://{host}:{port}/api/test-workflow")
    print(f"  调试模式: {reload}")
    print(f"{'='*60}")
    print(f"")
    
    uvicorn.run(
        "test_api_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == '__main__':
    main()
