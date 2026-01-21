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
import requests
import urllib3
from urllib.parse import urljoin
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
import uvicorn

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from success_worker import WorkflowProcessor
from crawler.utils.env_loader import load_env_file
from crawler.utils.redis_manager import RedisManager
from crawler.utils.encoding_handler import EncodingHandler

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
    model_config = ConfigDict(extra="allow")
    id: Optional[Any] = None
    name: Optional[str] = None
    baseUrl: Optional[str] = None


class WorkflowConfig(BaseModel):
    """工作流配置"""
    model_config = ConfigDict(extra="allow")
    taskInfo: Optional[TaskInfo] = None
    workflowSteps: Optional[list] = None
    previous_html: Optional[str] = Field(None, description="上一步骤的响应HTML内容")
    previous_extracted_data: Optional[dict] = Field(None, description="上一步提取的数据")
    test_link_index: Optional[int] = Field(0, description="要测试的链接索引")
    selected_record_data: Optional[dict] = Field(None, description="当前选中的记录数据（包含链接等）")


class TestWorkflowRequest(BaseModel):
    """测试工作流请求"""
    model_config = ConfigDict(extra="allow")
    test_url: Optional[str] = Field(None, description="测试URL")
    config: Optional[WorkflowConfig] = Field(None, description="工作流配置")
    config_data: Optional[dict] = Field(None, description="兼容性配置数据")
    workflowSteps: Optional[list] = Field(None, description="兼容性步骤列表")
    selected_record_data: Optional[dict] = Field(None, description="当前选中的记录数据")


class TestStepRequest(BaseModel):
    """测试单个步骤请求"""
    model_config = ConfigDict(extra="allow")
    test_url: Optional[str] = Field(None, description="测试URL")
    step: Optional[dict] = Field(None, description="步骤配置")
    config: Optional[dict] = Field(None, description="别名配置")
    config_data: Optional[dict] = Field(None, description="兼容性配置数据")
    workflowSteps: Optional[list] = Field(None, description="兼容性步骤列表")
    html_content: Optional[str] = Field(None, description="HTML内容（可选）")
    selected_record_data: Optional[dict] = Field(None, description="当前选中的记录数据（可选）")


class HealthResponse(BaseModel):
    """健康检查响应"""
    model_config = ConfigDict(extra="allow")
    status: str
    service: str
    version: str


