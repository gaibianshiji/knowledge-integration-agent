# Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the 学科知识整合智能体 to production with Cloudflare Pages (frontend) and Railway (backend).

**Architecture:** Frontend is a React SPA built with Vite, deployed to Cloudflare Pages. Backend is a FastAPI Python app deployed to Railway. Frontend communicates with backend via API proxy.

**Tech Stack:** React, Vite, FastAPI, Python, Cloudflare Pages, Railway

---

## File Structure

```
F:\0hacthon\
├── backend/
│   ├── app/                    # FastAPI application (existing)
│   ├── requirements.txt        # Python dependencies (existing)
│   ├── Procfile               # Railway process file (existing)
│   └── railway.toml           # Railway config (existing)
├── frontend/
│   ├── src/                   # React source (existing)
│   ├── public/
│   │   └── _redirects         # Cloudflare Pages proxy (existing)
│   ├── package.json           # Node dependencies (existing)
│   └── vite.config.js         # Vite config (existing)
├── .gitignore                 # Git ignore rules (existing)
└── README.md                  # Project docs (existing)
```

---

### Task 1: Push Code to GitHub

**Files:**
- Modify: `.gitignore` (verify rules)
- Create: GitHub repository

- [ ] **Step 1: Verify git status**

Run: `cd F:/0hacthon && git status`
Expected: Clean working tree, on branch master

- [ ] **Step 2: Add remote and push**

```bash
cd F:/0hacthon
git remote add origin https://github.com/gaibianshiji/knowledge-integration-agent.git
git push -u origin master
```

Expected: Code pushed to GitHub successfully

- [ ] **Step 3: Verify repository is public**

Visit: https://github.com/gaibianshiji/knowledge-integration-agent
Expected: Repository exists and is public

---

### Task 2: Deploy Backend to Railway

**Files:**
- Modify: `backend/.env` (add DEEPSEEK_API_KEY)
- Verify: `backend/Procfile` exists
- Verify: `backend/railway.toml` exists

- [ ] **Step 1: Visit Railway and login**

Visit: https://railway.app
Action: Login with GitHub account

- [ ] **Step 2: Create new project**

Action: Click "New Project" → "Deploy from GitHub repo"
Select: `gaibianshiji/knowledge-integration-agent`
Set Root Directory: `backend`

- [ ] **Step 3: Add environment variable**

Action: Click "Variables" tab
Add: `DEEPSEEK_API_KEY` = (your DeepSeek API key)

- [ ] **Step 4: Wait for deployment**

Expected: Build completes successfully
Expected: Service is running
Action: Copy the deployment URL (e.g., `https://xxx.up.railway.app`)

- [ ] **Step 5: Verify backend health**

Run: `curl https://YOUR_RAILWAY_URL/api/health`
Expected: `{"status":"ok"}`

---

### Task 3: Deploy Frontend to Cloudflare Pages

**Files:**
- Modify: `frontend/public/_redirects` (update backend URL)
- Modify: `frontend/.env.production` (update API base)

- [ ] **Step 1: Update _redirects with Railway URL**

Edit `frontend/public/_redirects`:
```
/api/*  https://YOUR_RAILWAY_URL/api/:splat  200
```

- [ ] **Step 2: Commit and push changes**

```bash
cd F:/0hacthon
git add frontend/public/_redirects
git commit -m "Update _redirects with Railway backend URL"
git push
```

- [ ] **Step 3: Visit Cloudflare Pages**

Visit: https://dash.cloudflare.com
Action: Go to "Workers & Pages" → "Create application" → "Pages"

- [ ] **Step 4: Connect GitHub repository**

Action: Click "Connect to Git"
Select: `gaibianshiji/knowledge-integration-agent`

- [ ] **Step 5: Configure build settings**

Set:
- Framework preset: `Vite`
- Build command: `npm run build`
- Build output directory: `dist`
- Root directory: `frontend`

- [ ] **Step 6: Add environment variable**

Action: Click "Environment variables"
Add: `VITE_API_BASE` = `https://YOUR_RAILWAY_URL/api`

- [ ] **Step 7: Deploy**

Action: Click "Save and Deploy"
Expected: Build completes successfully
Action: Copy the deployment URL (e.g., `https://xxx.pages.dev`)

---

### Task 4: Verify Production Deployment

- [ ] **Step 1: Open frontend URL**

Visit: https://YOUR_CLOUDFLARE_URL
Expected: Application loads correctly

- [ ] **Step 2: Test file upload**

Action: Upload a textbook PDF
Expected: File uploads and parses successfully

- [ ] **Step 3: Test knowledge graph**

Action: Click "全部构建"
Expected: Knowledge graph builds and displays

- [ ] **Step 4: Test RAG query**

Action: Click "构建向量索引", then ask a question
Expected: Returns answer with citations

- [ ] **Step 5: Test integration**

Action: Click "执行跨教材整合"
Expected: Integration completes with statistics

---

### Task 5: Update Documentation

**Files:**
- Modify: `README.md` (add deployment URLs)

- [ ] **Step 1: Update README with deployment info**

Add to README.md:
```markdown
## Live Demo

- Frontend: https://YOUR_CLOUDFLARE_URL
- Backend API: https://YOUR_RAILWAY_URL/api
- API Docs: https://YOUR_RAILWAY_URL/docs
```

- [ ] **Step 2: Commit and push**

```bash
cd F:/0hacthon
git add README.md
git commit -m "Update README with deployment URLs"
git push
```

---

### Task 6: Final Submission

- [ ] **Step 1: Prepare submission**

Collect:
- GitHub repo URL: https://github.com/gaibianshiji/knowledge-integration-agent
- Deployment URL: https://YOUR_CLOUDFLARE_URL

- [ ] **Step 2: Submit to hackathon**

Action: Fill submission form with:
- Name
- Student ID
- GitHub repo link
- Deployment link

- [ ] **Step 3: Verify submission**

Expected: Confirmation email or submission status
