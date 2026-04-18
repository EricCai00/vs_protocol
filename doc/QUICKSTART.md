# 快速开始指南

## 🚀 5分钟快速启动

### 1. 安装依赖

```bash
cd /public/home/caiyi/eric_github/vs_protocol
pip install -r requirements.txt
```

### 2. 启动Web界面

**方法一：使用启动脚本（推荐）**
```bash
./start_web.sh
```

**方法二：直接运行**
```bash
python app.py
```

**方法三：后台运行**
```bash
nohup python app.py > web_server.log 2>&1 &
```

### 3. 访问界面

打开浏览器访问：
```
http://localhost:5000
```

如果在远程服务器上，使用：
```
http://<服务器IP>:5000
```

## 📝 基本使用流程

### Step 1: 选择配置文件
1. 在左侧面板的下拉菜单中选择配置文件（如 `config_loose.yaml`）
2. 配置会自动加载到编辑器中

### Step 2: 编辑配置（可选）
1. 直接在文本框中编辑配置
2. 或使用下方的模块快捷开关
3. 点击"💾 保存配置"保存更改

### Step 3: 启动流程
1. 点击右侧的"▶️ 启动流程"按钮
2. 确认后流程开始运行

### Step 4: 监控进度
- 查看进度条和流程图
- 实时查看运行日志
- 可随时停止流程

## 🎯 主要功能

### 配置管理
- ✅ 加载/保存YAML配置
- ✅ 模块快捷开关
- ✅ 配置重置

### 流程控制
- ✅ 一键启动/停止
- ✅ 实时状态监控
- ✅ 进度可视化

### 日志系统
- ✅ 实时日志显示
- ✅ 日志分级（info/success/warning/error）
- ✅ 日志导出

## 📂 项目文件结构

```
vs_protocol/
├── app.py                 # Flask应用（Web服务器）
├── vs_protocol.py         # 原虚拟筛选流程脚本
├── start_web.sh          # 启动脚本
├── requirements.txt       # Python依赖
├── README_WEB.md         # 详细文档
├── QUICKSTART.md         # 本文件
├── templates/
│   └── index.html        # 网页模板
├── static/
│   ├── style.css         # 样式文件
│   └── script.js         # JavaScript脚本
└── config_*.yaml         # 配置文件
```

## ⚙️ 配置文件示例

最小配置示例：
```yaml
working_directory: /path/to/working/dir
project_name: my_project
start_module: physicochemical
receptor_pdb: /path/to/receptor.pdb
library_smiles: /path/to/library.smi

library:
  perform_preprocess: false
  threads: 60

module1:
  active: true
  perform_phychem_predict: true
  threads: 60

# ... 其他模块配置
```

## 🔧 常见问题

### Q: 无法访问Web界面？
A: 检查防火墙设置，确保5000端口开放

### Q: 流程启动失败？
A: 检查配置文件路径是否正确，查看日志面板的错误信息

### Q: 如何停止服务器？
A: 按 `Ctrl+C` 或使用 `kill` 命令

### Q: 如何查看后台日志？
A: `tail -f web_server.log`

## 📞 获取帮助

详细文档请查看：
- [README_WEB.md](README_WEB.md) - 完整使用文档
- [vs_protocol.py](vs_protocol.py) - 原始流程脚本

## 🎨 界面预览

```
┌─────────────────────────────────────────────────────────┐
│        🧬 虚拟筛选流程管理系统                            │
│           VS Protocol Web Interface                     │
└─────────────────────────────────────────────────────────┘

┌──────────────────┬──────────────────────────────────────┐
│  📋 配置管理      │  🚀 流程控制                          │
│                  │  ▶️ 启动流程  ⏹️ 停止流程             │
│  配置文件选择     │                                      │
│  [config_loose]  │  状态: 运行中                         │
│                  │  当前模块: 分子对接                    │
│  配置编辑器       │                                      │
│  [YAML编辑框]    │  📊 运行进度                          │
│                  │  ████████░░ 80%                       │
│  模块快捷开关     │                                      │
│  ☑ 理化性质      │  [流程可视化图]                       │
│  ☑ ADMET        │  1→2→3→4→[5]→6→7→8→9                 │
│  ☑ 分子对接      │                                      │
│                  │  📝 运行日志                          │
│                  │  [10:30:15] 开始对接...               │
│                  │  [10:30:20] 处理分子1000/5000        │
└──────────────────┴──────────────────────────────────────┘
```

## 🎉 开始使用

现在你已经准备好了！运行 `./start_web.sh` 开始使用吧！

