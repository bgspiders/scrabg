@echo off
REM 测试接口服务启动脚本 (Windows)

REM 设置环境变量
set TEST_API_PORT=5001
set TEST_API_HOST=0.0.0.0
set TEST_API_DEBUG=true

REM 启动服务
echo 正在启动测试接口服务...
echo 地址: http://localhost:5001
echo 健康检查: http://localhost:5001/health
echo 测试接口: http://localhost:5001/api/test-workflow
echo.

python test_api_server.py
