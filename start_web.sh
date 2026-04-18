#!/bin/bash
# VS Protocol Web Interface 启动脚本

echo "======================================"
echo "VS Protocol Web Interface"
echo "虚拟筛选流程图形界面"
echo "======================================"
echo ""

# 检查Python
if ! command -v python &> /dev/null; then
    echo "错误: 未找到Python"
    exit 1
fi

# 检查依赖
echo "检查依赖..."
python -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Flask未安装，正在安装依赖..."
    pip install -r requirements.txt
fi

echo ""
echo "启动Web服务器..."
echo "访问地址: http://localhost:5000"
echo "按 Ctrl+C 停止服务器"
echo "======================================"
echo ""

# 启动服务器
python app.py

