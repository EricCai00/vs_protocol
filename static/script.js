// VS Protocol Web Interface - JavaScript

// 全局变量
let socket;
let currentConfig = null;
let currentConfigName = null;
let originalConfig = null;
let autoScroll = true;

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeWebSocket();
    loadConfigs();
    setupEventListeners();
    updateStatus();
});

// WebSocket连接
function initializeWebSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('WebSocket已连接');
        addLogEntry('已连接到服务器', 'info');
    });
    
    socket.on('disconnect', function() {
        console.log('WebSocket断开连接');
        addLogEntry('与服务器断开连接', 'warning');
    });
    
    socket.on('status_update', function(status) {
        updateStatusDisplay(status);
        updateProgressDisplay(status);
    });
    
    socket.on('progress_update', function(status) {
        updateProgressDisplay(status);
    });
    
    socket.on('module_progress_update', function(data) {
        updateModuleProgress(data.module, data.progress);
    });
    
    socket.on('log_update', function(logEntry) {
        addLogEntry(logEntry.message, logEntry.level);
    });
}

// 设置事件监听器
function setupEventListeners() {
    // 配置文件选择
    document.getElementById('config-select').addEventListener('change', function() {
        loadConfig(this.value);
    });
    
    // 刷新配置列表
    document.getElementById('refresh-configs').addEventListener('click', loadConfigs);
    
    // 保存配置（覆盖当前文件）
    document.getElementById('save-config').addEventListener('click', saveConfig);
    // 另存为
    const saveAsBtn = document.getElementById('save-as-config');
    if (saveAsBtn) {
        saveAsBtn.addEventListener('click', saveConfigAs);
    }
    
    // 重置配置
    document.getElementById('reset-config').addEventListener('click', resetConfig);
    
    // 启动流程
    document.getElementById('start-btn').addEventListener('click', startPipeline);
    
    // 停止流程
    document.getElementById('stop-btn').addEventListener('click', stopPipeline);
    
    // 清空日志
    document.getElementById('clear-log').addEventListener('click', clearLog);
    
    // 下载日志
    document.getElementById('download-log').addEventListener('click', downloadLog);
    
    // 自动滚动开关
    document.getElementById('auto-scroll').addEventListener('change', function() {
        autoScroll = this.checked;
    });
    
    // 旧的YAML文本框已隐藏，这里无需监听
}

// 加载配置文件列表
function loadConfigs() {
    fetch('/api/configs')
        .then(response => response.json())
        .then(configs => {
            const select = document.getElementById('config-select');
            select.innerHTML = '<option value="">-- 选择配置文件 --</option>';
            
            configs.forEach(config => {
                const option = document.createElement('option');
                option.value = config.name;
                option.textContent = `${config.name} (${config.modified})`;
                select.appendChild(option);
            });
            
            showToast('配置列表已刷新', 'success');
        })
        .catch(error => {
            console.error('加载配置列表失败:', error);
            showToast('加载配置列表失败', 'error');
        });
}

// 加载配置文件内容
function loadConfig(configName) {
    if (!configName) {
        document.getElementById('config-content').value = '';
        currentConfig = null;
        currentConfigName = null;
        return;
    }
    
    fetch(`/api/config/${configName}`)
        .then(response => response.json())
        .then(config => {
            currentConfig = config;
            currentConfigName = configName;
            originalConfig = JSON.parse(JSON.stringify(config));
            // 渲染标签页与逐字段表单
            renderConfigTabsAndForms(config);
            showToast(`已加载配置: ${configName}`, 'success');
        })
        .catch(error => {
            console.error('加载配置失败:', error);
            showToast('加载配置失败', 'error');
        });
}

