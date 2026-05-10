# 部署指南

## 方案一：Cloudflare Pages + Railway（推荐）

### 第一步：部署后端到 Railway

1. **访问 [railway.app](https://railway.app)** 并用GitHub登录

2. **创建新项目**：
   - 点击 "New Project"
   - 选择 "Deploy from GitHub repo"
   - 如果没有看到仓库，先在GitHub上创建仓库并推送代码

3. **配置项目**：
   - Root Directory: `backend`
   - Build Command: 自动检测（pip install -r requirements.txt）
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

4. **添加环境变量**：
   - 点击 "Variables" 标签
   - 添加: `DEEPSEEK_API_KEY` = 你的 DeepSeek API Key

5. **部署**：
   - Railway会自动部署
   - 等待部署完成，获取后端URL（如 `https://xxx.up.railway.app`）

### 第二步：部署前端到 Cloudflare Pages

1. **访问 [dash.cloudflare.com](https://dash.cloudflare.com)**

2. **创建Pages项目**：
   - 进入 "Workers & Pages"
   - 点击 "Create application"
   - 选择 "Pages"
   - 连接GitHub仓库

3. **配置构建设置**：
   - Framework preset: `Vite`
   - Build command: `npm run build`
   - Build output directory: `dist`
   - Root directory: `frontend`

4. **添加环境变量**：
   - 点击 "Environment variables"
   - 添加: `VITE_API_BASE` = `https://你的Railway后端URL/api`

5. **部署**：
   - 点击 "Save and Deploy"
   - 等待部署完成，获取前端URL

### 第三步：更新 _redirects 文件

编辑 `frontend/public/_redirects`，将 `your-railway-backend` 替换为你的Railway后端URL：

```
/api/*  https://你的Railway后端URL/api/:splat  200
```

然后重新部署前端。

---

## 方案二：GitHub Pages（纯前端，需修改架构）

如果只需要展示前端，可以将后端API改为Serverless Functions。

---

## 方案三：本地演示

如果时间紧张，可以直接用本地环境演示：

```bash
# 启动后端
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 启动前端
cd frontend
npm run dev
```

访问 http://localhost:3000

---

## 提交清单

- [ ] GitHub仓库链接（公开）
- [ ] 在线部署链接
- [ ] README.md 包含完整说明
- [ ] docs/Agent架构说明.md
- [ ] docs/需求分析.md
- [ ] docs/系统设计.md
- [ ] report/整合报告.md
