-- 测试数据 SQL 脚本
-- 用于快速创建测试表和插入测试数据

-- 创建文章基本信息表
CREATE TABLE IF NOT EXISTS articles (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_id VARCHAR(32),
    title TEXT,
    link TEXT,
    link_hash VARCHAR(32),
    source_url TEXT,
    extra JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_created_at (created_at),
    INDEX idx_link_hash (link_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文章基本信息表';

-- 拆分正文内容到独立表
CREATE TABLE IF NOT EXISTS article_contents (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    article_id BIGINT NOT NULL,
    content LONGTEXT,
    content_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_article_id (article_id),
    INDEX idx_content_hash (content_hash),
    CONSTRAINT fk_article_contents_article_id FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文章内容表';

-- 创建待抓取请求表（如果不存在）
CREATE TABLE IF NOT EXISTS pending_requests (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    url TEXT NOT NULL,
    method VARCHAR(10) DEFAULT 'GET',
    headers_json TEXT,
    params_json TEXT,
    meta_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='待抓取请求表';

-- 插入测试请求数据
INSERT INTO pending_requests (url, method, headers_json, meta_json) VALUES
('https://news.bjx.com.cn/yw/', 'GET', '{"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"}', '{"test": true, "source": "test_data"}'),
('https://www.example.com/', 'GET', '{"User-Agent": "Mozilla/5.0"}', '{"test": true}');

-- 查看插入的数据
SELECT * FROM pending_requests;