class ApiResponse(BaseModel):
    """通用API响应"""
    model_config = ConfigDict(extra="allow")
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
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
    
    def _create_selector(self, body: str) -> Any:
        """创建 Selector，如果是 JSON 则先转为 XML"""
        from parsel import Selector
        processed_body = body
        try:
            stripped_body = body.strip()
            if stripped_body and (stripped_body.startswith('{') or stripped_body.startswith('[')):
                json_data = json.loads(stripped_body)
                if isinstance(json_data, (dict, list)):
                    processed_body = EncodingHandler.json_to_xml(json_data)
        except Exception:
            pass
        return Selector(text=processed_body)

    def _process_response_content(self, response: Any) -> tuple[str, dict]:
        """使用 EncodingHandler 识别并解码响应内容"""
        headers = dict(response.headers)
        content = response.content
        text = EncodingHandler.decode_content(content, headers)
        info = EncodingHandler.get_encoding_info(content, headers)
        return text, info
    
    def test_workflow(self, test_url: str, previous_html: Optional[str] = None, 
                      previous_extracted_data: Optional[dict] = None, 
                      test_link_index: int = 0,
                      selected_record_data: Optional[dict] = None) -> Dict[str, Any]:
        """
        测试单步工作流
        
        Args:
            test_url: 测试URL
            previous_html: 上一步骤的响应HTML内容（可选）
            previous_extracted_data: 上一步提取的数据（可选）
            test_link_index: 要测试的链接索引（默认0）
            selected_record_data: 当前选中的记录数据（包含链接等）
            
        Returns:
            测试结果字典
        """
        import requests
        
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
            
            # 只处理传入的第一个步骤（单步测试模式）
            step = self.steps[0]
            step_id = step.get('id', 1)
            step_type = step.get('type')
            step_name = step.get('name', f'Step {step_id}')
            step_config = step.get('config', {})
            
            # 初始化响应对象
            response = None
            response_html = None
            
            # --- 步骤 1: 获取基础响应 (处理请求逻辑) ---
            
            # 优先处理 selected_record_data 模式
            if selected_record_data and selected_record_data.get('link'):
                target_url = selected_record_data['link']
                # 确保 URL 是绝对的
                if not target_url.startswith(('http://', 'https://')) and test_url:
                    target_url = urljoin(test_url, target_url)
                
                headers = dict(self.default_headers)
                
                # 如果是 request 步骤且有自定义 headers，合并它们
                if step_type == 'request' and step_config.get('headersMode') == 'json' and step_config.get('headersJson'):
                    try:
                        headers.update(json.loads(step_config['headersJson']))
                    except: pass
                
                print(f"[TestWorkflow] 请求选中的记录链接: {target_url}")
                resp = requests.get(target_url, headers=headers, timeout=30, verify=False)
                if resp.status_code >= 400:
                    return {
                        'success': False,
                        'error': f'请求选中的记录链接失败: HTTP {resp.status_code} ({target_url})',
                        'url': target_url,
                        'execution_time': (time.time() - start_time) * 1000
                    }
                
                # 使用 EncodingHandler 自动识别并解码
                response_text, encoding_info = self._process_response_content(resp)
                
                response = {
                    'selector': self._create_selector(response_text),
                    'url': target_url,
                    'body': response_text,
                    'status_code': resp.status_code,
                    'encoding': encoding_info.get('encoding'),
                    'encoding_confidence': encoding_info.get('confidence'),
                    'context': {k: v for k, v in selected_record_data.items() if k != 'link'}
                }
                
                # 注入上一步提取的数据到 context (合并)
                if previous_extracted_data:
                    if 'link' in previous_extracted_data:
                        response['context']['extracted_links'] = previous_extracted_data['link']
                    for field, values in previous_extracted_data.items():
                        if field != 'link' and field not in response['context']:
                            response['context'][field] = values
                            
                response['context']['test_link_index'] = test_link_index
                response_html = response_text
            
            # 模式 A: 提供了上一步的 HTML
            elif previous_html:
                response = {
                    'selector': self._create_selector(previous_html),
                    'url': test_url,
                    'body': previous_html,
                    'status_code': 200,
                    'context': {}
                }
                response_html = previous_html
                
                # 注入上一步提取的数据到 context
                if previous_extracted_data:
                    if 'link' in previous_extracted_data:
                        response['context']['extracted_links'] = previous_extracted_data['link']
                    for field, values in previous_extracted_data.items():
                        if field != 'link':
                            response['context'][field] = values
                response['context']['test_link_index'] = test_link_index
            
            # 模式 B: 没有上一步 HTML，需要发起请求
            else:
                # 确定请求参数 (如果是 request 步骤则使用其配置，否则使用默认)
                method = step_config.get('method', 'GET').upper()
                url = step_config.get('url') or test_url
                
                # 处理 headers
                headers = dict(self.default_headers)
                if step_config.get('headersMode') == 'json' and step_config.get('headersJson'):
                    try:
                        headers.update(json.loads(step_config['headersJson']))
                    except: pass
                elif step_config.get('headersMode') == 'keyvalue' and step_config.get('headers'):
                    for h in step_config['headers']:
                        if isinstance(h, dict) and h.get('key') and h.get('value'):
                            headers[h['key']] = h['value']
                
                # 处理 params
                params = {}
                step_params = step_config.get('params', [])
                if isinstance(step_params, list):
                    for p in step_params:
                        if isinstance(p, dict) and p.get('key') and p.get('value'):
                            params[p['key']] = p['value']
                
                # 处理 body
                body = step_config.get('body')
                
                # 发起请求
                try:
                    # 如果 body 是 JSON 字符串且方法是 POST，尝试以 JSON 形式发送
                    if method == 'POST' and body:
                        # 尝试多种解析方式
                        json_body = None
                        
                        # 方式 1: 标准 JSON
                        try:
                            json_body = json.loads(body)
                        except json.JSONDecodeError:
                            # 方式 2: Python 字典字符串 (ast.literal_eval)
                            try:
                                import ast
                                json_body = ast.literal_eval(body)
                            except:
                                pass
                        
                        if isinstance(json_body, dict):
                            response_data = requests.post(url, headers=headers, params=params, json=json_body, timeout=30)
                        else:
                            response_data = requests.request(
                                method=method, url=url, headers=headers, params=params, data=body, timeout=30
                            )
                    else:
                        response_data = requests.request(
                            method=method, url=url, headers=headers, params=params, data=body, timeout=30
                        )
                except Exception as req_err:
                    return {
                        'success': False,
                        'error': f'请求发起失败: {str(req_err)}',
                        'url': url,
                        'execution_time': (time.time() - start_time) * 1000
                    }
                
                if response_data.status_code >= 400:
                    return {
                        'success': False,
                        'error': f'HTTP {response_data.status_code}',
                        'url': url,
                        'status_code': response_data.status_code,
                        'execution_time': (time.time() - start_time) * 1000
                    }
                
                # 使用 EncodingHandler 自动识别并解码
                response_text, encoding_info = self._process_response_content(response_data)
                
                response = {
                    'selector': self._create_selector(response_text),
                    'url': url,
                    'body': response_text,
                    'status_code': response_data.status_code,
                    'encoding': encoding_info.get('encoding'),
                    'encoding_confidence': encoding_info.get('confidence'),
                    'context': {}
                }
                response_html = response_text

            # --- 步骤 2: 处理特定步骤类型的逻辑 ---

            if step_type == 'request':
                results[f'step_{step_id}'] = {
                    'type': step_type, 'name': step_name,
                    'result': {
                        'url': response['url'],
                        'method': step_config.get('method', 'GET'),
                        'status_code': response['status_code'],
                        'content_length': len(response['body'])
                    }
                }
            
            elif step_type == 'link_extraction':
                extracted = self._test_link_extraction(step, response)
                results[f'step_{step_id}'] = {
                    'type': step_type, 'name': step_name, 'result': extracted
                }
            
            elif step_type == 'data_extraction':
                # 如果是详情页提取，且我们是从列表页跳转过来的（有 extracted_links）
                if 'extracted_links' in response.get('context', {}):
                    links = response['context']['extracted_links']
                    link_index = response['context'].get('test_link_index', 0)
                    
                    if links and 0 <= link_index < len(links):
                        target_link = links[link_index]
                        absolute_url = urljoin(response['url'], target_link)
                        
                        # 发起详情页请求
                        detail_resp = requests.get(absolute_url, headers=self.default_headers, timeout=30)
                        if detail_resp.status_code < 400:
                            # 使用 EncodingHandler 自动识别并解码
                            response_text, encoding_info = self._process_response_content(detail_resp)
                            
                            response = {
                                'selector': self._create_selector(response_text),
                                'url': absolute_url,
                                'body': response_text,
                                'status_code': detail_resp.status_code,
                                'encoding': encoding_info.get('encoding'),
                                'encoding_confidence': encoding_info.get('confidence'),
                                'context': response.get('context', {})
                            }
                            response_html = response_text
                        else:
                            return {
                                'success': False,
                                'error': f'请求详情页失败: HTTP {detail_resp.status_code} ({absolute_url})',
                                'execution_time': (time.time() - start_time) * 1000
                            }
                
                # 执行数据提取
                extracted = self._test_data_extraction(step, response)
                results[f'step_{step_id}'] = {
                    'type': step_type, 'name': step_name, 'result': extracted
                }

            else:
                results[f'step_{step_id}'] = {
                    'type': step_type, 'name': step_name,
                    'result': {'warning': f'Unsupported step type: {step_type}'}
                }
            
            execution_time = (time.time() - start_time) * 1000
            return {
                'success': True,
                'url': response.get('url', test_url),
                'status_code': response.get('status_code', 200),
                'encoding': response.get('encoding'),
                'encoding_confidence': response.get('encoding_confidence'),
                'content_length': len(response.get('body', '')),
                'steps_results': results,
                'execution_time': execution_time,
                'response_html': response_html
            }
            
        except Exception as e:
            import traceback
            return {
                'success': False,
                'error': str(e),
                'error_trace': traceback.format_exc(),
                'url': test_url,
                'status_code': 0, # 确保包含 status_code 避免后端报错
                'execution_time': (time.time() - start_time) * 1000
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
            
            # 如果是 link 字段且为文本，自动拼接绝对地址
            if field_name == "link" and isinstance(values, list):
                base_url = response.get('url')
                if base_url:
                    values = [urljoin(base_url, v) if v and isinstance(v, str) else v for v in values]
            
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
            
            # 如果是 link 字段且为文本，自动拼接绝对地址
            if field_name == "link":
                base_url = response.get('url')
                if base_url:
                    if isinstance(values, list):
                        values = [urljoin(base_url, v) if v and isinstance(v, str) else v for v in values]
                    elif isinstance(values, str) and values:
                        values = urljoin(base_url, values)
            
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
    """
    try:
        # 优先使用 config，其次使用 config_data，最后尝试 root 级的 workflowSteps
        if request.config:
            config_dict = request.config.model_dump()
        elif request.config_data:
            config_dict = request.config_data
        elif request.workflowSteps:
            config_dict = {'workflowSteps': request.workflowSteps}
        else:
            return ApiResponse(success=False, message='缺少配置信息 (config, config_data 或 workflowSteps)')
        
        # 提取参数
        test_url = request.test_url or config_dict.get('baseUrl') or config_dict.get('test_url')
        previous_html = config_dict.pop('previous_html', None)
        previous_extracted_data = config_dict.pop('previous_extracted_data', None)
        test_link_index = config_dict.pop('test_link_index', 0)
        selected_record_data = request.selected_record_data or config_dict.pop('selected_record_data', None)
        
        # 确保有 workflowSteps
        if not config_dict.get('workflowSteps'):
            return ApiResponse(success=False, message='配置中缺少 workflowSteps')
            
        # 创建测试处理器
        processor = TestWorkflowProcessor(config_dict)
        
        # 如果提供了外部 headers，更新默认 headers
        if config_dict.get('headers'):
            try:
                processor.default_headers.update(config_dict['headers'])
            except: pass
        
        print(f"[API] 收到测试请求: url={test_url}, has_selected_record={bool(selected_record_data)}")
        
        # 执行测试
        result = processor.test_workflow(
            test_url, 
            previous_html=previous_html,
            previous_extracted_data=previous_extracted_data,
            test_link_index=test_link_index,
            selected_record_data=selected_record_data
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
            data={'success': False, 'error': str(e), 'status_code': 0},
            message=f'服务器错误: {str(e)}',
            error_trace=error_trace
        )


@app.post('/api/test-step', response_model=ApiResponse)
async def test_single_step(request: TestStepRequest):
    """
    测试单个步骤接口 (兼容多种配置格式)
    """
    try:
        # 获取原始字典以便全量搜索
        raw_payload = request.model_dump()
        print(raw_payload)
        if request.model_extra:
            raw_payload.update(request.model_extra)
            
        # 更加鲁棒的步骤提取逻辑
        step = request.step
        config_data = request.config_data or request.config or {}
        workflow_steps = request.workflowSteps
        
        # 1. 如果有 workflowSteps，取第一个作为当前步骤
        if not step:
            if workflow_steps:
                step = workflow_steps[0]
            elif isinstance(config_data, dict) and config_data.get('workflowSteps'):
                step = config_data['workflowSteps'][0]
            elif isinstance(config_data, dict) and config_data.get('step'):
                step = config_data['step']
        
        if not step:
            return ApiResponse(
                success=False, 
                message='缺少步骤配置 (请检查 payload 结构)',
                data={
                    'debug': {
                        'received_keys': list(raw_payload.keys()),
                        'has_config_data': bool(request.config_data),
                        'has_config': bool(request.config),
                        'has_workflow_steps': bool(request.workflowSteps),
                        'has_step': bool(request.step)
                    }
                }
            )
            
        # 确定测试 URL
        test_url = request.test_url
        if not test_url and isinstance(config_data, dict):
            test_url = config_data.get('test_url') or config_data.get('baseUrl')
            
        # 构建执行配置
        final_config = {
            'taskInfo': (config_data.get('taskInfo') if isinstance(config_data, dict) else None) or {'id': 1, 'name': 'Test', 'baseUrl': test_url},
            'workflowSteps': [step]
        }
        
        processor = TestWorkflowProcessor(final_config)
        
        # 处理全局 headers
        global_headers = {}
        if isinstance(config_data, dict) and config_data.get('headers'):
            global_headers = config_data['headers']
        elif raw_payload.get('headers'):
            global_headers = raw_payload['headers']
            
        if global_headers:
            try:
                processor.default_headers.update(global_headers)
            except: pass
            
        # 确定中间数据源
        previous_html = request.html_content
        previous_data = None
        
        if isinstance(config_data, dict):
            previous_html = config_data.get('previous_html') or previous_html
            previous_data = config_data.get('previous_extracted_data')
            
        test_link_index = raw_payload.get('test_link_index', 0)
        if isinstance(config_data, dict) and 'test_link_index' in config_data:
            test_link_index = config_data['test_link_index']
            
        selected_record_data = request.selected_record_data
        if not selected_record_data and isinstance(config_data, dict):
            selected_record_data = config_data.get('selected_record_data')
        
        print(f"[API] 收到单步测试请求: url={test_url}, has_selected_record={bool(selected_record_data)}")
        
        # 执行测试
        result = processor.test_workflow(
            test_url or final_config['taskInfo'].get('baseUrl'), 
            previous_html=previous_html,
            previous_extracted_data=previous_data,
            test_link_index=test_link_index,
            selected_record_data=selected_record_data
        )
        
        if result.get('success'):
            return ApiResponse(
                success=True,
                data=result,
                message='步骤测试成功',
                execution_time=result.get('execution_time', 0)
            )
        else:
            return ApiResponse(
                success=False,
                data=result,
                message=result.get('error', '步骤测试失败'),
                execution_time=result.get('execution_time', 0)
            )
    
    except Exception as e:
        error_trace = traceback.format_exc()
        return ApiResponse(
            success=False,
            data={'success': False, 'error': str(e), 'status_code': 0},
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
