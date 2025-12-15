# Scrapy-Redis 分布式爬虫系统

基于 Scrapy-Redis 的分布式爬虫系统，支持从配置文件或 MySQL 数据库读取任务，将数据保存到 MySQL。

## 功能特性

- ✅ 基于 Scrapy-Redis 的分布式爬虫架构
- ✅ 支持 JSON 配置文件驱动的爬虫任务
- ✅ 支持从 MySQL 读取任务并推送到 Redis
- ✅ 支持仅请求模式（不解析内容，直接保存响应）
- ✅ 数据自动保存到 MySQL 数据库
- ✅ 良好的扩展性，支持自定义 workflow 步骤

## 项目结构

```
scrabg/
├── crawler/                    # Scrapy 爬虫项目
│   ├── __init__.py
│   ├── items.py               # 数据项定义
│   ├── pipelines.py           # MySQL 数据管道
│   ├── settings.py            # Scrapy 配置
│   ├── spiders/               # 爬虫文件
│   │   ├── __init__.py
│   │   ├── config_spider.py   # 配置驱动爬虫
│   │   └── fetch_spider.py    # 仅请求爬虫
│   └── utils/                 # 工具模块
│       ├── __init__.py
│       ├── config_loader.py   # 配置加载器
│       ├── env_loader.py      # 环境变量加载器（.env 文件支持）
│       └── workflow.py        # 工作流执行器（Scrapy 内部使用）
├── .env.example               # 环境变量配置示例文件
├── demo.json                  # 示例配置文件
├── config_request_producer.py # 根据 demo.json 生成初始请求
├── success_worker.py          # 解析成功队列并推进 workflow
├── producer_push_from_mysql.py # MySQL 任务推送脚本（可选）
├── requirements.txt           # Python 依赖
├── scrapy.cfg                 # Scrapy 项目配置
├── test_setup.py              # 环境测试脚本
├── test_data.sql              # 测试数据 SQL
└── README.md                  # 本文档
```

## 环境要求

- Python 3.8+
- Redis 服务器
- MySQL 5.7+ 或 MariaDB 10.3+

## 快速开始

### 1. 创建虚拟环境

```bash
# 创建虚拟环境（名为 scrabgs）
python3 -m venv scrabgs

# 激活虚拟环境
# macOS/Linux:
source scrabgs/bin/activate
# Windows:
# scrabgs\Scripts\activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

**推荐方式：使用 .env 文件**

复制 `.env.example` 文件并重命名为 `.env`，然后修改其中的配置：

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env 文件，填入你的配置信息
# Redis 配置
REDIS_URL=redis://localhost:6379/0

# MySQL 配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=your_username
MYSQL_PASSWORD=your_password
MYSQL_DB=your_database
MYSQL_CHARSET=utf8mb4

# Scrapy 配置（可选）
CONFIG_PATH=demo.json
LOG_LEVEL=INFO

# 爬虫队列配置（可选）
SCRAPY_START_KEY=fetch_spider:start_urls
SUCCESS_QUEUE_KEY=fetch_spider:success
```

**注意：** `.env` 文件已添加到 `.gitignore`，不会被提交到版本控制。

**密码配置说明：**
- Redis 密码：在 `REDIS_URL` 中配置，格式：`redis://:password@host:port/db`
- MySQL 密码：在 `MYSQL_PASSWORD` 中配置，如果包含特殊字符（如 `@`、`#`、`$` 等），需要用引号包裹
- 详细配置说明请参考：[ENV_CONFIG.md](ENV_CONFIG.md)

**备选方式：直接设置环境变量**

如果不使用 `.env` 文件，也可以直接设置环境变量：

```bash
export REDIS_URL="redis://localhost:6379/0"
export MYSQL_HOST="localhost"
export MYSQL_PORT="3306"
export MYSQL_USER="your_username"
export MYSQL_PASSWORD="your_password"
export MYSQL_DB="your_database"
export CONFIG_PATH="demo.json"
export LOG_LEVEL="INFO"
```

### 4. 准备数据库

#### 4.1 创建数据表

```sql
-- 用于保存爬取结果
CREATE TABLE articles (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id VARCHAR(32),
    title TEXT,
    link TEXT,
    content LONGTEXT,
    source_url TEXT,
    extra JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用于存储待抓取请求（用于 fetch_spider）
CREATE TABLE pending_requests (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    url TEXT NOT NULL,
    method VARCHAR(10) DEFAULT 'GET',
    headers_json TEXT,
    params_json TEXT,
    meta_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

#### 4.2 插入测试数据（可选）

```sql
-- 插入测试请求
INSERT INTO pending_requests (url, method, headers_json, meta_json) VALUES
('https://news.bjx.com.cn/yw/', 'GET', '{"User-Agent": "Mozilla/5.0"}', '{"test": true}');
```

### 5. 启动 Redis

确保 Redis 服务正在运行：

```bash
# 检查 Redis 是否运行
redis-cli ping
# 应该返回: PONG
```

## 使用方式

### 方式一：配置驱动爬虫（config_spider）

使用 `demo.json` 配置文件驱动爬虫：

```bash
# 激活虚拟环境
source scrabgs/bin/activate

