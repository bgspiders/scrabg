# .env 文件配置指南

## 数据库类型选择

项目支持 MySQL 和 MongoDB 两种数据库，可通过配置环境变量进行切换。

```bash
# 文章数据存储类型
ARTICLE_DB_TYPE=mysql  # 可选: mysql, mongodb
```

**说明**：
- `mysql`: 使用 MySQL 数据库存储文章数据
- `mongodb`: 使用 MongoDB 存储文章数据
- 默认值: `mysql`
- **重要**: 切换数据库类型后需要重启后端服务

**作用范围**：
1. **后端 API** (`/backend/crawl/controller/article_controller.py`): 文章数据管理接口
2. **success_worker.py**: 爆虫数据存储（优先级: MongoDB > MySQL > Redis）

---

## 密码配置说明

### Redis 密码配置

Redis 密码可以在 `REDIS_URL` 中配置，格式如下：

#### 无密码（默认）
```bash
REDIS_URL=redis://localhost:6379/0
```

#### 有密码（方式一：密码在 URL 中）
```bash
# 格式: redis://:password@host:port/db
REDIS_URL=redis://:your_redis_password@localhost:6379/0
```

#### 有密码（方式二：用户名和密码）
```bash
# 格式: redis://username:password@host:port/db
REDIS_URL=redis://username:your_redis_password@localhost:6379/0
```

#### 特殊字符处理
如果密码包含特殊字符（如 `@`、`#`、`:` 等），需要进行 URL 编码：
- `@` → `%40`
- `#` → `%23`
- `:` → `%3A`
- `/` → `%2F`

示例：
```bash
# 原始密码: my@pass#123
# URL 编码后: my%40pass%23123
REDIS_URL=redis://:my%40pass%23123@localhost:6379/0
```

### MySQL 密码配置

MySQL 密码在 `MYSQL_PASSWORD` 中配置：

#### 简单密码（无特殊字符）
```bash
MYSQL_PASSWORD=123456
MYSQL_PASSWORD=mypassword
```

#### 包含特殊字符的密码
如果密码包含特殊字符，建议使用引号包裹：

```bash
# 包含 @ 符号
MYSQL_PASSWORD="my@password"

# 包含 # 符号
MYSQL_PASSWORD="my#password"

# 包含 $ 符号
MYSQL_PASSWORD="my$password"

# 包含空格
MYSQL_PASSWORD="my password"

# 包含引号（需要转义）
MYSQL_PASSWORD="my\"password"
MYSQL_PASSWORD='my\'password'
```

#### 常见特殊字符处理

| 特殊字符 | 处理方式 | 示例 |
|---------|---------|------|
| `@` | 用引号包裹 | `MYSQL_PASSWORD="pass@word"` |
| `#` | 用引号包裹 | `MYSQL_PASSWORD="pass#word"` |
| `$` | 用引号包裹 | `MYSQL_PASSWORD="pass$word"` |
| `%` | 用引号包裹 | `MYSQL_PASSWORD="pass%word"` |
| `&` | 用引号包裹 | `MYSQL_PASSWORD="pass&word"` |
| `*` | 用引号包裹 | `MYSQL_PASSWORD="pass*word"` |
| `(` `)` | 用引号包裹 | `MYSQL_PASSWORD="pass(word)"` |
| `[` `]` | 用引号包裹 | `MYSQL_PASSWORD="pass[word]"` |
| `{` `}` | 用引号包裹 | `MYSQL_PASSWORD="pass{word}"` |
| 空格 | 用引号包裹 | `MYSQL_PASSWORD="pass word"` |
| `"` | 转义或使用单引号 | `MYSQL_PASSWORD="pass\"word"` |
| `'` | 转义或使用双引号 | `MYSQL_PASSWORD='pass\'word'` |

## 代理配置说明

项目支持两种代理模式：**固定代理**和**动态代理**。

### 固定代理配置

使用固定的代理服务器地址。

```bash
# 设置代理模式为固定代理
PROXY_MODE=static

# HTTP/HTTPS 代理
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890

# 或者使用 SOCKS5 代理
SOCKS_PROXY=socks5://127.0.0.1:1080
```

#### 带认证的代理
```bash
HTTP_PROXY=http://username:password@proxy.example.com:8080
HTTPS_PROXY=http://username:password@proxy.example.com:8080
```

### 动态代理配置

通过 API 接口获取代理地址，适用于代理池服务。

```bash
# 设置代理模式为动态代理
PROXY_MODE=dynamic

# 动态代理 API 地址
DYNAMIC_PROXY_API=http://your-proxy-api.com/get

# API 请求方法（GET 或 POST）
DYNAMIC_PROXY_API_METHOD=GET

# API 请求头（JSON 格式，可选）
DYNAMIC_PROXY_API_HEADERS='{"Authorization": "Bearer your_token"}'

# 代理刷新间隔（秒），0 表示每次请求都获取新代理
DYNAMIC_PROXY_REFRESH_INTERVAL=0
```

#### 动态代理 API 响应格式

支持多种响应格式：

**格式 1：简单代理**
```json
{
  "proxy": "http://123.45.67.89:8080"
}
```

**格式 2：分别指定 HTTP/HTTPS**
```json
{
  "http": "http://123.45.67.89:8080",
  "https": "http://123.45.67.89:8080"
}
```

**格式 3：Host + Port**
```json
{
  "host": "123.45.67.89",
  "port": 8080
}
```

**格式 4：纯字符串**
```json
"http://123.45.67.89:8080"
```

### 不使用代理

