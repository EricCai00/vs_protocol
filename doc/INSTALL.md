# 安装指南

## 📦 依赖安装

### 方法一：使用pip安装（推荐）

```bash
cd /public/home/caiyi/eric_github/vs_protocol
pip install -r requirements.txt
```

### 方法二：手动安装

```bash
pip install Flask==3.0.0
pip install flask-socketio==5.3.5
pip install python-socketio==5.10.0
pip install eventlet==0.33.3
pip install PyYAML==6.0.1
```

### 方法三：使用conda安装

```bash
conda install flask flask-socketio pyyaml -c conda-forge
pip install eventlet python-socketio
```

## ✅ 验证安装

运行以下命令检查依赖是否正确安装：

```bash
python -c "import flask; import flask_socketio; import yaml; print('✅ 所有依赖安装成功！')"
```

如果看到 "✅ 所有依赖安装成功！"，说明安装完成。

## 🚀 启动服务

安装完成后，使用以下命令启动Web服务：

```bash
# 方法1：使用启动脚本
./start_web.sh

# 方法2：直接运行
python app.py

# 方法3：后台运行
nohup python app.py > web_server.log 2>&1 &
```

## 🌐 访问界面

启动后，在浏览器中访问：
- 本地访问：http://localhost:5000
- 远程访问：http://<服务器IP>:5000

## 📋 系统要求

- Python 2.7 或 Python 3.6+
- 至少 1GB 可用内存
- 支持的操作系统：Linux, macOS, Windows

## 🔧 可能的问题

### 问题1：pip安装失败

**解决方案：**
```bash
# 升级pip
pip install --upgrade pip

# 使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题2：权限错误

**解决方案：**
```bash
# 使用用户安装
pip install --user -r requirements.txt

# 或使用sudo（不推荐）
sudo pip install -r requirements.txt
```

### 问题3：端口被占用

**解决方案：**
```bash
# 查看5000端口占用
lsof -i :5000

# 杀死占用进程
kill -9 <PID>

# 或修改app.py中的端口号
# socketio.run(app, host='0.0.0.0', port=5001)
```

### 问题4：防火墙阻止访问

**解决方案：**
```bash
# CentOS/RHEL
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload

# Ubuntu
sudo ufw allow 5000/tcp
```

## 📞 获取帮助

如果遇到其他问题，请查看：
- [QUICKSTART.md](QUICKSTART.md) - 快速开始指南
- [README_WEB.md](README_WEB.md) - 详细使用文档

或联系项目维护者。