# 运行爬虫
scrapy crawl config_spider

# 或指定配置文件路径
scrapy crawl config_spider -s CONFIG_PATH=/path/to/config.json
```

**工作流程：**
1. 读取配置文件 `demo.json`
2. 根据 `taskInfo.baseUrl` 生成初始请求
3. 按照 `workflowSteps` 执行：
   - `request`: 发送 HTTP 请求
   - `link_extraction`: 提取链接
   - `data_extraction`: 提取数据
4. 将提取的数据保存到 MySQL `articles` 表

### 方式二：MySQL 任务推送 + 仅请求爬虫（fetch_spider）

从 MySQL 读取任务，Scrapy 仅负责请求，结果保存到 Redis：

```bash
# 激活虚拟环境
source scrabgs/bin/activate

# 1. 从 MySQL 推送任务到 Redis
python producer_push_from_mysql.py

# 2. 启动爬虫（可启动多个实例实现分布式）
scrapy crawl fetch_spider
```

**工作流程：**
1. `producer_push_from_mysql.py` 从 `pending_requests` 表读取任务
2. 解析请求参数，推送到 Redis 队列 `fetch_spider:start_urls`
3. `fetch_spider` 从 Redis 消费请求
4. 发送 HTTP 请求，将响应保存到 Redis 队列 `fetch_spider:success`
5. 后续可由其他程序从 `fetch_spider:success` 队列读取并解析

### 方式三：demo.json 驱动 + 全链路 Redis

该模式完全遵循 `demo.json` 的 `workflowSteps`，Scrapy 只负责请求，解析由外部脚本完成：

1. **推送初始请求**
   ```bash
   source scrabgs/bin/activate
   python config_request_producer.py
   ```
   读取 `demo.json`，生成 `workflow_index=0` 的初始请求并写入 `SCRAPY_START_KEY`。

2. **Scrapy 仅负责请求**
   ```bash
   scrapy crawl fetch_spider -L INFO
   ```
   `fetch_spider` 把响应写回 `SUCCESS_QUEUE_KEY`，不做任何解析。

3. **success_worker 解析 workflow**
   ```bash
   python success_worker.py
   ```
   `success_worker` 持续监听成功队列，按步骤执行：
   - `request`：直接推进到下一步骤
   - `link_extraction`：抽取链接/标题等字段，推送下一批请求（携带新的 `workflow_index`）
   - `data_extraction`：抽取数据写入 `SUCCESS_ITEM_KEY`，并执行 `nextRequestCustomCode` 以生成更多请求

4. **循环至任务完成**
   - 只要成功队列中仍有响应，`success_worker` 就会继续解析并推送后续请求
   - 队列为空即表示 workflow 完成，可从 `SUCCESS_ITEM_KEY` 读取数据结果，或在 `SUCCESS_ERROR_KEY` 查看失败记录

> 如果需要持久化结果，可编写消费者程序读取 `SUCCESS_ITEM_KEY` 并写入数据库或消息队列。

## 配置说明

### .env 文件配置

项目支持从 `.env` 文件读取配置，所有相关脚本和爬虫会自动加载项目根目录下的 `.env` 文件。

**配置优先级：**
1. 系统环境变量（最高优先级）
2. `.env` 文件中的配置
3. 代码中的默认值（最低优先级）

**支持的配置项：**

| 配置项 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `REDIS_URL` | Redis 连接 URL | `redis://localhost:6379/0` | 否 |
| `MYSQL_HOST` | MySQL 主机地址 | `localhost` | 否 |
| `MYSQL_PORT` | MySQL 端口 | `3306` | 否 |
| `MYSQL_USER` | MySQL 用户名 | - | 是 |
| `MYSQL_PASSWORD` | MySQL 密码 | - | 是 |
| `MYSQL_DB` | MySQL 数据库名 | - | 是 |
| `MYSQL_CHARSET` | MySQL 字符集 | `utf8mb4` | 否 |
| `MYSQL_POOL_SIZE` | 连接池大小 | `5` | 否 |
| `MYSQL_POOL_MAX_OVERFLOW` | 连接池最大溢出 | `5` | 否 |
| `CONFIG_PATH` | 配置文件路径 | `demo.json` | 否 |
| `LOG_LEVEL` | 日志级别 | `INFO` | 否 |
| `SCRAPY_START_KEY` | Scrapy 启动队列键 | `fetch_spider:start_urls` | 否 |
| `SUCCESS_QUEUE_KEY` | 成功队列键 | `fetch_spider:success` | 否 |
| `SUCCESS_ITEM_KEY` | 数据结果队列键 | `fetch_spider:data_items` | 否 |
| `SUCCESS_ERROR_KEY` | 错误队列键 | `fetch_spider:errors` | 否 |

## 测试项目

### 测试脚本

运行测试脚本验证环境配置：

