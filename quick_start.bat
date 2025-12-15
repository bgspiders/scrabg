@echo off
REM 快速启动脚本 - Windows 版本

echo ==========================================
echo Scrapy-Redis 分布式爬虫系统 - 快速启动
echo ==========================================
echo.

REM 检查虚拟环境是否存在
if not exist "scrabgs" (
    echo 📦 创建虚拟环境 scrabgs...
    python -m venv scrabgs
    echo ✅ 虚拟环境创建成功
) else (
    echo ✅ 虚拟环境已存在
)

REM 激活虚拟环境
echo.
echo 🔧 激活虚拟环境...
call scrabgs\Scripts\activate.bat

REM 安装依赖
echo.
echo 📥 安装依赖包...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
echo ✅ 依赖安装完成

REM 运行测试
echo.
echo 🧪 运行环境测试...
python test_setup.py

echo.
echo ==========================================
echo 快速启动完成！
echo ==========================================
echo.
echo 下一步：
echo 1. 设置环境变量（参考 README.md）
echo 2. 准备数据库表（运行 test_data.sql）
echo 3. 启动爬虫：
echo    scrabgs\Scripts\activate
echo    scrapy crawl config_spider
echo.

pause

