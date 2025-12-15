#!/bin/bash
# 快速启动脚本 - 用于测试项目

set -e

echo "=========================================="
echo "Scrapy-Redis 分布式爬虫系统 - 快速启动"
echo "=========================================="
echo ""

# 检查虚拟环境是否存在
if [ ! -d "scrabgs" ]; then
    echo "📦 创建虚拟环境 scrabgs..."
    python3 -m venv scrabgs
    echo "✅ 虚拟环境创建成功"
else
    echo "✅ 虚拟环境已存在"
fi

# 激活虚拟环境
echo ""
echo "🔧 激活虚拟环境..."
source scrabgs/bin/activate

# 安装依赖
echo ""
echo "📥 安装依赖包..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✅ 依赖安装完成"

# 运行测试
echo ""
echo "🧪 运行环境测试..."
python test_setup.py

echo ""
echo "=========================================="
echo "快速启动完成！"
echo "=========================================="
echo ""
echo "下一步："
echo "1. 设置环境变量（参考 README.md）"
echo "2. 准备数据库表（运行 test_data.sql）"
echo "3. 启动爬虫："
echo "   source scrabgs/bin/activate"
echo "   scrapy crawl config_spider"
echo ""

