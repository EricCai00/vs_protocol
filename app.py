#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Web Interface for VS Protocol
虚拟筛选流程的图形界面
"""
import os
import sys
import yaml
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from collections import OrderedDict
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit


# 配置YAML加载器以保持字段顺序
def ordered_load(stream, Loader=yaml.SafeLoader, object_pairs_hook=OrderedDict):
    class OrderedLoader(Loader):
        pass
    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    return yaml.load(stream, OrderedLoader)

# 配置YAML保存时也保持顺序
def ordered_dump(data, stream=None, Dumper=yaml.SafeDumper, **kwds):
    class OrderedDumper(Dumper):
        pass
    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items())
    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    OrderedDumper.add_representer(dict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)

app = Flask(__name__)
app.json.sort_keys = False
app.config['SECRET_KEY'] = 'vs_protocol_secret_key_2025'
socketio = SocketIO(app, cors_allowed_origins="*")

# 全局变量
REPO_PATH = Path(__file__).parent.resolve()
VS_PROTOCOL_SCRIPT = REPO_PATH / "vs_protocol.py"
current_process = None
current_status = {
    "running": False,
    "current_module": "",
    "progress": 0,
    "log": [],
    "start_time": None,
    "config_file": None,
    "module_progress": {
        "prepare_ligand": {"current": 0, "total": 0, "percent": 0},
        "unidock": {"current": 0, "total": 0, "percent": 0}
    }
}

# 模块列表
MODULE_INFO = {
    "library": {"name": "库预处理", "order": 0},
    "receptor": {"name": "受体准备", "order": 1},
    "physicochemical": {"name": "理化性质筛选", "order": 2},
    "admet": {"name": "ADMET筛选", "order": 3},
    "druglikeness": {"name": "类药性预测", "order": 4},
    "prepare_ligand": {"name": "分子准备", "order": 5},
    "docking": {"name": "分子对接", "order": 6},
    "result": {"name": "结果分析", "order": 7},
}


@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


@app.route('/api/configs')
def list_configs():
    """列出所有配置文件"""
    configs = []
    for file in REPO_PATH.glob("*.yaml"):
        if file.name.startswith('config'):
            configs.append({
                "name": file.name,
                "path": str(file),
                "modified": datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            })
    return jsonify(configs)


@app.route('/api/config/<config_name>')
def get_config(config_name):
    """获取配置文件内容"""
    config_path = REPO_PATH / config_name
    if not config_path.exists():
        return jsonify({"error": "配置文件不存在"}), 404
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = ordered_load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/config/<config_name>', methods=['POST'])
def save_config(config_name):
    """保存配置文件"""
    config_path = REPO_PATH / config_name
    
    try:
        config_data = request.json
        with open(config_path, 'w', encoding='utf-8') as f:
            ordered_dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return jsonify({"success": True, "message": "配置已保存"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/config/save', methods=['POST'])
def save_config_as():
    """另存为：保存配置到指定路径"""
    try:
        data = request.json or {}
        save_path = data.get('save_path')
        config_data = data.get('config_data')

        if not save_path:
            return jsonify({"error": "缺少保存路径 save_path"}), 400
        if not isinstance(config_data, dict):
            return jsonify({"error": "配置数据格式不正确"}), 400

        # 规范化路径
        save_path = os.path.expanduser(save_path)
        # 默认补全.yaml 后缀
        if not save_path.endswith('.yaml') and not save_path.endswith('.yml'):
            save_path += '.yaml'

        # 创建父目录
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            os.makedirs(save_dir, exist_ok=True)

        with open(save_path, 'w', encoding='utf-8') as f:
            ordered_dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        return jsonify({
            "success": True,
            "message": "配置已保存",
            "path": save_path,
            "name": os.path.basename(save_path)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/start', methods=['POST'])
def start_pipeline():
    """启动流程"""
    global current_process, current_status
    
    if current_status["running"]:
        return jsonify({"error": "流程正在运行中"}), 400
    
    data = request.json
    config_name = data.get('config_name')
    
    if not config_name:
        return jsonify({"error": "未指定配置文件"}), 400
    
    config_path = REPO_PATH / config_name
    if not config_path.exists():
        return jsonify({"error": "配置文件不存在"}), 404
    
    # 重置状态
    current_status = {
        "running": True,
        "current_module": "初始化",
        "progress": 0,
        "log": [],
        "start_time": datetime.now().isoformat(),
        "config_file": config_name,
        "module_progress": {
            "prepare_ligand": {"current": 0, "total": 0, "percent": 0},
            "unidock": {"current": 0, "total": 0, "percent": 0}
        },
        "completed_modules": []
    }
    
    # 在新线程中启动流程
    thread = threading.Thread(target=run_pipeline, args=(str(config_path),))
    thread.daemon = True
    thread.start()
    
    return jsonify({"success": True, "message": "流程已启动"})


@app.route('/api/stop', methods=['POST'])
def stop_pipeline():
    """停止流程"""
    global current_process, current_status
    
    if not current_status["running"]:
        return jsonify({"error": "没有正在运行的流程"}), 400
    
    if current_process:
        current_process.terminate()
        current_process = None
    
    current_status["running"] = False
    current_status["current_module"] = "已停止"
    add_log("流程已被用户停止", "warning")
    
    return jsonify({"success": True, "message": "流程已停止"})


@app.route('/api/status')
def get_status():
    """获取当前状态"""
    return jsonify(current_status)


def run_pipeline(config_path):
    """运行流程的后台任务"""
    global current_process, current_status
    try:
        add_log("开始运行流程，配置文件: {}".format(config_path), "info")
        
        # 启动子进程，设置PYTHONUNBUFFERED=1以禁用输出缓冲
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        
        current_process = subprocess.Popen(
            [sys.executable, str(VS_PROTOCOL_SCRIPT), config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            env=env
        )
        
        # 读取输出
        for line in current_process.stdout:
            line = line.strip()
            if line:
                add_log(line, "info")
                parse_progress(line)
        
        # 等待进程结束
        return_code = current_process.wait()
        
        if return_code == 0:
            current_status["progress"] = 100
            current_status["completed_modules"].append(current_status["current_module"])
            current_status["current_module"] = "完成"
            add_log("流程成功完成！", "success")
        else:
            current_status["current_module"] = "错误"
            add_log("流程异常退出，返回码: {}".format(return_code), "error")
            
    except Exception as e:
        current_status["current_module"] = "错误"
        add_log("运行出错: {}".format(str(e)), "error")
    
    finally:
        current_status["running"] = False
        current_process = None


def parse_progress(line):
    """解析日志行，更新进度"""
    global current_status
    import re
    

    # 检测模块标记
    for module_key, module_info in MODULE_INFO.items():
        # module_markers = [
        #     "MODULE {}:".format(module_info['order']),
        #     module_info['name']
        # ]
        module_markers = [f'-- MODULE {module_info["order"]}: ']

        if any(marker in line for marker in module_markers):
            # 如果切换到新模块，将之前的模块标记为已完成
            # add_log('LINE: ' + line, 'info')
            # add_log('cur status: ' + str(current_status), 'info')
            # add_log('module_info: ' + str(module_info), 'info')
            if current_status["current_module"] and current_status["current_module"] != module_info['name']:
                if current_status["current_module"] not in current_status.get("completed_modules", []):
                    current_status.setdefault("completed_modules", []).append(current_status["current_module"])
            
            current_status["current_module"] = module_info['name']
            # 计算进度百分比
            progress = int((module_info['order'] / (len(MODULE_INFO) - 1)) * 100)
            current_status["progress"] = progress
            
            # 如果进入分子对接模块，尝试读取总数
            if module_info['name'] == '分子对接':
                try:
                    config_path = REPO_PATH / current_status.get("config_file", "")
                    if config_path.exists():
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config = ordered_load(f)
                            project_name = config.get('project_name', '')
                            working_dir = config.get('working_directory', '')
                            if project_name and working_dir:
                                # list文件在 working_dir/project_name/module_4/{project_name}_list.txt
                                working_dir_expanded = Path(working_dir).expanduser()
                                list_file = working_dir_expanded / project_name / 'docking' / f"{project_name}_list.txt"
                                if list_file.exists():
                                    with open(list_file, 'r') as lf:
                                        total = sum(1 for _ in lf)
                                    current_status["module_progress"]["unidock"]["total"] = total
                                    current_status["module_progress"]["unidock"]["current"] = 0
                                    current_status["module_progress"]["unidock"]["percent"] = 0
                                    add_log(f"检测到分子对接任务，共 {total} 个分子", "info")
                                else:
                                    add_log(f"未找到分子列表文件: {list_file}", "warning")
                except Exception as e:
                    add_log(f"读取分子列表失败: {str(e)}", "warning")
            
            # 如果切换到新模块，将之前的模块标记为已完成
            # add_log('LINE: ' + line, 'info')
            # add_log('cur status: ' + str(current_status), 'info')
            # add_log('module_info: ' + str(module_info), 'info')
            # 通过WebSocket发送更新
            socketio.emit('progress_update', current_status)
            break
    
    # 解析prepare_ligand的进度（格式：0% 243:103355=50m03s ...）
    prepare_ligand_match = re.match(r'^(\d+)%\s+\d+:\d+=', line)
    if prepare_ligand_match:
        percent = int(prepare_ligand_match.group(1))
        current_status["module_progress"]["prepare_ligand"]["percent"] = percent
        socketio.emit('module_progress_update', {
            "module": "prepare_ligand",
            "progress": current_status["module_progress"]["prepare_ligand"]
        })
    
    # 解析unidock的进度（格式：Batch X size: Y）
    unidock_match = re.search(r'Batch\s+\d+\s+size:\s+(\d+)', line)
    if unidock_match:
        batch_size = int(unidock_match.group(1))
        current_status["module_progress"]["unidock"]["current"] += batch_size
        
        # 计算百分比
        if current_status["module_progress"]["unidock"]["total"] > 0:
            percent = int((current_status["module_progress"]["unidock"]["current"] / 
                          current_status["module_progress"]["unidock"]["total"]) * 100)
            current_status["module_progress"]["unidock"]["percent"] = min(percent, 100)
        else:
            # 如果还没有总数，尝试读取
            try:
                config_path = REPO_PATH / current_status.get("config_file", "")
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = ordered_load(f)
                        project_name = config.get('project_name', '')
                        working_dir = config.get('working_directory', '')
                        if project_name and working_dir:
                            working_dir_expanded = Path(working_dir).expanduser()
                            list_file = working_dir_expanded / project_name / 'docking' / f"{project_name}_list.txt"
                            if list_file.exists():
                                with open(list_file, 'r') as lf:
                                    total = sum(1 for _ in lf)
                                current_status["module_progress"]["unidock"]["total"] = total
                                # 重新计算百分比
                                if total > 0:
                                    percent = int((current_status["module_progress"]["unidock"]["current"] / total) * 100)
                                    current_status["module_progress"]["unidock"]["percent"] = min(percent, 100)
            except:
                pass
        
        socketio.emit('module_progress_update', {
            "module": "unidock",
            "progress": current_status["module_progress"]["unidock"]
        })


def add_log(message, level="info"):
    """添加日志"""
    log_entry = {
        "time": datetime.now().strftime('%H:%M:%S'),
        "level": level,
        "message": message
    }
    current_status["log"].append(log_entry)
    
    # 限制日志数量
    if len(current_status["log"]) > 1000:
        current_status["log"] = current_status["log"][-1000:]
    
    # 通过WebSocket发送日志
    socketio.emit('log_update', log_entry)


@socketio.on('connect')
def handle_connect():
    """WebSocket连接"""
    emit('status_update', current_status)


@socketio.on('request_status')
def handle_status_request():
    """客户端请求状态更新"""
    emit('status_update', current_status)


if __name__ == '__main__':
    print("=" * 60)
    print("VS Protocol Web Interface")
    print("虚拟筛选流程图形界面")
    print("=" * 60)
    print("访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    
    # 使用gevent作为异步模式
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)

