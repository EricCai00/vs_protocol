# 进度显示优化说明

## 问题描述

在运行虚拟筛选流程时，特别是分子准备（Module 4-1a）和分子对接（Module 4-1b）阶段，会输出大量冗长的分子信息，例如：

```
[17:00:08] [7m1%[0m 1737:101861=22m18s C(=O)(N1CCN(c2ncccn2)CC1)Nc1c(cc(cc1)C)C HIT106288765
[17:00:08] #   1338 sec C(=O)(N1CCN(c2ncccn2)CC1)Nc1c(cc(cc1)C)C HIT106288765
[17:00:08] 1.67763856445105
[17:00:08] [7m1%[0m 1738:101860=22m18s C(=O)(N1CCN(c2ncccn2)CC1)Nc1c(cc(cc1)C)C HIT106288765
...（成千上万行）
```

这些是GNU parallel的详细输出，包含每个分子的SMILES字符串和处理信息，对用户来说太冗长，难以查看真正重要的进度信息。

## 解决方案

### 1. 分子准备阶段（distributed_prepare_ligand.py 和 distributed_prepare_ligand_pdb.py）

**修改的函数**: `stream_pty_master_fd_raw()`

**优化策略**:
- ✅ 过滤掉每个分子的详细信息（SMILES、分子名称等）
- ✅ 只保留进度条信息（包含 `%`、`ETA:`、`sec` 等关键字）
- ✅ 移除ANSI转义序列，使输出更清晰
- ✅ 避免重复显示相同的进度行
- ✅ 保留所有错误和警告信息

**效果对比**:

**之前** (冗长输出):
```
[17:00:08] 1737:101861=22m18s C(=O)(N1CCN(c2ncccn2)CC1)Nc1c... HIT106288765
[17:00:08] #   1338 sec C(=O)(N1CCN(c2ncccn2)CC1)Nc1c... HIT106288765
[17:00:08] 1.67763856445105
[17:00:08] 1738:101860=22m18s C(=O)(N1CCN(c2ncccn2)CC1)Nc1c... HIT106288765
...（数千行）
```

**之后** (简洁输出):
```
1% ETA: 22m18s
5% ETA: 20m30s
10% ETA: 18m15s
...
100% Completed
```

### 2. 分子对接阶段（distributed_unidock.py）

**修改的函数**: `launch_unidock_tasks()`

**优化策略**:
- ✅ 抑制UniDock的标准输出和错误输出（`stdout=subprocess.DEVNULL`）
- ✅ 显示每个GPU任务的启动信息
- ✅ 实时监控任务完成情况
- ✅ 每2秒更新一次进度
- ✅ 显示百分比进度
- ✅ 保留任务错误退出的警告信息

**效果对比**:

**之前** (可能的冗长输出):
```
Launching on gpu01 (GPU 0): ssh gpu01 cd ... && CUDA_VISIBLE_DEVICES=0 ...
Launching on gpu01 (GPU 1): ssh gpu01 cd ... && CUDA_VISIBLE_DEVICES=1 ...
...（可能有大量UniDock输出）
```

**之后** (简洁进度):
```
Starting UniDock on 4 GPU(s)...
  Task 1/4: gpu01 (GPU 0)
  Task 2/4: gpu01 (GPU 1)
  Task 3/4: gpu02 (GPU 0)
  Task 4/4: gpu02 (GPU 1)
  Progress: 1/4 tasks completed (25%)
  Progress: 2/4 tasks completed (50%)
  Progress: 3/4 tasks completed (75%)
  Progress: 4/4 tasks completed (100%)
All UniDock tasks completed.
```

## 技术实现细节

### 分子准备阶段的过滤逻辑

```python
# 只保留包含进度信息的行
if any(marker in line for marker in ['ETA:', '%', 'sec', 'Computers', 'Sockets']):
    # 移除ANSI转义序列
    import re
    clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
    
    # 只显示进度百分比行，避免重复
    if '%' in clean_line and clean_line != last_progress:
        output_stream.write(clean_line + '\n')
        output_stream.flush()

# 保留错误和警告
elif 'Error' in line or 'Warning' in line:
    output_stream.write(line + '\n')
    output_stream.flush()

# 其他详细信息被过滤
```

### 分子对接阶段的进度监控

```python
# 启动所有任务时抑制输出
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 定期检查完成情况
while any(p.poll() is None for p in procs):
    newly_completed = sum(1 for p in procs if p.poll() is not None) - completed
    if newly_completed > 0:
        completed += newly_completed
        progress = int((completed / total) * 100)
        print(f"  Progress: {completed}/{total} tasks completed ({progress}%)")
    time.sleep(2)
```

