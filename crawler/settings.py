import os

# 加载 .env 文件
from crawler.utils.env_loader import load_env_file
load_env_file()

BOT_NAME = "crawler"

SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"

ROBOTSTXT_OBEY = False

# 运行参数可由 demo.json 覆盖
CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 0

# Scrapy-Redis
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
SCHEDULER_QUEUE_CLASS = "scrapy_redis.queue.FifoQueue"
SCHEDULER_PERSIST = True
# 取消去重：使用 Scrapy 的空实现，允许重复 URL 进入队列
DUPEFILTER_CLASS = "scrapy.dupefilters.BaseDupeFilter"
# 去重：使用 Scrapy 的空实现，允许重复 URL 进入队列
#DUPEFILTER_CLASS = "scrapy.dupefilters.RFPDupeFilter"


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# MySQL 配置（必填：MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB）
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "")
MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4")
MYSQL_POOL_SIZE = int(os.getenv("MYSQL_POOL_SIZE", "5"))
MYSQL_POOL_MAX_OVERFLOW = int(os.getenv("MYSQL_POOL_MAX_OVERFLOW", "5"))

# 下载中间件（包括代理中间件）
DOWNLOADER_MIDDLEWARES = {
    "crawler.middlewares.proxy_middleware.ProxyMiddleware": 100,
}

ITEM_PIPELINES = {
    "crawler.pipelines.MySQLStorePipeline": 300,
}

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 允许通过环境变量传入配置文件路径
CONFIG_PATH = os.getenv("CONFIG_PATH", "demo.json")

