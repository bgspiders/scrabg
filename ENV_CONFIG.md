# .env 文件配置指南

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

### Q: 忘记密码怎么办？
A: 查看数据库管理员或重置密码，然后更新 `.env` 文件

