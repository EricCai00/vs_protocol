# 模块进度条实现说明

## 概述
本次更新为prepare_ligand（分子准备）和unidock（分子对接）模块添加了独立的进度条，替代了原有的全局进度条，并修正了pipeline-flow的初始状态显示问题。

## 主要改进

### 1. 后端改进 (app.py)

#### 新增状态跟踪
在 `current_status` 中添加了两个新字段：
- `module_progress`: 存储各模块的进度信息
  - `prepare_ligand`: 分子准备进度（百分比）
  - `unidock`: 分子对接进度（当前数量/总数/百分比）
- `completed_modules`: 已完成的模块列表

#### 进度解析增强
在 `parse_progress()` 函数中添加了两种模块级进度的解析：

**分子准备 (prepare_ligand)**
- 匹配格式：`0% 243:103355=50m03s N1(C(=O)...`
- 正则表达式：`r'^(\d+)%\s+\d+:\d+='`
- 提取第一个字段的百分比值

**分子对接 (unidock)**
- 匹配格式：`Batch 28 size: 254`
- 正则表达式：`r'Batch\s+\d+\s+size:\s+(\d+)'`
- 累加每个批次的大小
- 从 `{project_name}_list.txt` 读取总分子数
- 自动计算完成百分比

#### 模块状态跟踪
- 当切换到新模块时，自动将前一个模块标记为已完成
- 当进入分子对接模块时，自动读取总分子数并记录到日志

#### WebSocket事件
新增 `module_progress_update` 事件，用于实时推送模块级进度更新。

### 2. 前端改进 (script.js)

#### 更新进度显示逻辑
- 移除了全局进度条的显示和更新逻辑
- 添加了 `updateModuleProgress()` 函数处理模块级进度
- 监听新的 `module_progress_update` WebSocket事件

#### Pipeline-Flow状态修正
**修正前的问题：**
- 一开始所有模块都显示为完成状态（绿色）
- 只有在完成一个模块后才会更新状态

**修正后的行为：**
- 初始状态下，所有模块都不显示完成或活动状态
- 只有实际完成的模块才显示为绿色（completed）
- 当前正在运行的模块显示为活动状态（active）
- 未开始的模块保持默认状态

#### 模块进度条显示控制
- prepare_ligand 进度条：仅在分子对接模块运行时或有进度数据时显示
- unidock 进度条：仅在分子对接模块运行时或有进度数据时显示
- 进度条显示格式：
  - prepare_ligand: `X%`
  - unidock: `当前数量/总数量 (X%)`

### 3. HTML改进 (templates/index.html)

#### 进度显示区域重构
移除了原有的全局进度条，添加了两个模块级进度条：

```html
<!-- 分子准备进度 -->
<div class="module-progress-section" id="prepare-ligand-section" style="display: none;">
    <h3>分子准备 (Prepare Ligand)</h3>
    <div class="progress-container">
        <div class="progress-bar">
            <div id="prepare-ligand-fill" class="progress-fill" style="width: 0%">
                <span id="prepare-ligand-text">0%</span>
            </div>
        </div>
    </div>
</div>

<!-- 分子对接进度 -->
<div class="module-progress-section" id="unidock-section" style="display: none;">
    <h3>分子对接 (UniDock)</h3>
    <div class="progress-container">
        <div class="progress-bar">
            <div id="unidock-fill" class="progress-fill" style="width: 0%">
                <span id="unidock-text">0/0 (0%)</span>
            </div>
        </div>
    </div>
</div>
```

### 4. 样式改进 (static/style.css)

添加了模块进度条的专用样式：

```css
.module-progress-section {
    margin-bottom: 25px;
    padding: 15px;
    background: var(--bg-color);
    border-radius: 10px;
    border: 1px solid var(--border-color);
}

.module-progress-section h3 {
    font-size: 1.1rem;
    margin: 0 0 12px 0;
    color: var(--primary-color);
    font-weight: 600;
}
```

## 使用说明

### 运行流程
1. 启动流程后，pipeline-flow 会根据实际进度更新状态
2. 进入分子对接模块时，系统会自动：
   - 读取 `{project_name}_list.txt` 获取总分子数
   - 在日志中显示总分子数
   - 显示分子准备和分子对接的进度条
3. 进度条会实时更新：
   - 分子准备：显示 GNU parallel 报告的百分比
   - 分子对接：显示已完成的分子数量和百分比

### 日志输出识别
系统会自动识别以下格式的输出：

**分子准备输出示例：**
```
0% 243:103355=50m03s N1(C(=O)c2cc3c(nccc3)cc2)CC(=O)N(C2(C1)CCOCC2)CC HIT105008518
5% 486:103355=45m12s ...
10% 729:103355=40m30s ...
```

**分子对接输出示例：**
```
Batch 28 size: 254
Batch 29 size: 305
Batch 30 size: 198
```

## 技术细节

### 进度计算
- **prepare_ligand**: 直接使用输出中的百分比
- **unidock**: 
  - 累加所有批次的 size 值
  - 总数从 `{project_name}_list.txt` 读取
  - 百分比 = (当前累计 / 总数) × 100

### 状态同步
- 使用 WebSocket 进行实时双向通信
- 后端通过 `socketio.emit()` 推送更新
- 前端通过 `socket.on()` 接收更新并更新UI

### 容错处理
- 如果无法读取总分子数，进度条仍然会显示已处理的数量
- 使用 try-except 包装所有文件读取操作
- 在日志中记录错误信息但不中断流程

## 兼容性
- 所有更改向后兼容
- 不影响其他模块的运行
- 如果检测不到进度输出，进度条会保持隐藏状态

## 未来改进建议
1. 可以考虑为其他耗时模块也添加类似的进度条
2. 可以添加预计剩余时间（ETA）显示
3. 可以添加进度历史图表
4. 可以添加进度暂停/恢复功能