// 保存配置
function saveConfig() {
    if (!currentConfigName) {
        showToast('请先选择配置文件', 'error');
        return;
    }
    
    // 直接使用 currentConfig 保存
    fetch(`/api/config/${currentConfigName}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(currentConfig)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('配置已保存', 'success');
            originalConfig = JSON.parse(JSON.stringify(currentConfig));
        } else {
            showToast('保存失败: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('保存配置失败:', error);
        showToast('保存配置失败', 'error');
    });
}

// 重置配置
function resetConfig() {
    if (!originalConfig) {
        showToast('没有可重置的配置', 'error');
        return;
    }
    
    if (confirm('确定要重置配置吗？未保存的更改将丢失。')) {
        currentConfig = JSON.parse(JSON.stringify(originalConfig));
        renderConfigTabsAndForms(currentConfig);
        showToast('配置已重置', 'info');
    }
}

// 更新模块开关
function updateModuleSwitches(config) {
    // 新UI不再使用“模块快捷开关”区域
}

// 另存为
function saveConfigAs() {
    if (!currentConfig) {
        showToast('请先选择并加载配置', 'error');
        return;
    }
    const savePathInput = document.getElementById('save-path');
    const savePath = savePathInput ? savePathInput.value.trim() : '';
    if (!savePath) {
        showToast('请输入保存路径', 'error');
        return;
    }
    fetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ save_path: savePath, config_data: currentConfig })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showToast('已保存到: ' + data.path, 'success');
        } else {
            showToast('保存失败: ' + (data.error || '未知错误'), 'error');
        }
    })
    .catch(err => {
        console.error(err);
        showToast('保存失败: 网络错误', 'error');
    });
}

// 渲染标签页与表单
function renderConfigTabsAndForms(config) {
    const headers = document.getElementById('tab-headers');
    const contents = document.getElementById('tab-contents');
    headers.innerHTML = '';
    contents.innerHTML = '';

    // 定义分组：全局 + 各模块
    const groups = [];
    const topLevelScalars = {};
    // 收集非对象的顶层项，放到“全局”页
    Object.keys(config || {}).forEach(k => {
        const v = config[k];
        if (typeof v !== 'object' || v === null || Array.isArray(v)) {
            topLevelScalars[k] = v;
        }
    });
    groups.push({ key: '__global__', name: '全局', data: topLevelScalars });

    const order = ['library','receptor','physicochemical','admet','druglikeness','prepare_ligand','docking','result'];
    const labels = {
        library: '库预处理',
        receptor: '受体准备',
        physicochemical: '理化性质过滤',
        admet: 'ADMET过滤',
        druglikeness: '类药性预测',
        prepare_ligand: '分子准备',
        docking: '分子对接',
        result: '结果分析'
    };
    order.forEach(key => {
        if (config[key] && typeof config[key] === 'object' && !Array.isArray(config[key])) {
            groups.push({ key, name: labels[key] || key, data: config[key] });
        }
    });

    // 生成标签头和内容
    groups.forEach((g, idx) => {
        const header = document.createElement('div');
        header.className = 'tab-header' + (idx === 0 ? ' active' : '');
        header.dataset.tab = g.key;
        const title = document.createElement('span');
        title.textContent = g.name;
        header.appendChild(title);

        // 在标签上直接放一个启用checkbox（仅针对含 active/perform_preprocess 的对象）
        if (g.key !== '__global__') {
            const activeKey = 'active' in g.data ? 'active' : ('perform_preprocess' in g.data ? 'perform_preprocess' : null);
            if (activeKey) {
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.checked = !!g.data[activeKey];
                cb.addEventListener('change', function(){
                    setValueByPath(currentConfig, [g.key, activeKey], this.checked);
                });
                header.appendChild(cb);
            }
        }
        headers.appendChild(header);

        const pane = document.createElement('div');
        pane.className = 'tab-pane' + (idx === 0 ? ' active' : '');
        pane.dataset.tab = g.key;

        const formGrid = document.createElement('div');
        formGrid.className = 'form-grid';
        // 渲染对象字段（递归渲染一层嵌套）
        renderObjectFields(formGrid, g.key === '__global__' ? [] : [g.key], g.data);
        pane.appendChild(formGrid);
        contents.appendChild(pane);
    });

    // 绑定切换
    headers.querySelectorAll('.tab-header').forEach(h => {
        h.addEventListener('click', () => {
            const tab = h.dataset.tab;
            headers.querySelectorAll('.tab-header').forEach(x => x.classList.remove('active'));
            contents.querySelectorAll('.tab-pane').forEach(x => x.classList.remove('active'));
            h.classList.add('active');
            const pane = contents.querySelector(`.tab-pane[data-tab="${tab}"]`);
            if (pane) pane.classList.add('active');
        });
    });
}

function renderObjectFields(container, pathPrefix, data) {
    // 保持原顺序：不使用Object.entries()排序
    const entries = [];
    for (const k in (data || {})) {
        if (data.hasOwnProperty(k)) {
            entries.push([k, data[k]]);
        }
    }
    
    // 首先检查当前层级是否有perform_*字段
    const hasPerformFields = entries.some(([k, v]) => k.startsWith('perform_'));
    
    if (hasPerformFields) {
        // 当前层级有perform_*字段，按perform分段处理
        const segments = splitByPerformSections(data);
        segments.forEach(seg => {
            if (seg.performKey) {
                // 跳过active和perform_preprocess（已在标签上显示）
                if (seg.performKey === 'active' || seg.performKey === 'perform_preprocess') {
                    return;
                }
                
                // 有 perform_* 的小部分：用边框框起来
                const smallSection = document.createElement('div');
                smallSection.className = 'small-section';
                
                const smallTitle = document.createElement('div');
                smallTitle.className = 'small-section-title';
                
                const label = document.createElement('label');
                label.textContent = seg.performKey;
                
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = !!seg.performValue;
                
                // 根据初始状态设置disabled样式
                if (!checkbox.checked) {
                    smallSection.classList.add('disabled');
                }
                
                checkbox.addEventListener('change', function() {
                    setValueByPath(currentConfig, pathPrefix.concat([seg.performKey]), this.checked);
                    // 切换disabled样式
                    if (this.checked) {
                        smallSection.classList.remove('disabled');
                    } else {
                        smallSection.classList.add('disabled');
                    }
                });
                
                smallTitle.appendChild(label);
                smallTitle.appendChild(checkbox);
                smallSection.appendChild(smallTitle);
                
                // 渲染小部分内的字段
                const innerGrid = document.createElement('div');
                innerGrid.className = 'form-grid';
                renderFieldsOnly(innerGrid, pathPrefix, seg.fields);
                smallSection.appendChild(innerGrid);
                
                container.appendChild(smallSection);
            } else {
                // 不在perform小部分里的字段，直接渲染
                Object.keys(seg.fields).forEach(k => {
                    if (k === 'active' || k === 'perform_preprocess') {
                        return;
                    }
                    const v = seg.fields[k];
                    if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
                        // 嵌套对象，作为子模块处理
                        renderNestedModule(container, pathPrefix, k, v);
                    } else {
                        renderSingleField(container, pathPrefix, k, v);
                    }
                });
            }
        });
    } else {
        // 当前层级没有perform_*字段，按原逻辑处理
        entries.forEach(([key, value]) => {
            if (key === 'active' || key === 'perform_preprocess') {
                // 这些已在标签上呈现，不在表单重复
                return;
            }
            if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                // 子模块：占完整宽度，用分隔线分隔
                renderNestedModule(container, pathPrefix, key, value);
            } else {
                // 纯量字段：渲染控件
                renderSingleField(container, pathPrefix, key, value);
            }
        });
    }
}

// 新增：渲染嵌套模块（如unidock、deep_docking等）
function renderNestedModule(container, pathPrefix, key, value) {
    const submodule = document.createElement('div');
    submodule.className = 'submodule-section';
    
    const title = document.createElement('div');
    title.className = 'submodule-title';
    title.textContent = key;
    submodule.appendChild(title);
    
    // 检查子模块内是否有 perform_* 字段，按小部分分组
    const segments = splitByPerformSections(value);
    
    if (segments.length > 0) {
        segments.forEach(seg => {
            if (seg.performKey) {
                // 有 perform_* 的小部分：用边框框起来
                const smallSection = document.createElement('div');
                smallSection.className = 'small-section';
                
                const smallTitle = document.createElement('div');
                smallTitle.className = 'small-section-title';
                
                const label = document.createElement('label');
                label.textContent = seg.performKey;
                
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = !!seg.performValue;
                
                // 根据初始状态设置disabled样式
                if (!checkbox.checked) {
                    smallSection.classList.add('disabled');
                }
                
                checkbox.addEventListener('change', function() {
                    setValueByPath(currentConfig, pathPrefix.concat([key, seg.performKey]), this.checked);
                    // 切换disabled样式
                    if (this.checked) {
                        smallSection.classList.remove('disabled');
                    } else {
                        smallSection.classList.add('disabled');
                    }
                });
                
                smallTitle.appendChild(label);
                smallTitle.appendChild(checkbox);
                smallSection.appendChild(smallTitle);
                
                // 渲染小部分内的字段
                const innerGrid = document.createElement('div');
                innerGrid.className = 'form-grid';
                renderFieldsOnly(innerGrid, pathPrefix.concat([key]), seg.fields);
                smallSection.appendChild(innerGrid);
                
                submodule.appendChild(smallSection);
            } else {
                // 不在perform小部分里的字段，直接渲染
                const outerGrid = document.createElement('div');
                outerGrid.className = 'form-grid';
                renderFieldsOnly(outerGrid, pathPrefix.concat([key]), seg.fields);
                submodule.appendChild(outerGrid);
            }
        });
    }
    
    container.appendChild(submodule);
}

// 辅助函数：只渲染字段，不处理子模块
function renderFieldsOnly(container, pathPrefix, data) {
    const entries = [];
    for (const k in (data || {})) {
        if (data.hasOwnProperty(k)) {
            entries.push([k, data[k]]);
        }
    }
    
    entries.forEach(([key, value]) => {
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            // 嵌套对象：递归处理为子模块
            const submodule = document.createElement('div');
            submodule.className = 'submodule-section';
            
            const title = document.createElement('div');
            title.className = 'submodule-title';
            title.textContent = key;
            submodule.appendChild(title);
            
            const innerGrid = document.createElement('div');
            innerGrid.className = 'form-grid';
            renderFieldsOnly(innerGrid, pathPrefix.concat([key]), value);
            submodule.appendChild(innerGrid);
            
            container.appendChild(submodule);
        } else {
            renderSingleField(container, pathPrefix, key, value);
        }
    });
}

// 渲染单个字段
function renderSingleField(container, pathPrefix, key, value) {
    const item = document.createElement('div');
    item.className = 'form-item';
    
    const label = document.createElement('label');
    label.textContent = key;
    
    const fullPath = pathPrefix.concat([key]);
    const input = createInputForValue(value, (newVal) => {
        setValueByPath(currentConfig, fullPath, newVal);
    });
    
    // checkbox 特殊处理：label 和 input 在同一个 label 元素内
    if (typeof value === 'boolean') {
        item.className = 'form-item checkbox-item';
        label.appendChild(input);
        item.appendChild(label);
    } else {
        item.appendChild(label);
        item.appendChild(input);
    }
    
    container.appendChild(item);
}

// 按 perform_* 分段
function splitByPerformSections(obj) {
    const entries = [];
    for (const k in (obj || {})) {
        if (obj.hasOwnProperty(k)) {
            entries.push([k, obj[k]]);
        }
    }
    const segments = [];
    let current = null;
    
    entries.forEach(([k, v]) => {
        if (k.startsWith('perform_')) {
            // 开启新的小部分
            if (current) {
                segments.push(current);
            }
            current = {
                performKey: k,
                performValue: v,
                fields: {}
            };
        } else {
            if (current) {
                // 在perform小部分内
                current.fields[k] = v;
            } else {
                // 不在任何perform小部分内，创建一个无perform的段
                if (segments.length === 0 || segments[segments.length - 1].performKey) {
                    segments.push({ performKey: null, performValue: null, fields: {} });
                }
                segments[segments.length - 1].fields[k] = v;
            }
        }
    });
    
    if (current) {
        segments.push(current);
    }
    
    return segments;
}

function createInputForValue(value, onChange) {
    if (typeof value === 'boolean') {
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = value;
        cb.addEventListener('change', function(){ onChange(this.checked); });
        return cb;
    }
    if (typeof value === 'number') {
        const inp = document.createElement('input');
        inp.type = 'number';
        inp.value = value;
        inp.step = 'any';
        inp.addEventListener('input', function(){
            const v = this.value;
            const num = Number(v);
            onChange(isNaN(num) ? 0 : num);
        });
        return inp;
    }
    // 其他：文本
    const inp = document.createElement('input');
    inp.type = 'text';
    inp.value = value == null ? '' : String(value);
    inp.addEventListener('input', function(){ onChange(this.value); });
    return inp;
}

function setValueByPath(obj, pathArr, val) {
    let cur = obj;
    for (let i = 0; i < pathArr.length - 1; i++) {
        const k = pathArr[i];
        if (!(k in cur) || typeof cur[k] !== 'object' || cur[k] === null) {
            cur[k] = {};
        }
        cur = cur[k];
    }
    cur[pathArr[pathArr.length - 1]] = val;
}

// 启动流程
function startPipeline() {
    if (!currentConfigName) {
        showToast('请先选择配置文件', 'error');
        return;
    }
    
    if (confirm(`确定要启动流程吗？\n配置文件: ${currentConfigName}`)) {
        fetch('/api/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                config_name: currentConfigName
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast('流程已启动', 'success');
                document.getElementById('start-btn').disabled = true;
                document.getElementById('stop-btn').disabled = false;
            } else {
                showToast('启动失败: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('启动流程失败:', error);
            showToast('启动流程失败', 'error');
        });
    }
}

// 停止流程
function stopPipeline() {
    if (confirm('确定要停止流程吗？')) {
        fetch('/api/stop', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast('流程已停止', 'info');
                document.getElementById('start-btn').disabled = false;
                document.getElementById('stop-btn').disabled = true;
            } else {
                showToast('停止失败: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('停止流程失败:', error);
            showToast('停止流程失败', 'error');
        });
    }
}

// 更新状态显示
function updateStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(status => {
            updateStatusDisplay(status);
            updateProgressDisplay(status);
            
            // 更新日志（仅在日志数量变化时更新，避免重复渲染）
            const logContainer = document.getElementById('log-container');
            const currentLogCount = logContainer.querySelectorAll('.log-entry').length;
            if (status.log.length !== currentLogCount) {
                logContainer.innerHTML = '';
                status.log.forEach(entry => {
                    addLogEntry(entry.message, entry.level, entry.time);
                });
            }
        })
        .catch(error => {
            console.error('获取状态失败:', error);
        });
    
    // 定期更新
    setTimeout(updateStatus, 2000);
}

// 更新状态显示
function updateStatusDisplay(status) {
    const statusText = document.getElementById('status-text');
    const currentModule = document.getElementById('current-module');
    const startTime = document.getElementById('start-time');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    
    if (status.running) {
        statusText.textContent = '运行中';
        statusText.className = 'status-badge status-running';
        startBtn.disabled = true;
        stopBtn.disabled = false;
    } else {
        if (status.current_module === '完成') {
            statusText.textContent = '已完成';
            statusText.className = 'status-badge status-completed';
        } else if (status.current_module === '错误') {
            statusText.textContent = '错误';
            statusText.className = 'status-badge status-error';
        } else {
            statusText.textContent = '空闲';
            statusText.className = 'status-badge status-idle';
        }
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
    
    currentModule.textContent = status.current_module || '--';
    startTime.textContent = status.start_time ? new Date(status.start_time).toLocaleString('zh-CN') : '--';
}

// 更新进度显示
function updateProgressDisplay(status) {
    // 更新流程图
    const flowItems = document.querySelectorAll('.flow-item');
    
    // 根据当前模块高亮（预筛选三个子模块统一映射到 prescreening）
    const moduleMap = {
        '库预处理': 'library',
        '受体准备': 'receptor',
        '理化性质筛选': 'prescreening',
        'ADMET筛选': 'prescreening',
        '类药性预测': 'prescreening',
        '分子准备': 'prepare_ligand',
        '分子对接': 'docking',
        '结果分析': 'result'
    };

    const currentModuleName = status.current_module;
    const completedModules = status.completed_modules || [];

    // 清除所有状态
    flowItems.forEach(item => {
        item.classList.remove('active', 'completed');
    });

    // 设置完成的模块
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
    const IGNORED_STATES = ['初始化', '完成', '错误', '已停止'];
    if (currentModuleName && !IGNORED_STATES.includes(currentModuleName)) {
        const moduleKey = moduleMap[currentModuleName];
        if (moduleKey) {
            const item = document.querySelector(`.flow-item[data-module="${moduleKey}"]`);
            if (item) {
                // 当前活动模块优先于已完成状态
                item.classList.remove('completed');
                item.classList.add('active');
            }
        }
    }
    
    // 显示/隐藏模块进度条 - 只在当前模块运行时显示
    const prepareLigandSection = document.getElementById('prepare-ligand-section');
    const unidockSection = document.getElementById('unidock-section');
    
    // 分子准备进度条：只在分子对接模块且有prepare进度时显示
    // console.log('completedModules: ' + completedModules)
    // console.log('currentModuleName: ' + currentModuleName)
    // console.log('status.prepare_progress: ' + status.module_progress.prepare_ligand.current + ' ' + status.module_progress.prepare_ligand.total + ' ' + status.module_progress.prepare_ligand.percent)
    // console.log('status.unidock_progress: ' + status.module_progress.unidock.current + ' ' + status.module_progress.unidock.total + ' ' + status.module_progress.unidock.percent)
    if (currentModuleName === '分子对接' && status.module_progress && status.module_progress.prepare_ligand && 
        status.module_progress.prepare_ligand.percent > 0 && status.module_progress.prepare_ligand.percent < 100) {
        prepareLigandSection.style.display = 'block';
    } else {
        prepareLigandSection.style.display = 'none';
    }
    
    // 分子对接进度条：只在分子对接模块且有unidock进度时显示
    if (currentModuleName === '分子对接' && status.module_progress && status.module_progress.unidock && 
        (status.module_progress.unidock.percent > 0 && status.module_progress.unidock.percent < 100)) {
        unidockSection.style.display = 'block';
    } else {
        unidockSection.style.display = 'none';
    }
    
    // 更新模块进度
    if (status.module_progress) {
        if (status.module_progress.prepare_ligand) {
            updateModuleProgress('prepare_ligand', status.module_progress.prepare_ligand);
        }
        if (status.module_progress.unidock) {
            updateModuleProgress('unidock', status.module_progress.unidock);
        }
    }
}

// 更新模块级进度
function updateModuleProgress(module, progress) {
    if (module === 'prepare_ligand') {
        const fill = document.getElementById('prepare-ligand-fill');
        const text = document.getElementById('prepare-ligand-text');
        
        if (fill && text) {
            fill.style.width = progress.percent + '%';
            text.textContent = progress.percent + '%';
        }
    } else if (module === 'unidock') {
        const fill = document.getElementById('unidock-fill');
        const text = document.getElementById('unidock-text');
        
        if (fill && text) {
            fill.style.width = progress.percent + '%';
            text.textContent = `${progress.current}/${progress.total} (${progress.percent}%)`;
        }
    }
}

// 添加日志条目
function addLogEntry(message, level = 'info', time = null) {
    const logContainer = document.getElementById('log-container');
    const entry = document.createElement('div');
    entry.className = `log-entry log-${level}`;
    
    const timeSpan = document.createElement('span');
    timeSpan.className = 'log-time';
    timeSpan.textContent = time || new Date().toLocaleTimeString('zh-CN');
    
    const messageSpan = document.createElement('span');
    messageSpan.className = 'log-message';
    messageSpan.textContent = message;
    
    entry.appendChild(timeSpan);
    entry.appendChild(messageSpan);
    logContainer.appendChild(entry);
    
    // 自动滚动到底部
    if (autoScroll) {
        logContainer.scrollTop = logContainer.scrollHeight;
    }
}

// 清空日志
function clearLog() {
    if (confirm('确定要清空日志吗？')) {
        document.getElementById('log-container').innerHTML = '';
        showToast('日志已清空', 'info');
    }
}

// 下载日志
function downloadLog() {
    const logContainer = document.getElementById('log-container');
    const logEntries = logContainer.querySelectorAll('.log-entry');
    
    let logText = '虚拟筛选流程日志\n';
    logText += '=' .repeat(60) + '\n';
    logText += `导出时间: ${new Date().toLocaleString('zh-CN')}\n`;
    logText += '=' .repeat(60) + '\n\n';
    
    logEntries.forEach(entry => {
        const time = entry.querySelector('.log-time').textContent;
        const message = entry.querySelector('.log-message').textContent;
        logText += `[${time}] ${message}\n`;
    });
    
    const blob = new Blob([logText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `vs_protocol_log_${new Date().toISOString().replace(/:/g, '-')}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast('日志已下载', 'success');
}

// 显示提示信息
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

// 简单的对象转YAML（实际应该用专门的库）
function objectToYaml(obj, indent = 0) {
    let yaml = '';
    const spaces = '  '.repeat(indent);
    
    for (const key in obj) {
        const value = obj[key];
        
        if (value === null || value === undefined) {
            yaml += `${spaces}${key}: null\n`;
        } else if (typeof value === 'object' && !Array.isArray(value)) {
            yaml += `${spaces}${key}:\n`;
            yaml += objectToYaml(value, indent + 1);
        } else if (Array.isArray(value)) {
            yaml += `${spaces}${key}:\n`;
            value.forEach(item => {
                yaml += `${spaces}  - ${item}\n`;
            });
        } else if (typeof value === 'boolean') {
            yaml += `${spaces}${key}: ${value}\n`;
        } else if (typeof value === 'number') {
            yaml += `${spaces}${key}: ${value}\n`;
        } else {
            yaml += `${spaces}${key}: ${value}\n`;
        }
    }
    
    return yaml;
}

// 简单的YAML转对象（实际应该用专门的库）
function yamlToObject(yaml) {
    const lines = yaml.split('\n');
    const obj = {};
    const stack = [{ obj, indent: -1 }];
    
    lines.forEach(line => {
        if (!line.trim() || line.trim().startsWith('#')) return;
        
        const indent = line.search(/\S/);
        const trimmed = line.trim();
        
        if (trimmed.includes(':')) {
            const [key, ...valueParts] = trimmed.split(':');
            const value = valueParts.join(':').trim();
            
            // 弹出栈直到找到合适的父级
            while (stack.length > 1 && stack[stack.length - 1].indent >= indent) {
                stack.pop();
            }
            
            const parent = stack[stack.length - 1].obj;
            
            if (value === '' || value === 'null') {
                parent[key] = {};
                stack.push({ obj: parent[key], indent });
            } else if (value === 'true') {
                parent[key] = true;
            } else if (value === 'false') {
                parent[key] = false;
            } else if (!isNaN(value) && value !== '') {
                parent[key] = parseFloat(value);
            } else {
                parent[key] = value;
            }
        }
    });
    
    return obj;
}
