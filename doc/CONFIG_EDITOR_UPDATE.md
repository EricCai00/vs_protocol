# 配置编辑器UI更新说明

## 更新时间
2025-10-14

## 主要改进

### 1. 标签页式布局
- 配置按模块分为多个标签页（全局、库预处理、受体准备、各个module等）
- 每个标签页包含该模块的所有配置项
- 标签上直接显示模块启用/禁用的复选框

### 2. 逐字段编辑控件
- **布尔值**：checkbox（与label同行显示）
- **数字**：number输入框（支持小数）
- **字符串**：text输入框
- 所有字段按原YAML顺序显示，不按字母排序

### 3. 子模块与小部分的层级显示

#### 子模块（Submodule）
- 占完整两列宽度
- 用分隔线（border-top）与其他内容分隔
- 标题用蓝色加粗显示
- 示例：`module3`中的`substructure`、`similarity`、`druglikeness`

#### 小部分（Small Section）
- 由`perform_*`字段定义（如`perform_substruct`、`perform_simi`等）
- 用蓝色边框框起来，带浅蓝色背景
- 标题包含启用/禁用复选框
- 包含从该`perform_*`到下一个`perform_*`之间的所有配置项
- 可以存在于模块内或子模块内

#### 普通字段
- 不在任何小部分内的字段直接显示，不强制归入"其他"分组
- 按原YAML顺序排列

### 4. 保存功能

#### 保存当前文件
- 点击"💾 保存当前文件"按钮
- 直接覆盖当前加载的配置文件
- 后端API: `POST /api/config/<config_name>`

#### 另存为
- 在"另存为路径"输入框中输入完整路径
- 点击"💾 另存为"按钮
- 可保存到任意位置
- 自动补全`.yaml`后缀
- 后端API: `POST /api/config/save`
  - 参数: `save_path`, `config_data`

### 5. 样式优化

#### 工具栏
- "另存为"输入框和按钮高度统一（8px padding）
- 按钮文字不会溢出
- 输入框自适应宽度

#### 表单网格
- 两列布局（移动端自适应为单列）
- 子模块和小部分自动占满整行
- 合理的间距和padding

#### 颜色主题
- 子模块标题：主题蓝色（#2563eb）
- 小部分边框：主题蓝色
- 小部分背景：浅蓝色（rgba(37, 99, 235, 0.03)）
- 分隔线：边框灰色（#e2e8f0）

## 技术实现

### 前端逻辑

#### 保持YAML原始顺序
```javascript
const entries = [];
for (const k in (data || {})) {
    if (data.hasOwnProperty(k)) {
        entries.push([k, data[k]]);
    }
}
```

#### perform_*分段算法
1. 遍历对象的键值对（保持原顺序）
2. 遇到`perform_*`开头的键时，开始新的小部分
3. 后续字段归入当前小部分，直到遇到下一个`perform_*`
4. 不在任何`perform_*`后的字段保持独立，不强制分组

#### 值更新机制
```javascript
function setValueByPath(obj, pathArr, val) {
    // 按路径数组深度遍历并设置值
    // 支持嵌套对象的更新
}
```

### 后端接口

#### 新增接口：另存为
```python
@app.route('/api/config/save', methods=['POST'])
def save_config_as():
    data = request.json
    save_path = data.get('save_path')
    config_data = data.get('config_data')
    
    # 规范化路径，补全.yaml后缀
    # 创建父目录
    # 写入YAML文件
    
    return jsonify({
        "success": True,
        "path": save_path,
        "name": os.path.basename(save_path)
    })
```

## 使用示例

### 1. 加载配置
1. 从下拉菜单选择配置文件（如`config_loose.yaml`）
2. 配置自动加载并渲染为标签页和表单

### 2. 编辑配置
- **切换标签页**：点击标签头切换不同模块
- **启用/禁用模块**：直接在标签上勾选/取消checkbox
- **启用/禁用小部分**：在小部分标题处勾选checkbox
- **修改值**：直接在输入框中输入新值
- **修改布尔值**：勾选/取消checkbox

### 3. 保存配置

#### 覆盖当前文件
```
1. 编辑配置
2. 点击"💾 保存当前文件"
3. 确认提示
```

#### 另存为新文件
```
1. 编辑配置
2. 在"另存为路径"输入框输入路径，例如：
   - /public/home/caiyi/eric_github/vs_protocol/config_new.yaml
   - config_test.yaml （会保存到项目根目录）
3. 点击"💾 另存为"
4. 查看成功提示
```

## 文件结构示例

### 配置层级
```
module3 (标签页)
  └─ substructure (子模块 - 用分隔线)
      ├─ perform_substruct (小部分 - 用边框框起来)
      │   └─ substruct_list (字段)
      └─ ... 其他字段
  └─ similarity (子模块 - 用分隔线)
      ├─ perform_simi (小部分 - 用边框框起来)
      │   ├─ similarity_query (字段)
      │   ├─ num_threads (字段)
      │   ├─ radius (字段)
      │   └─ threshold (字段)
      └─ ... 其他字段
  └─ druglikeness (子模块 - 用分隔线)
      ├─ perform_dln_pred (小部分 - 用边框框起来)
      │   └─ ... 字段
      └─ perform_dln_filter (小部分 - 用边框框起来)
          ├─ gpu_num (字段)
          ├─ dln_count_lower (字段)
          └─ verbose (字段)
```

## CSS类说明

| 类名 | 用途 | 样式特点 |
|------|------|----------|
| `.tab-headers` | 标签页头部容器 | flex布局，可换行 |
| `.tab-header` | 单个标签 | 圆角按钮样式，active时蓝色 |
| `.tab-contents` | 标签页内容容器 | 边框、圆角、padding |
| `.tab-pane` | 单个标签页内容 | display:none，active时显示 |
| `.form-grid` | 表单网格 | 两列布局，响应式 |
| `.form-item` | 单个表单项 | 垂直布局 |
| `.checkbox-item` | checkbox表单项 | 水平布局，label在前 |
| `.submodule-section` | 子模块容器 | 占满整行，顶部分隔线 |
| `.submodule-title` | 子模块标题 | 蓝色加粗，底部分隔线 |
| `.small-section` | 小部分容器 | 蓝色边框，浅蓝背景 |
| `.small-section-title` | 小部分标题 | 包含checkbox |

## 注意事项

1. **路径输入**：另存为时请输入完整路径或相对项目根目录的路径
2. **YAML后缀**：如果未输入`.yaml`或`.yml`后缀，系统会自动补全`.yaml`
3. **权限**：确保对目标路径有写入权限
4. **原始顺序**：所有配置项严格按照YAML文件中的原始顺序显示
5. **实时更新**：修改任何字段都会立即更新内存中的配置对象

## 浏览器兼容性

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

使用了现代CSS特性（grid、flexbox、CSS变量）和ES6+ JavaScript特性。

## 未来改进建议

1. **字段验证**：添加输入验证（范围检查、格式校验等）
2. **字段说明**：鼠标悬停显示字段说明文档
3. **下拉选项**：某些字段提供预定义选项（如`search_mode`）
4. **配置比较**：对比两个配置文件的差异
5. **配置模板**：提供常用配置模板快速创建
6. **撤销/重做**：支持配置编辑的撤销和重做
7. **搜索过滤**：在大型配置中快速定位字段

---

**版本**: v2.0.0  
**状态**: ✅ 已完成  
**测试状态**: 待用户测试
