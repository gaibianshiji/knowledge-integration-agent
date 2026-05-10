# Vercel 部署修复方案

## 问题

- PDF 教材 32-418MB，远超 Vercel 4.5MB body 限制
- Vercel 文件系统只读，数据无法持久化
- 已解析的数据（8.5MB JSON + 12KB 图谱）被 .gitignore 排除

## 方案：预加载数据到部署包

### 核心思路

**不依赖文件上传，直接把已解析的数据打包进部署。** 教材已经本地解析完成，只需：
1. 把解析后的 JSON 数据提交到 git
2. 后端启动时自动加载这些数据
3. 前端页面加载时显示已有教材

### 改动清单

#### 1. 修改 .gitignore（允许数据文件）
- 取消 `backend/data/parsed/` 和 `backend/data/graphs/` 的忽略
- 保留 `*.pdf` 和 `backend/data/uploads/` 的忽略（不提交原始 PDF）

#### 2. 提交数据文件
- `backend/data/parsed/*.json`（8.5MB，7 个教材）
- `backend/data/graphs/*.json`（12KB，知识图谱）

#### 3. 修改后端启动逻辑（`backend/app/main.py`）
- 添加 startup 事件，自动从磁盘加载已解析的教材数据到内存
- 这样 Vercel 每次冷启动时都能加载数据

#### 4. 前端自动加载教材列表
- `App.jsx` 的 `loadTextbooks()` 已经会调用 API，无需改动

#### 5. 限制文件上传大小
- `upload.py` 添加 4MB 文件大小限制
- 添加提示信息

### 不需要改的
- 不需要 Vercel Blob
- 不需要改部署平台
- 不需要重写前端
- 不需要改 API 接口

### 时间估算
- 修改代码：15 分钟
- 提交 + 部署：10 分钟
- 验证：5 分钟
- **总计：30 分钟**

### 验证标准
- [ ] 0hacthon.vercel.app 能正常打开
- [ ] 左侧显示 7 本教材
- [ ] 知识图谱能构建和展示
- [ ] RAG 问答能正常工作
- [ ] 跨教材整合能正常工作