```bash
# 激活虚拟环境
source scrabgs/bin/activate

# 确保已创建 .env 文件（可选，也可以使用环境变量）
# cp .env.example .env
# 编辑 .env 文件填入你的配置

# 运行测试
python test_setup.py
```

测试脚本会自动从 `.env` 文件读取配置（如果存在），然后验证：
- ✅ 依赖包是否安装
- ✅ Redis 连接是否正常
- ✅ MySQL 连接是否正常
- ✅ 配置文件是否能加载
- ✅ 数据库表是否存在
- ✅ Redis 队列是否可用

### 手动测试步骤

#### 1. 测试 Redis 连接

```bash
source scrabgs/bin/activate
python -c "from redis import Redis; r = Redis.from_url('redis://localhost:6379/0'); print('Redis连接成功:', r.ping())"
```

#### 2. 测试 MySQL 连接

```bash
source scrabgs/bin/activate
python -c "
import os
os.environ['MYSQL_USER'] = 'your_user'
os.environ['MYSQL_PASSWORD'] = 'your_password'
os.environ['MYSQL_DB'] = 'your_db'
from sqlalchemy import create_engine, text
engine = create_engine(f'mysql+pymysql://{os.environ[\"MYSQL_USER\"]}:{os.environ[\"MYSQL_PASSWORD\"]}@localhost/{os.environ[\"MYSQL_DB\"]}')
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('MySQL连接成功:', result.fetchone())
"
```

#### 3. 测试配置加载

```bash
source scrabgs/bin/activate
python -c "
from crawler.utils.config_loader import load_config
config = load_config('demo.json')
print('配置加载成功')
print('任务名称:', config['taskInfo']['name'])
print('工作流步骤数:', len(config['workflowSteps']))
"
```

#### 4. 测试推送任务到 Redis

```bash
source scrabgs/bin/activate
# 确保 MySQL 中有测试数据
python producer_push_from_mysql.py

# 检查 Redis 队列
redis-cli LLEN fetch_spider:start_urls
```

#### 5. 测试爬虫运行

```bash
source scrabgs/bin/activate

# 测试 config_spider（使用配置文件）
scrapy crawl config_spider -L INFO

# 测试 fetch_spider（从 Redis 消费）
scrapy crawl fetch_spider -L INFO
```

#### 6. 验证数据保存

```sql
-- 检查 articles 表中的数据
SELECT * FROM articles ORDER BY created_at DESC LIMIT 10;

-- 检查成功队列中的数据（需要从 Redis 读取）
redis-cli LRANGE fetch_spider:success 0 9
```

## 分布式部署

### 启动多个爬虫实例

在不同服务器或同一服务器的不同终端启动多个爬虫实例：

```bash
# 服务器 1
source scrabgs/bin/activate
scrapy crawl fetch_spider

# 服务器 2
source scrabgs/bin/activate
scrapy crawl fetch_spider

# 服务器 3
source scrabgs/bin/activate
scrapy crawl fetch_spider
```

所有实例会从同一个 Redis 队列消费任务，实现分布式爬取。

### 监控队列状态

```bash
# 查看待处理任务数
redis-cli LLEN fetch_spider:start_urls

# 查看成功队列任务数
redis-cli LLEN fetch_spider:success

# 查看去重集合大小
redis-cli SCARD fetch_spider:dupefilter
```

## 配置说明

### demo.json 配置结构

- `taskInfo`: 任务基本信息
  - `id`: 任务ID
  - `name`: 任务名称
  - `baseUrl`: 基础URL
  - `concurrency`: 并发数
  - `requestInterval`: 请求间隔（秒）
- `workflowSteps`: 工作流步骤数组
  - `type`: 步骤类型（request/link_extraction/data_extraction）
  - `config`: 步骤配置
  - `timeout`: 超时时间
  - `retryCount`: 重试次数

## 常见问题

### 1. Redis 连接失败

- 检查 Redis 服务是否启动：`redis-cli ping`
- 检查 `REDIS_URL` 环境变量是否正确
- 检查防火墙设置

### 2. MySQL 连接失败

- 检查 MySQL 服务是否启动
- 验证用户名、密码、数据库名是否正确
- 检查 MySQL 用户权限

### 3. 爬虫不工作

- 检查 Redis 队列中是否有任务：`redis-cli LLEN fetch_spider:start_urls`
- 查看日志：`scrapy crawl fetch_spider -L DEBUG`
- 检查配置文件格式是否正确

### 4. 数据未保存到 MySQL

- 检查 `ITEM_PIPELINES` 配置
- 检查 MySQL 表结构是否正确
- 查看爬虫日志中的错误信息

## 开发扩展

### 添加新的工作流步骤类型

1. 在 `crawler/utils/workflow.py` 中添加新的步骤处理逻辑
2. 在 `demo.json` 中使用新的步骤类型

### 自定义数据处理

1. 修改 `crawler/pipelines.py` 中的 `process_item` 方法
2. 添加自定义的数据清洗和转换逻辑

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue。