```bash
# 方式 1：设置为 static 但不配置代理地址
PROXY_MODE=static
HTTP_PROXY=
HTTPS_PROXY=
SOCKS_PROXY=

# 方式 2：注释掉所有代理配置
# PROXY_MODE=static
# HTTP_PROXY=
# HTTPS_PROXY=
```

## 完整配置示例

### 示例 1：简单配置（无密码）
```bash
REDIS_URL=redis://localhost:6379/0
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DB=scrabg
```

### 示例 2：Redis 有密码
```bash
REDIS_URL=redis://:mypassword123@localhost:6379/0
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DB=scrabg
```

### 示例 3：MySQL 密码包含特殊字符
```bash
REDIS_URL=redis://localhost:6379/0
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=admin
MYSQL_PASSWORD="my@pass#123"
MYSQL_DB=scrabg
```

### 示例 4：复杂密码配置
```bash
# Redis 密码包含特殊字符（URL 编码）
REDIS_URL=redis://:my%40pass%23123@localhost:6379/0

# MySQL 密码包含特殊字符（引号包裹）
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=admin
MYSQL_PASSWORD="P@ssw0rd#2024!"
MYSQL_DB=scrabg
```

### 示例 5：使用 MongoDB 存储数据
```bash
REDIS_URL=redis://localhost:6379/0

# MongoDB 配置（优先级高于 MySQL）
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=scra
MONGODB_COLLECTION=articles
```

### 示例 6：使用 MongoDB Atlas 云数据库
```bash
REDIS_URL=redis://localhost:6379/0

# MongoDB Atlas 配置
MONGODB_URI=mongodb+srv://username:password@cluster0.mongodb.net/scra?retryWrites=true&w=majority
MONGODB_DB=scra
MONGODB_COLLECTION=articles
```

### 示例 7：使用固定代理
```bash
REDIS_URL=redis://localhost:6379/0
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DB=scrabg

# 固定代理配置
PROXY_MODE=static
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

### 示例 6：使用动态代理
```bash
REDIS_URL=redis://localhost:6379/0
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DB=scrabg

# 动态代理配置
PROXY_MODE=dynamic
DYNAMIC_PROXY_API=http://api.proxy-pool.com/get
DYNAMIC_PROXY_API_METHOD=GET
DYNAMIC_PROXY_REFRESH_INTERVAL=300
```

## 安全建议

1. **不要将 `.env` 文件提交到版本控制**
   - `.env` 文件已添加到 `.gitignore`
   - 只提交 `.env.example` 作为模板

2. **使用强密码**
   - 包含大小写字母、数字和特殊字符
   - 长度至少 12 位

3. **定期更换密码**
   - 定期更新数据库和 Redis 密码

4. **限制文件权限**
   ```bash
   chmod 600 .env  # 只有所有者可以读写
   ```

5. **生产环境使用环境变量**
   - 生产环境建议使用系统环境变量而不是 `.env` 文件
   - 使用密钥管理服务（如 AWS Secrets Manager、HashiCorp Vault）

## 测试配置

配置完成后，可以使用测试脚本验证：

```bash
source scrabgs/bin/activate
python test_setup.py
```

测试脚本会检查：
- Redis 连接是否正常
- MySQL 连接是否正常
- 配置是否正确加载

## 常见问题

### Q: 密码包含 `@` 符号导致连接失败？
A: MySQL 密码用引号包裹：`MYSQL_PASSWORD="pass@word"`  
   Redis 密码需要 URL 编码：`redis://:pass%40word@host:6379/0`

### Q: 密码包含引号怎么办？
A: 使用转义：`MYSQL_PASSWORD="my\"password"` 或 `MYSQL_PASSWORD='my\'password'`

### Q: 如何验证密码是否正确？
A: 运行 `python test_setup.py` 测试连接

### Q: 数据存储优先级是什么？
A: MongoDB > MySQL > Redis 队列
   - 如果配置了 MongoDB 且连接成功，优先使用 MongoDB
   - 如果没有 MongoDB 但有 MySQL，使用 MySQL
   - 如果都没配置，数据存到 Redis 队列

### Q: MongoDB 密码包含特殊字符怎么办？
A: MongoDB URI 中的密码需要 URL 编码：
   - 原始密码: `P@ss#123`
   - URI: `mongodb://user:P%40ss%23123@host:27017`
   - 或者使用 MongoDB Atlas 提供的连接字符串

### Q: 如何切换不同的数据库？
A: 只需在 `.env` 中配置相应数据库，系统会自动选择：
   - 只用 MongoDB: 配置 `MONGODB_URI`
   - 只用 MySQL: 配置 `MYSQL_*` 参数
   - 不用数据库: 不配置数据库参数，数据存 Redis

### Q: 忘记密码怎么办？
A: 查看数据库管理员或重置密码，然后更新 `.env` 文件

### Q: 如何配置代理？
A: 在 `.env` 文件中设置 `PROXY_MODE`，然后配置相应的代理参数。详见上面的“代理配置说明”

### Q: 动态代理 API 返回错误怎么办？
A: 检查：
   1. `DYNAMIC_PROXY_API` 地址是否正确
   2. API 是否需要认证，如需要则配置 `DYNAMIC_PROXY_API_HEADERS`
   3. API 响应格式是否符合要求（参考上面的响应格式）

### Q: 代理不生效怎么办？
A: 确认：
   1. `PROXY_MODE` 已正确设置为 `static` 或 `dynamic`
   2. 如果是 static 模式，确认 `HTTP_PROXY` 或 `HTTPS_PROXY` 已配置
   3. 如果是 dynamic 模式，确认 `DYNAMIC_PROXY_API` 已配置
   4. 查看程序运行日志，确认代理是否正常加载

