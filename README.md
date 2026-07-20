# SEO Auto Dashboard Template

每周一自动更新的 SEO 监控 dashboard，数据来自 Google Search Console + GA4 + SE Ranking。

**公开访问：** `https://{你的GitHub用户名}.github.io/{repo名}/`

---

## 功能

- **Google Search Console** — 关键词排名、点击、曝光、CTR（每周自动）
- **Google Analytics 4** — 流量来源、页面表现、跳出率（每周自动）
- **技术检测** — Security Headers、AI 爬虫、llms.txt、REST API（每周自动）
- **SE Ranking** — 健康评分、断链、重复标题、域名到期（每周自动，需 SE Ranking API）
- **问题清单 + 修复指引** — 全中文，按优先级排列

---

## 快速开始（约30分钟完成）

### 第一步：使用这个模板

点右上角 **"Use this template"** → **"Create a new repository"**

### 第二步：建立 Google API 权限

1. 前往 [Google Cloud Console](https://console.cloud.google.com) → 建立新项目
2. 启用两个 API：
   - **Google Search Console API**
   - **Google Analytics Data API**
3. IAM → 服务账号 → 建立 → 角色：查看者 → 建立 → 密钥 → JSON → 下载
4. 把 Service Account 邮箱加入 GSC 和 GA4 的权限（查看者）

### 第三步：在 GitHub 加入 Secrets

进入你的 repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret 名称 | 内容 | 必须？ |
|------------|------|--------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | service account JSON 文件的全部内容 | ✅ |
| `GA4_PROPERTY_ID` | `properties/` + 数字，例如 `properties/508017836` | ✅ |
| `GSC_SITE_URL` | `sc-domain:yourdomain.com` | ✅ |
| `SITE_URL` | `https://yourdomain.com` | ✅ |
| `BRAND_NAME` | 品牌名称，例如 `Iconfit Fitness Club` | ✅ |
| `SERANKING_API_KEY` | SE Ranking API Key（选填）| ⬜ |
| `SERANKING_AUDIT_ID` | SE Ranking Audit ID（选填）| ⬜ |
| `SERANKING_SITE_ID` | SE Ranking Project ID，用于每日关键词排名走向（选填）| ⬜ |

### 第四步：启用 GitHub Pages

repo → **Settings → Pages → Branch: main → Folder: /docs → Save**

### 第五步：手动触发第一次运行

repo → **Actions → Weekly SEO Audit → Run workflow**

等约2分钟，访问你的 GitHub Pages 链接即可看到 dashboard！

---

## 自动更新时间表

| 内容 | 频率 |
|------|------|
| GSC + GA4 + 技术检测 | 每周一 09:00（马来西亚时间，UTC+8）|
| SE Ranking 数据 | 每周一同步（需填 SERANKING_API_KEY）|

如需调整时间，修改 `.github/workflows/seo-audit.yml` 里的 cron 设定。

---

## 手动更新 SE Ranking（无 API 版）

如果没有 SE Ranking API，可以手动上传 PDF：

```bash
pip install pdfplumber
python3 scripts/update_seranking.py /path/to/audit.pdf
git add data/seranking.json docs/index.html
git commit -m "Update SE Ranking"
git push
```

---

## 常见问题

| 问题 | 解决方法 |
|------|---------|
| git push 被拒绝 | 必须用 Classic Token，勾选 `repo` + `workflow` |
| Actions 报错（GSC）| 确认 service account 已加入 GSC 权限 |
| Actions 报错（GA4）| 确认已启用 Google Analytics Data API |
| Pages 显示 404 | Settings → Pages → 选 /docs 目录 |
| Dashboard 没更新 | `Cmd+Shift+R` 强制刷新 |

---

Made with ❤️ by [ARMS](https://bearms.today)
