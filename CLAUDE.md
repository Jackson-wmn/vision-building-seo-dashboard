# SEO Dashboard Setup Guide for Claude Code

你好！这是一个 SEO 自动监控 dashboard 模板。帮用户完成以下设置流程。

---

## 完整流程

1. 收集品牌信息
2. 跑 SEO Audit（`/seo-audit`）
3. 连接数据源（GSC、GA4、SE Ranking）
4. Build dashboard
5. 引导 GitHub 部署

---

## 第一步：收集信息

逐一询问（每次只问一个）：

1. 你的**品牌名称**是什么？（例如：Iconfit Fitness Club）
2. 你的**网站网址**是什么？（例如：https://iconfit.com.my）
3. 你有 **SE Ranking** 账号吗？（有 / 没有）
   - 如果有：你的 SE Ranking API Key 和 Audit ID 是什么？

---

## 第二步：跑 SEO Audit

收集到网址后，执行：

```
/seo-audit
```

对用户的网站做完整 SEO 分析。audit 完成后，把结果摘要保存到 `data/latest.json`，供 dashboard 使用。

---

## 第三步：连接数据源

### Google Search Console + GA4

告诉用户：

> 现在需要连接 Google 数据，这样 dashboard 每周会自动更新真实数据。

引导步骤：
1. 前往 [Google Cloud Console](https://console.cloud.google.com) → 建立新项目
2. 启用：**Google Search Console API** 和 **Google Analytics Data API**
3. IAM → 服务账号 → 建立 → 角色：查看者 → 建立密钥 → JSON → 下载
4. 把服务账号邮箱加入 GSC 权限（查看者）和 GA4 权限（查看者）
5. 问用户要他们的 `GA4_PROPERTY_ID`（`properties/` + 数字）和 `GSC_SITE_URL`（`sc-domain:yourdomain.com`）

拿到后，在本地测试连接：

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GA4_PROPERTY_ID="properties/xxxxxxxx"
export GSC_SITE_URL="sc-domain:yourdomain.com"
export SITE_URL="https://yourdomain.com"
python scripts/audit.py
```

### SE Ranking（如果用户有）

```bash
export SERANKING_API_KEY="用户的key"
export SERANKING_AUDIT_ID="用户的id"
python scripts/fetch_seranking.py
```

---

## 第四步：Build Dashboard

数据准备好后，生成 dashboard：

```bash
BRAND_NAME="用户的品牌名" SITE_URL="用户的网址" python scripts/generate_dashboard.py
```

告诉用户：打开 `docs/index.html` 在浏览器预览效果。

---

## 第五步：部署到 GitHub

### 5a. Push 到 GitHub

```bash
git init
git add .
git commit -m "My SEO Dashboard"
```

在 GitHub 建立新 repo，push 上去。

### 5b. 加入 GitHub Secrets

Settings → Secrets and variables → Actions → New repository secret：

| Secret | 内容 |
|--------|------|
| `BRAND_NAME` | 品牌名称 |
| `SITE_URL` | 网站网址 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | service account JSON 全部内容 |
| `GA4_PROPERTY_ID` | `properties/` + 数字 |
| `GSC_SITE_URL` | `sc-domain:yourdomain.com` |
| `SERANKING_API_KEY` | （选填）|
| `SERANKING_AUDIT_ID` | （选填）|
| `SERANKING_SITE_ID` | SE Ranking Project ID，用于每日关键词排名走向（选填）|

### 5c. 启用 GitHub Pages

Settings → Pages → Branch: main → Folder: /docs → Save

### 5d. 手动触发第一次运行

Actions → Weekly SEO Audit → Run workflow

等约2分钟，访问 `https://{你的GitHub用户名}.github.io/{repo名}/` 即可看到 dashboard。

---

## 注意事项

- 每周一 09:00（马来西亚时间）自动更新数据
- SE Ranking 没有账号可以跳过，其他功能照常运作
- 如果用户想要英文版 dashboard，告诉他可以修改 `scripts/generate_dashboard.py`
