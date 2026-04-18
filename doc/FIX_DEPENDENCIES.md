# 依赖问题修复指南

## 问题描述

启动时遇到以下错误：
```
AttributeError: module 'lib' has no attribute 'X509_V_FLAG_NOTIFY_POLICY'
```

## 原因分析

这是 `eventlet` 与 `pyOpenSSL` 版本不兼容导致的问题。在Python 3.9+环境中，`eventlet` 可能与系统的OpenSSL库产生冲突。

## 解决方案

我已经将依赖从 `eventlet` 切换到 `gevent`，这是一个更稳定的异步库。

## 修复步骤

### 步骤1：卸载旧依赖

```bash
pip uninstall -y eventlet
```

### 步骤2：安装新依赖

```bash
pip install -r requirements.txt
```

### 一键修复（推荐）

```bash
pip uninstall -y eventlet && pip install -r requirements.txt
```

## 验证修复

安装完成后，重新启动服务：

```bash
./start_web.sh
```

应该能看到：
```
======================================
VS Protocol Web Interface
虚拟筛选流程图形界面
======================================

检查依赖...

启动Web服务器...
访问地址: http://localhost:5000
按 Ctrl+C 停止服务器
======================================

 * Serving Flask app 'app'
 * Debug mode: off
...
```

## 其他可能的问题

### 问题1：gevent安装失败

**原因**：缺少编译工具

**解决**：
```bash
# CentOS/RHEL
sudo yum install gcc python3-devel

# Ubuntu/Debian
sudo apt-get install gcc python3-dev

# 然后重新安装
pip install gevent
```

### 问题2：权限错误

**解决**：
```bash
pip install --user -r requirements.txt
```

### 问题3：版本冲突

**解决**：创建虚拟环境
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

## 更新内容

### requirements.txt 变更

**之前：**
```
eventlet==0.33.3
```

**之后：**
```
gevent==23.9.1
gevent-websocket==0.10.1
```

### app.py 变更

- 将 `debug=True` 改为 `debug=False`（gevent在debug模式下可能有问题）
- 其他代码无需修改，gevent与eventlet API兼容

## 性能对比

| 特性 | eventlet | gevent |
|------|----------|--------|
| 稳定性 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Python 3.9+兼容 | ⚠️ 有问题 | ✅ 完美 |
| WebSocket支持 | ✅ | ✅ |
| 性能 | 好 | 好 |
| 维护状态 | 活跃度低 | 活跃 |

## 快速参考

```bash
# 完整修复流程
cd /public/home/caiyi/eric_github/vs_protocol
pip uninstall -y eventlet
pip install -r requirements.txt
./start_web.sh
```

## 验证成功

如果看到以下输出，说明修复成功：
```
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.x.x:5000
```

然后在浏览器访问 http://localhost:5000 即可使用界面。

---

**更新时间**: 2025-10-13  
**状态**: ✅ 已修复