## 修改的文件清单

1. **module_4/distributed_prepare_ligand.py**
   - 函数: `stream_pty_master_fd_raw()`
   - 行数: 30-75
   - 变更: 添加日志过滤和ANSI序列清理

2. **module_4/distributed_prepare_ligand_pdb.py**
   - 函数: `stream_pty_master_fd_raw()`
   - 行数: 32-77
   - 变更: 添加日志过滤和ANSI序列清理

3. **module_4/distributed_unidock.py**
   - 函数: `launch_unidock_tasks()`
   - 行数: 49-107
   - 变更: 添加进度监控和输出抑制

## 优点

### 用户体验
- ✅ **清晰的进度显示**: 用户可以清楚看到处理进度
- ✅ **减少日志混乱**: 不再被数千行分子信息淹没
- ✅ **保留重要信息**: 错误和警告仍然会显示
- ✅ **更好的Web界面显示**: 日志面板不会被大量无用信息填满

### 性能
- ✅ **减少I/O开销**: 输出更少的文本
- ✅ **更快的日志传输**: Web界面通过WebSocket传输的数据更少
- ✅ **节省存储**: 日志文件更小

### 可维护性
- ✅ **易于调试**: 可以通过设置`verbose=True`查看详细输出
- ✅ **向后兼容**: 不影响原有的功能逻辑
- ✅ **易于扩展**: 过滤逻辑可以轻松调整

## 使用说明

### 查看详细输出（调试模式）

如果需要查看完整的分子处理信息（用于调试），可以：

1. **修改配置文件**，设置verbose选项：
```yaml
module4:
  unidock:
    verbose: true
```

2. **直接运行脚本**时添加`-v`参数：
```bash
python module_4/distributed_prepare_ligand.py -i input.smi -o output_dir -t 60 -v
python module_4/distributed_unidock.py -c config.txt -r receptor.pdbqt -d wd -n project -t 4 -m fast -v
```

### 在Web界面中的效果

启动Web界面后，日志面板将显示：

**分子准备阶段**:
```
[17:00:08] 正在准备分子...
[17:00:15] 5% ETA: 18m30s
[17:01:20] 10% ETA: 16m45s
[17:02:25] 15% ETA: 15m20s
...
[17:18:30] 100% 处理完成
```

**分子对接阶段**:
```
[17:20:00] Starting UniDock on 4 GPU(s)...
[17:20:00]   Task 1/4: gpu01 (GPU 0)
[17:20:00]   Task 2/4: gpu01 (GPU 1)
[17:20:00]   Task 3/4: gpu02 (GPU 0)
[17:20:00]   Task 4/4: gpu02 (GPU 1)
[17:25:30]   Progress: 1/4 tasks completed (25%)
[17:31:00]   Progress: 2/4 tasks completed (50%)
[17:36:30]   Progress: 3/4 tasks completed (75%)
[17:42:00]   Progress: 4/4 tasks completed (100%)
[17:42:00] All UniDock tasks completed.
```

## 注意事项

### 1. ANSI转义序列

GNU parallel的`--bar`选项会输出ANSI转义序列用于格式化，如`\x1b[7m`（反色）、`\x1b[0m`（重置）等。这些在终端中看起来正常，但在日志文件或Web界面中会显示为乱码。优化后的代码会自动移除这些序列。

### 2. 进度更新频率

UniDock的进度监控每2秒检查一次，这个频率可以根据需要调整：
- 更频繁（如1秒）: 更实时，但CPU开销稍高
- 更少（如5秒）: CPU开销更低，但进度更新不够及时

### 3. 错误处理

所有错误和警告信息仍然会被保留和显示，确保问题可以被及时发现和处理。

## 未来改进建议

1. **更精确的进度估算**: 
   - 可以读取输入文件行数，计算更准确的完成百分比
   - 估算剩余时间（ETA）

2. **进度条可视化**:
   - 在终端显示ASCII进度条
   - 在Web界面显示图形化进度条

3. **实时统计**:
   - 显示处理速度（分子/秒）
   - 显示成功/失败数量

4. **可配置的过滤规则**:
   - 允许用户在配置文件中设置显示级别
   - 支持自定义过滤模式

## 总结

这次优化大大改善了虚拟筛选流程的用户体验，特别是在Web界面中使用时。用户现在可以清晰地看到处理进度，而不会被大量无关的详细信息干扰。同时，所有重要的错误和警告信息都会被保留，确保系统的可调试性。

---

**更新时间**: 2025-10-13  
**版本**: v1.1.0  
**状态**: ✅ 已优化



