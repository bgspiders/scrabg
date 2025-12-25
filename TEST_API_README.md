# 测试接口服务使用说明 (FastAPI)

## 概述

测试接口服务是一个基于 FastAPI 的独立 HTTP API 服务，用于测试爬虫工作流配置。它使用与 `success_worker.py` 完全相同的解析逻辑，确保测试和正式运行的代码一致。

## 架构设计

```
前端 (Vue3)
    ↓
后端 FastAPI (/crawl/spider/test-config)
    ↓ HTTP请求
测试接口服务 (FastAPI :5001)
    ↓ 复用逻辑
success_worker.py (WorkflowProcessor)
```

## 优势

1. **逻辑统一**: 测试服务直接继承 `WorkflowProcessor`，确保测试和生产逻辑完全一致
2. **解耦合**: 后端无需导入爬虫解析库，减少依赖冲突
3. **独立部署**: 测试服务可以独立扩展和重启，不影响主服务
4. **易于调试**: 可以单独测试和调试爬虫解析逻辑
5. **自动文档**: FastAPI 自带 Swagger UI 和 ReDoc 文档

## 快速开始

### 1. 安装依赖

```bash
cd scrabg
pip install -r requirements.txt
```

### 2. 启动测试服务

**Linux/Mac:**
```bash
chmod +x start_test_api.sh
./start_test_api.sh
```

**Windows:**
```bash
start_test_api.bat
```

**或直接运行:**
```bash
python test_api_server.py
```

### 3. 配置后端

在后端的 `.env` 或环境变量中添加：

```bash
# 测试接口服务地址（可选，默认 http://localhost:5001）
TEST_API_URL=http://localhost:5001
```

### 4. 验证服务

访问健康检查接口：
```bash
curl http://localhost:5001/health
```

访问 API 文档：
- Swagger UI: http://localhost:5001/docs
- ReDoc: http://localhost:5001/redoc

预期返回：
```json
{
  "status": "ok",
  "service": "test-api-server",
  "version": "1.0.0"
}
```

## API 接口

### 1. 健康检查

**请求:**
```
GET /health
```

**响应:**
```json
{
  "status": "ok",
  "service": "test-api-server",
  "version": "1.0.0"
}
```

### 2. 测试完整工作流

**请求:**
```
POST /api/test-workflow
Content-Type: application/json

{
  "test_url": "https://example.com",
  "config": {
    "taskInfo": {
      "id": 1,
      "name": "测试任务",
      "baseUrl": "https://example.com"
    },
    "workflowSteps": [
      {
        "id": 1,
        "type": "request",
        "config": {
          "url": "https://example.com",
          "method": "GET"
        }
      },
      {
        "id": 2,
        "type": "link_extraction",
        "config": {
          "linkExtractionRules": [
            {
              "fieldName": "link",
              "extractType": "xpath",
              "expression": "//a/@href",
              "maxLinks": 10
            }
          ]
        }
      },
      {
        "id": 3,
        "type": "data_extraction",
        "config": {
          "extractionRules": [
            {
              "fieldName": "title",
              "extractType": "xpath",
              "expression": "//title/text()"
            }
          ]
        }
      }
    ]
  }
}
```

**响应（成功）:**
```json
{
  "success": true,
  "data": {
    "url": "https://example.com",
    "status_code": 200,
    "content_length": 12345,
    "steps_results": {
      "step_1": {
        "type": "request",
        "name": "Step 1",
        "result": {
          "url": "https://example.com",
          "method": "GET",
          "status_code": 200,
          "content_length": 12345
        }
      },
      "step_2": {
        "type": "link_extraction",
        "name": "Step 2",
        "result": {
          "link": ["https://example.com/page1", "https://example.com/page2"]
        }
      },
      "step_3": {
        "type": "data_extraction",
        "name": "Step 3",
        "result": {
          "title": "Example Domain"
        }
      }
    },
    "execution_time": 1234.56
  },
  "message": "配置测试成功",
  "execution_time": 1234.56
}
```

**响应（失败）:**
```json
{
  "success": false,
  "data": {
    "error": "HTTP 404",
    "url": "https://example.com/notfound"
  },
  "message": "请求失败: HTTP 404",
  "execution_time": 123.45
}
```

### 3. 测试单个步骤

**请求:**
```
POST /api/test-step
Content-Type: application/json

{
  "test_url": "https://example.com",
  "step": {
    "type": "data_extraction",
    "config": {
      "extractionRules": [
        {
          "fieldName": "title",
          "extractType": "xpath",
          "expression": "//title/text()"
        }
      ]
    }
  }
}
```

**响应:**
```json
{
  "success": true,
  "data": {
    "title": "Example Domain"
  },
  "message": "步骤测试成功"
}
```

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| TEST_API_PORT | 服务端口 | 5001 |
| TEST_API_HOST | 监听地址 | 0.0.0.0 |
| TEST_API_DEBUG | 调试模式 | true |

## 使用流程

1. **启动测试服务**: `./start_test_api.sh` 或 `python test_api_server.py`
2. **启动后端服务**: `cd backend && python app.py --env=dev`
3. **启动前端**: `cd frontend && yarn dev`
4. **在前端配置爬虫**: 访问 http://localhost:3200，配置工作流步骤
5. **点击测试按钮**: 前端 → 后端 → 测试服务 → 返回结果

## 故障排查

### 1. 后端报错：无法连接到测试服务

**原因**: 测试接口服务未启动

**解决**: 
```bash
cd scrabg
./start_test_api.sh
```

### 2. 测试服务报错：No module named 'parsel'

**原因**: 缺少依赖

**解决**:
```bash
cd scrabg
pip install -r requirements.txt
```

### 3. 测试结果与生产不一致

**检查**:
1. 确认测试服务代码版本是否最新
2. 检查 `success_worker.py` 是否有修改未同步
3. 查看测试服务日志

## 开发建议

1. **修改解析逻辑**: 只需修改 `success_worker.py`，测试服务会自动继承
2. **添加新步骤类型**: 在 `WorkflowProcessor` 中添加处理方法
3. **调试**: 设置 `TEST_API_DEBUG=true` 可以看到详细日志

## 性能优化

1. **缓存**: 可以添加响应缓存减少重复请求
2. **异步**: 使用异步处理提高并发能力
3. **队列**: 对于大量测试请求，可以引入任务队列

## 安全建议

1. **生产环境**: 不建议暴露到公网，仅内网访问
2. **认证**: 可以添加 API Token 认证
3. **限流**: 添加请求频率限制防止滥用
