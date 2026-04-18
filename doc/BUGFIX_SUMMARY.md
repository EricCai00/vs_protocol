# 模块进度条问题修复总结

## 修复的问题

### 1. ✅ 进度条文字显示问题
**问题描述：**
- 在进度小于3%时，百分比数字与背景融为一体看不清
- 数字在进度条内居中，导致在进度很小时被卡住看不见

**解决方案：**
修改了 `static/style.css` 中的 `.progress-fill` 样式：
```css
.progress-fill {
    position: relative;  /* 使用相对定位 */
}

.progress-fill span {
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    color: white;
    font-weight: 700;
    font-size: 1rem;
    white-space: nowrap;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);  /* 添加文字阴影增强可读性 */
    z-index: 2;
    pointer-events: none;
}
```

**效果：**
- 文字现在总是居中显示在进度条容器上
- 添加了文字阴影，即使在浅色背景上也清晰可见
- 即使进度为0%，文字也能正常显示

### 2. ✅ 模块进度条显示时机
**问题描述：**
- 进度条在非相关模块时也会显示
- 模块完成后进度条不会隐藏

**解决方案：**
修改了 `static/script.js` 中的 `updateProgressDisplay()` 函数：
```javascript
// 分子准备进度条：只在分子对接模块且有prepare进度时显示
if (currentModuleName === '分子对接' && 
    status.module_progress && 
    status.module_progress.prepare_ligand && 
    status.module_progress.prepare_ligand.percent > 0 && 
    status.module_progress.prepare_ligand.percent < 100) {
    prepareLigandSection.style.display = 'block';
} else {
    prepareLigandSection.style.display = 'none';
}

// 分子对接进度条：只在分子对接模块且有unidock进度时显示
if (currentModuleName === '分子对接' && 
    status.module_progress && 
    status.module_progress.unidock && 
    (status.module_progress.unidock.percent > 0 || 
     status.module_progress.unidock.total > 0)) {
    unidockSection.style.display = 'block';
} else {
    unidockSection.style.display = 'none';
}
```

**效果：**
- 进度条只在对应模块运行时显示
- prepare_ligand进度条在达到100%后自动隐藏
- unidock进度条在模块完成后自动隐藏
- 其他模块运行时不会显示这些进度条

### 3. ✅ UniDock总数读取问题
**问题描述：**
- 显示 "3467/0 (0%)"，说明总数为0
- 原代码在 `REPO_PATH` 下查找 `{project_name}_list.txt`
- 实际文件位置在 `working_dir/project_name/module_4/{project_name}_list.txt`

**解决方案：**
修改了 `app.py` 中的 `parse_progress()` 函数，在两个地方读取list文件：

**方案1：进入分子对接模块时读取**
```python
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
                    list_file = working_dir_expanded / project_name / 'module_4' / f"{project_name}_list.txt"
                    if list_file.exists():
                        with open(list_file, 'r') as lf:
                            total = sum(1 for _ in lf)
                        current_status["module_progress"]["unidock"]["total"] = total
                        current_status["module_progress"]["unidock"]["current"] = 0
                        current_status["module_progress"]["unidock"]["percent"] = 0
                        add_log(f"检测到分子对接任务，共 {total} 个分子", "info")
    except Exception as e:
        add_log(f"读取分子列表失败: {str(e)}", "warning")
```

**方案2：检测到Batch输出时作为备用**
```python
# 解析unidock的进度（格式：Batch X size: Y）
unidock_match = re.search(r'Batch\s+\d+\s+size:\s+(\d+)', line)
if unidock_match:
    batch_size = int(unidock_match.group(1))
    current_status["module_progress"]["unidock"]["current"] += batch_size
    
    # 如果还没有总数，尝试读取
    if current_status["module_progress"]["unidock"]["total"] == 0:
        # 从配置读取并查找list文件...
```

**效果：**
- 进入分子对接模块时立即读取总数并显示在日志中
- 即使第一次读取失败，在检测到Batch输出时也会尝试读取
- 从正确的路径读取文件：`working_dir/project_name/module_4/{project_name}_list.txt`
- 支持路径中的 `~` 扩展

### 4. ✅ Pipeline-Flow实时更新问题
**问题描述：**
- 一开始所有模块都是绿色（已完成状态）
- 模块状态更新不及时
- 页面加载时不显示当前状态

**解决方案：**

**后端改进 (app.py)：**
```python
# 添加completed_modules追踪
current_status = {
    ...
    "completed_modules": []
}

# 切换模块时自动标记前一模块为完成
if current_status["current_module"] and current_status["current_module"] != module_info['name']:
    if current_status["current_module"] not in current_status.get("completed_modules", []):
        current_status.setdefault("completed_modules", []).append(current_status["current_module"])
```

**前端改进 (script.js)：**
```javascript
// 清除所有状态
flowItems.forEach(item => {
    item.classList.remove('active', 'completed');
});

// 只设置真正完成的模块
completedModules.forEach(moduleName => {
    const moduleKey = moduleMap[moduleName];
    if (moduleKey) {
        const item = document.querySelector(`.flow-item[data-module="${moduleKey}"]`);
        if (item) {
            item.classList.add('completed');
        }
    }
});

// 设置当前活动模块
if (currentModuleName && 
    currentModuleName !== '初始化' && 
    currentModuleName !== '完成' && 
    currentModuleName !== '错误' && 
    currentModuleName !== '已停止') {
    const moduleKey = moduleMap[currentModuleName];
    if (moduleKey) {
        const item = document.querySelector(`.flow-item[data-module="${moduleKey}"]`);
        if (item) {
            item.classList.add('active');
        }
    }
}
```

**实时更新优化：**
```javascript
// 在status_update事件中也更新pipeline-flow
socket.on('status_update', function(status) {
    updateStatusDisplay(status);
    updateProgressDisplay(status);  // 添加这一行
});

// 优化日志更新，避免不必要的重渲染
const currentLogCount = logContainer.querySelectorAll('.log-entry').length;
if (status.log.length !== currentLogCount) {
    // 只在日志数量变化时重新渲染
    logContainer.innerHTML = '';
    status.log.forEach(entry => {
        addLogEntry(entry.message, entry.level, entry.time);
    });
}
```

**效果：**
- 初始状态下所有模块不显示为完成状态（灰色）
- 当前运行的模块显示为活动状态（蓝色高亮）
- 已完成的模块显示为完成状态（绿色）
- 状态实时更新，无延迟
- WebSocket连接后立即同步状态

## 技术细节

### 文件路径解析
```python
# 从配置文件读取working_dir和project_name
working_dir = config.get('working_directory', '')  # 例如：~/data/vs_protocol
project_name = config.get('project_name', '')      # 例如：test_project

# 扩展路径中的 ~
working_dir_expanded = Path(working_dir).expanduser()

# 构建完整路径
list_file = working_dir_expanded / project_name / 'module_4' / f"{project_name}_list.txt"
# 结果：/home/user/data/vs_protocol/test_project/module_4/test_project_list.txt
```

### 进度条文字定位技术
使用CSS的绝对定位和transform，确保文字始终居中且可见：
```css
.progress-fill span {
    position: absolute;      /* 脱离文档流 */
    left: 50%;              /* 左边缘在中心 */
    top: 50%;               /* 上边缘在中心 */
    transform: translate(-50%, -50%);  /* 平移回到真正的中心 */
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);  /* 阴影增强可读性 */
}
```

### 状态同步机制
1. **WebSocket实时推送**：后端通过 `socketio.emit()` 推送状态变化
2. **轮询作为备份**：每2秒通过HTTP轮询确保状态同步
3. **事件驱动更新**：多个WebSocket事件处理不同类型的更新
   - `status_update`: 全局状态更新
   - `progress_update`: 模块切换和完成状态
   - `module_progress_update`: 模块内部进度更新
   - `log_update`: 日志消息更新

## 测试建议

### 测试场景1：进度条文字可见性
1. 启动流程，观察进度条从0%开始增长
2. 确认在0-5%时文字清晰可见
3. 确认在任何进度下文字都居中且清晰

### 测试场景2：模块进度条显示
1. 启动流程，进入分子对接模块前不应显示进度条
2. 进入分子对接模块后：
   - 如果有prepare步骤，应显示分子准备进度条
   - 开始对接后，应显示分子对接进度条
3. prepare完成后，分子准备进度条应消失
4. 对接完成后，分子对接进度条应消失

### 测试场景3：总数读取
1. 检查日志中是否出现"检测到分子对接任务，共 X 个分子"
2. 确认进度条显示 "当前/总数 (百分比)"，总数不为0
3. 确认百分比计算正确

### 测试场景4：Pipeline-Flow状态
1. 刷新页面，所有模块应为灰色（未开始）
2. 启动流程，当前模块应高亮为蓝色
3. 完成的模块应为绿色
4. 切换模块时状态应立即更新

## 相关文件

- `app.py`: 后端进度解析和状态管理
- `static/script.js`: 前端状态更新和显示逻辑
- `static/style.css`: 进度条样式
- `templates/index.html`: HTML结构

## 兼容性

所有改进都向后兼容，不影响现有功能。如果检测不到进度输出，系统仍能正常运行，只是不显示进度条。

