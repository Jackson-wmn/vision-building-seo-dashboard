"""Generate comprehensive HTML dashboard from latest audit data."""
import json, os, datetime

BRAND_NAME = os.environ.get('BRAND_NAME', 'My Brand')
SITE_URL   = os.environ.get('SITE_URL', '')

with open('data/latest.json') as f:
    d = json.load(f)

scores  = d['scores']
gsc     = d['gsc']
ga4     = d['ga4']
tech    = d['technical']
gen_at  = d['generated_at'][:10]

# SE Ranking data stored separately so weekly auto-run doesn't overwrite it
try:
    with open('data/seranking.json') as f:
        ser = json.load(f)
except Exception:
    ser = {}

def score_color(s):
    if s >= 70: return '#16a34a'
    if s >= 50: return '#f59e0b'
    return '#ef4444'

def score_label(s):
    if s >= 70: return '良好'
    if s >= 50: return '需改善'
    return '严重'

def bar(pct, color='#4f46e5', height=8):
    return f'<div style="background:#e5e7eb;border-radius:4px;height:{height}px;"><div style="background:{color};width:{min(float(pct),100):.0f}%;height:{height}px;border-radius:4px;transition:width 0.3s;"></div></div>'

# ── Issues checklist ──────────────────────────────────────────
issues = [
    # (category, title, status, severity, fix, effort)
    ('安全', 'REST API 用户账号外露（8个账号公开）', not tech['rest_api_exposed'], '严重', 'functions.php 加入 REST API 过滤，或用 Wordfence 封锁 /wp-json/wp/v2/users', '15分钟'),
    ('安全', '5个安全 Headers 全部缺失', tech['security_headers'] >= 5, '严重', 'Cloudflare → Transform Rules → Modify Response Header → 一次加入5个', '15分钟'),
    ('安全', 'WordPress 版本外露', not tech['wp_version_exposed'], '中', 'functions.php 加入 remove_action("wp_head","wp_generator")', '5分钟'),
    ('安全', 'xmlrpc.php 在 head 中广告', not tech['xmlrpc_advertised'], '中', 'functions.php 加入 remove_action("wp_head","rsd_link")，再用 Cloudflare WAF 封锁路径', '10分钟'),
    ('AI 可见度', 'ClaudeBot 被单独封锁（GPTBot 可进）', tech['claudebot_allowed'], '严重', 'Cloudflare → Security → WAF → 找封锁 ClaudeBot 的规则 → 删除', '5分钟'),
    ('AI 可见度', '/llms.txt 已创建', tech['has_llms_txt'], '高', 'WordPress functions.php 已加入 llms.txt 代码', '完成'),
    ('Schema', f'Organization name 未设置为品牌名', False, '高', f'Rank Math → Local SEO → Business Info → Business Name → 改为 "{BRAND_NAME}"', '5分钟'),
    ('Schema', 'Homepage 有 Article schema', False, '高', 'Rank Math → 首页 → Schema 标签 → 删除 Article 区块', '10分钟'),
    ('Schema', 'Person.sameAs 有 staging URL', False, '中', 'WordPress → 用户 → 删除 staging/cloudwaysapps.com 链接', '5分钟'),
    ('Schema', 'openingHours 格式错误', False, '低', 'Rank Math → Local SEO → Opening Hours → 检查格式', '5分钟'),
    ('本地SEO', '电话号码不一致', False, '高', '统一全站电话号码 + Google Business Profile', '30分钟'),
    ('本地SEO', 'hreflang 地区设置错误', False, '中', 'Rank Math → Titles & Meta → 检查 hreflang，加入 x-default', '15分钟'),
    ('内容', '高跳出率页面需优化', False, '高', '检查跳出率 >80% 的页面，改善内容和加载速度', '2小时'),
    ('内容', '没有团队/关于页面', False, '高', '创建团队页面，加入人员照片、资历、专长（提升 E-E-A-T）', '4小时'),
    ('内容', '博客文章内容太短', False, '中', '将热门文章扩展至1500+字', '持续'),
    ('内容', '没有隐私政策页面', False, '中', '添加 Privacy Policy 页面', '30分钟'),
    ('性能', '浏览器缓存未设置', False, '中', '缓存插件 → 浏览器缓存 → 设为 86400（1天）', '10分钟'),
    ('性能', 'JS 没有 defer', False, '中', 'Elementor → Experiments → Improved Asset Loading → 开启', '10分钟'),
] + ([
    # SE Ranking issues (dynamic, from seranking.json)
    ('链接健康', f'{ser["issues"].get("broken_4xx",{}).get("count",0)}个断链（4XX）', False, '严重', ser["issues"].get("broken_4xx",{}).get("fix","修复断链"), ser["issues"].get("broken_4xx",{}).get("effort","1小时")),
    ('链接健康', f'{ser["issues"].get("redirects_3xx",{}).get("count",0)}个内部链接经过3XX重定向', False, '中', ser["issues"].get("redirects_3xx",{}).get("fix","更新链接"), ser["issues"].get("redirects_3xx",{}).get("effort","30分钟")),
    ('多语言SEO', f'{ser["issues"].get("duplicate_titles",{}).get("count",0)}个页面标题重复', False, '高', ser["issues"].get("duplicate_titles",{}).get("fix","翻译标题"), ser["issues"].get("duplicate_titles",{}).get("effort","2小时")),
    ('多语言SEO', f'{ser["issues"].get("duplicate_descriptions",{}).get("count",0)}个 Meta Description 重复', False, '高', ser["issues"].get("duplicate_descriptions",{}).get("fix","翻译描述"), ser["issues"].get("duplicate_descriptions",{}).get("effort","2小时")),
    ('多语言SEO', f'{ser["issues"].get("missing_x_default",{}).get("count",0)}个页面缺少 x-default hreflang', False, '高', ser["issues"].get("missing_x_default",{}).get("fix","添加 hreflang"), ser["issues"].get("missing_x_default",{}).get("effort","15分钟")),
    ('域名', f'🚨 域名将于 {ser.get("domain_expiry","?")} 到期', False, '严重', '立即登入域名注册商续费！过期将导致网站完全下线', '立即'),
] if ser and ser.get('issues') and ser.get('domain_expiry') else [])

fixed_count = sum(1 for i in issues if i[2])
total_count = len(issues)
progress_pct = round(fixed_count / total_count * 100)

# Group by category
from collections import defaultdict
by_cat = defaultdict(list)
for issue in issues:
    by_cat[issue[0]].append(issue)

cat_html = ''
cat_colors = {'安全':'#ef4444','AI 可见度':'#8b5cf6','Schema':'#3b82f6','本地SEO':'#f59e0b','内容':'#10b981','性能':'#6366f1','链接健康':'#0ea5e9','多语言SEO':'#a855f7','域名':'#dc2626'}

for cat, items in by_cat.items():
    color = cat_colors.get(cat, '#888')
    fixed = sum(1 for i in items if i[2])
    rows = ''
    for _, title, status, severity, fix, effort in items:
        icon = '✅' if status else '❌'
        sev_color = '#ef4444' if severity=='严重' else '#f59e0b' if severity=='高' else '#6b7280'
        rows += f'''<tr style="border-bottom:1px solid #f3f4f6;{'opacity:0.6;' if status else ''}">
            <td style="padding:8px 10px;font-size:12px;">{icon}</td>
            <td style="padding:8px 10px;font-size:12px;{'text-decoration:line-through;color:#999;' if status else ''}">{title}</td>
            <td style="padding:8px 10px;text-align:center;"><span style="background:{sev_color}22;color:{sev_color};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">{severity}</span></td>
            <td style="padding:8px 10px;font-size:11px;color:#888;">{effort}</td>
            <td style="padding:8px 10px;font-size:11px;color:#555;max-width:200px;">{fix if not status else "已完成"}</td>
        </tr>'''
    cat_html += f'''<div style="margin-bottom:16px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
            <span style="background:{color};color:white;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:700;">{cat}</span>
            <span style="font-size:12px;color:#888;">{fixed}/{len(items)} 已修复</span>
        </div>
        <div style="background:white;border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06);">
        <table style="width:100%;border-collapse:collapse;">
            <tr style="background:#f8fafc;border-bottom:2px solid #e5e7eb;">
                <th style="padding:7px 10px;font-size:11px;color:#888;text-align:left;width:30px;"></th>
                <th style="padding:7px 10px;font-size:11px;color:#888;text-align:left;">问题</th>
                <th style="padding:7px 10px;font-size:11px;color:#888;text-align:center;width:60px;">优先级</th>
                <th style="padding:7px 10px;font-size:11px;color:#888;text-align:left;width:70px;">工时</th>
                <th style="padding:7px 10px;font-size:11px;color:#888;text-align:left;">修复方法</th>
            </tr>
            {rows}
        </table></div></div>'''

# ── Keyword table ─────────────────────────────────────────────
kw_rows = ''
for q in gsc['top_queries'][:10]:
    if q['impressions'] > 100 and q['clicks'] < 5:
        tag = '<span style="background:#fef2f2;color:#ef4444;padding:2px 6px;border-radius:4px;font-size:11px;">大机会</span>'
    elif q['position'] <= 5 and q['clicks'] > 5:
        tag = '<span style="background:#dcfce7;color:#16a34a;padding:2px 6px;border-radius:4px;font-size:11px;">保持</span>'
    elif q['position'] > 20:
        tag = '<span style="background:#fef2f2;color:#ef4444;padding:2px 6px;border-radius:4px;font-size:11px;">排名太低</span>'
    else:
        tag = '<span style="background:#fef9c3;color:#ca8a04;padding:2px 6px;border-radius:4px;font-size:11px;">优化</span>'
    pos_color = '#16a34a' if q['position'] <= 5 else '#f59e0b' if q['position'] <= 15 else '#ef4444'
    kw_rows += f'''<tr style="border-bottom:1px solid #f3f4f6;">
        <td style="padding:7px 8px;font-size:12px;">{q["query"]}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;">{int(q["impressions"]):,}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;font-weight:700;color:{'#16a34a' if q['clicks']>5 else '#ef4444' if q['clicks']==0 else '#f59e0b'};">{int(q["clicks"])}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;color:{pos_color};font-weight:700;">#{q["position"]:.0f}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;">{q["ctr"]:.1f}%</td>
        <td style="text-align:center;padding:7px 8px;">{tag}</td>
    </tr>'''

# ── GA4 page table ────────────────────────────────────────────
page_rows = ''
for p in ga4['top_pages'][:8]:
    bc = '#ef4444' if p['bounce'] > 70 else '#f59e0b' if p['bounce'] > 40 else '#16a34a'
    flag = ' ⚠️' if p['bounce'] > 80 else ''
    page_rows += f'''<tr style="border-bottom:1px solid #f3f4f6;">
        <td style="padding:7px 8px;font-size:12px;">{p["page"]}{flag}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;font-weight:600;">{p["sessions"]}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;color:{bc};font-weight:700;">{p["bounce"]:.0f}%</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;">{p["duration"]}s</td>
    </tr>'''

# ── Score category cards ──────────────────────────────────────
cat_cards = ''
for key, label in [('technical','技术 SEO'),('schema','Schema'),('content','内容质量'),('on_page','页面优化'),('performance','性能'),('ai','AI 可见度'),('images','图片')]:
    s = scores[key]
    c = score_color(s)
    lbl = score_label(s)
    cat_cards += f'''<div style="background:white;border-radius:10px;padding:14px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.06);">
        <div style="font-size:26px;font-weight:800;color:{c};">{s}</div>
        <div style="font-size:11px;font-weight:600;color:#555;margin:2px 0;">{label}</div>
        <div style="font-size:10px;color:{c};background:{c}22;padding:1px 6px;border-radius:4px;display:inline-block;">{lbl}</div>
        <div style="margin-top:8px;">{bar(s, c, 6)}</div>
    </div>'''

# ── Channel rows ──────────────────────────────────────────────
total_s = ga4['total_sessions'] or 1
ch_rows = ''
for ch in ga4['channels']:
    pct = round(ch['sessions'] / total_s * 100)
    color = '#16a34a' if ch['channel']=='Organic Search' else '#94a3b8'
    dur_min = f"{ch['duration']//60}分{ch['duration']%60}秒" if ch['duration'] >= 60 else f"{ch['duration']}秒"
    ch_rows += f'''<div style="margin-bottom:10px;">
        <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;">
            <span style="font-weight:600;color:{'#16a34a' if ch['channel']=='Organic Search' else 'inherit'};">{ch["channel"]} {'⭐' if ch['channel']=='Organic Search' else ''}</span>
            <span style="color:#888;">{ch["sessions"]}次 · 停留{dur_min} · 跳出{ch["bounce"]}%</span>
        </div>
        {bar(pct, color, 8)}
    </div>'''

# ── Priority quick wins ───────────────────────────────────────
quick_wins = [i for i in issues if not i[2] and i[5] in ['5分钟','10分钟','15分钟']]
qw_html = ''
for _, title, _, sev, fix, effort in quick_wins[:6]:
    qw_html += f'''<div style="display:flex;align-items:flex-start;gap:10px;background:white;border-radius:8px;padding:10px 12px;margin-bottom:6px;box-shadow:0 1px 2px rgba(0,0,0,.05);">
        <span style="background:#f59e0b;color:white;border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;">⚡</span>
        <div style="flex:1;">
            <div style="font-size:12px;font-weight:600;">{title}</div>
            <div style="font-size:11px;color:#888;margin-top:2px;">{fix}</div>
        </div>
        <span style="font-size:11px;color:#888;flex-shrink:0;white-space:nowrap;">{effort}</span>
    </div>'''

# ── Domain expiry alert (only shown when SE Ranking reports a real expiry date) ──
ser_issue_cards_html = "".join(f'''<div style="background:#f8fafc;border-radius:8px;padding:10px;border-left:3px solid {'#ef4444' if v['severity']=='严重' else '#f59e0b' if v['severity']=='高' else '#6b7280'};">
      <div style="font-size:11px;font-weight:700;color:#1a1a1a;">{v['label']}</div>
      <div style="font-size:20px;font-weight:800;color:{'#ef4444' if v['severity']=='严重' else '#f59e0b' if v['severity']=='高' else '#6b7280'};margin:2px 0;">{v['count']}</div>
      <div style="font-size:10px;color:#888;">{v['description'][:60]}...</div>
    </div>''' for v in ser.get("issues",{}).values())

domain_alert_html = ''
if ser.get('domain_expiry') and ser.get('domain_expiry') != 'N/A':
    domain_alert_html = f'''<div style="background:#fef2f2;border:2px solid #ef4444;border-radius:12px;padding:14px 20px;margin-bottom:14px;display:flex;align-items:center;gap:14px;">
  <span style="font-size:28px;">🚨</span>
  <div>
    <div style="font-size:14px;font-weight:800;color:#dc2626;">域名即将到期！{SITE_URL} 将于 {ser.get("domain_expiry")} 到期</div>
    <div style="font-size:12px;color:#ef4444;margin-top:3px;">若未续费，网站将完全下线，GSC 排名清零，一切 SEO 工作归零。</div>
    <div style="font-size:12px;color:#991b1b;margin-top:4px;">⚡ 立即行动：登入域名注册商 → 续费 {SITE_URL}</div>
  </div>
</div>'''

html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{BRAND_NAME} SEO Dashboard</title>
<style>
  * {{ box-sizing:border-box;margin:0;padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f1f5f9;color:#1a1a1a; }}
  .wrap {{ max-width:960px;margin:0 auto;padding:20px 16px; }}
  .card {{ background:white;border-radius:12px;padding:20px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.07); }}
  h2 {{ font-size:14px;font-weight:700;margin-bottom:14px;color:#1a1a1a; }}
  .g2 {{ display:grid;grid-template-columns:1fr 1fr;gap:14px; }}
  .g4 {{ display:grid;grid-template-columns:repeat(4,1fr);gap:10px; }}
  .g7 {{ display:grid;grid-template-columns:repeat(7,1fr);gap:8px; }}
  table {{ width:100%;border-collapse:collapse; }}
  th {{ font-size:11px;color:#888;font-weight:600;padding:6px 8px;text-align:left;border-bottom:2px solid #f3f4f6; }}
  .tag {{ padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600; }}
  @media(max-width:640px){{.g2,.g4,.g7{{grid-template-columns:1fr 1fr;}}}}
</style>
</head>
<body>
<div class="wrap">

<!-- Header -->
<div class="card" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;background:linear-gradient(135deg,#1e293b,#334155);color:white;">
  <div>
    <div style="font-size:20px;font-weight:800;">{BRAND_NAME} SEO Dashboard</div>
    <div style="font-size:12px;color:#94a3b8;margin-top:4px;">{SITE_URL} · 更新：{gen_at} · 每周一自动刷新 · 统计：过去90天</div>
  </div>
  <div style="text-align:center;background:rgba(255,255,255,.1);border-radius:12px;padding:12px 20px;">
    <div style="font-size:40px;font-weight:800;color:{score_color(scores['overall'])};">{scores['overall']}</div>
    <div style="font-size:12px;color:#94a3b8;">/ 100 SEO 总评分</div>
  </div>
</div>

<!-- CRITICAL: Domain Expiry Alert (only shown when SE Ranking reports a real expiry date) -->
{domain_alert_html}

<!-- Progress Bar -->
<div class="card" style="padding:16px 20px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
    <span style="font-size:13px;font-weight:700;">修复进度</span>
    <span style="font-size:13px;color:#888;">{fixed_count} / {total_count} 已完成 ({progress_pct}%)</span>
  </div>
  {bar(progress_pct, '#16a34a', 12)}
  <div style="display:flex;gap:16px;margin-top:10px;font-size:11px;color:#888;">
    <span>✅ {fixed_count} 已修复</span>
    <span>❌ {total_count - fixed_count} 待修复</span>
    <span>⚡ {len(quick_wins)} 个5-15分钟快速修复</span>
  </div>
</div>

<!-- Score Cards -->
<div class="g7" style="margin-bottom:14px;">{cat_cards}</div>

<!-- Quick Wins -->
<div class="card">
  <h2>⚡ 快速修复（每项15分钟内完成）</h2>
  {qw_html}
</div>

<!-- GSC + GA4 -->
<div class="g2">
  <div class="card">
    <h2>搜索表现（Google Search Console）</h2>
    <div class="g4" style="margin-bottom:14px;">
      <div style="text-align:center;background:#f8fafc;border-radius:8px;padding:10px;">
        <div style="font-size:22px;font-weight:800;color:#4f46e5;">{int(gsc["total_clicks"])}</div>
        <div style="font-size:11px;color:#888;">总点击</div>
      </div>
      <div style="text-align:center;background:#f8fafc;border-radius:8px;padding:10px;">
        <div style="font-size:22px;font-weight:800;color:#4f46e5;">{int(gsc["total_impressions"]):,}</div>
        <div style="font-size:11px;color:#888;">总曝光</div>
      </div>
      <div style="text-align:center;background:#f8fafc;border-radius:8px;padding:10px;">
        <div style="font-size:22px;font-weight:800;color:{'#ef4444' if gsc['avg_ctr']<1 else '#16a34a'};">{gsc["avg_ctr"]:.2f}%</div>
        <div style="font-size:11px;color:#888;">平均CTR</div>
      </div>
      <div style="text-align:center;background:#f8fafc;border-radius:8px;padding:10px;">
        <div style="font-size:22px;font-weight:800;color:#f59e0b;">#{gsc["avg_position"]}</div>
        <div style="font-size:11px;color:#888;">平均排名</div>
      </div>
    </div>
    <h2 style="font-size:12px;color:#888;margin-bottom:8px;">关键词机会</h2>
    <table>
      <tr><th>关键词</th><th style="text-align:center;">曝光</th><th style="text-align:center;">点击</th><th style="text-align:center;">排名</th><th style="text-align:center;">CTR</th><th style="text-align:center;">状态</th></tr>
      {kw_rows}
    </table>
  </div>
  <div class="card">
    <h2>网站流量（Google Analytics 4）</h2>
    <div style="text-align:center;margin-bottom:14px;">
      <div style="font-size:32px;font-weight:800;color:#4f46e5;">{ga4["total_sessions"]}</div>
      <div style="font-size:12px;color:#888;">总访问次数（90天）</div>
    </div>
    {ch_rows}
    <div style="background:#dcfce7;border-radius:8px;padding:8px 12px;margin:10px 0;font-size:12px;color:#16a34a;">
      💡 自然搜索访客停留时间最长，是最高质量流量来源
    </div>
    <h2 style="font-size:12px;color:#888;margin-top:12px;margin-bottom:8px;">页面表现</h2>
    <table>
      <tr><th>页面</th><th style="text-align:center;">访问</th><th style="text-align:center;">跳出率</th><th style="text-align:center;">停留</th></tr>
      {page_rows}
    </table>
  </div>
</div>

<!-- Full Checklist -->
<div class="card">
  <h2>📋 完整问题清单 & 修复指引</h2>
  <div style="background:#fef9c3;border-radius:8px;padding:10px 14px;margin-bottom:16px;font-size:12px;color:#92400e;">
    ⚠️ 优先修复「严重」和「高」优先级问题，这些对排名影响最大。每修复一项，下周 dashboard 会自动更新状态。
  </div>
  {cat_html}
</div>

<!-- SE Ranking Section -->
<div class="card">
  <h2>📊 SE Ranking 网站健康报告（{ser.get('updated_at','?')} · {ser.get('source','手动导入')}）</h2>
  <div class="g4" style="margin-bottom:16px;">
    <div style="text-align:center;background:#fef9c3;border-radius:8px;padding:12px;">
      <div style="font-size:28px;font-weight:800;color:#f59e0b;">{ser.get("health_score",0)}<span style="font-size:14px;">/100</span></div>
      <div style="font-size:11px;color:#888;">SE Ranking 健康评分</div>
    </div>
    <div style="text-align:center;background:#fef2f2;border-radius:8px;padding:12px;">
      <div style="font-size:28px;font-weight:800;color:#ef4444;">{ser.get("errors",0)}</div>
      <div style="font-size:11px;color:#888;">严重错误</div>
    </div>
    <div style="text-align:center;background:#fff7ed;border-radius:8px;padding:12px;">
      <div style="font-size:28px;font-weight:800;color:#f59e0b;">{ser.get("warnings",0)}</div>
      <div style="font-size:11px;color:#888;">警告</div>
    </div>
    <div style="text-align:center;background:#f0fdf4;border-radius:8px;padding:12px;">
      <div style="font-size:28px;font-weight:800;color:#16a34a;">{ser.get("notices",0)}</div>
      <div style="font-size:11px;color:#888;">提示</div>
    </div>
  </div>
  <div style="font-size:12px;color:#888;margin-bottom:12px;">共 {ser.get("total_issues",0)} 个问题 · 爬取 {ser.get("pages_crawled",0)} 个页面 · 发现 {ser.get("urls_found",0)} 个 URL</div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;">
    {ser_issue_cards_html}
  </div>
</div>

<!-- Footer -->
<div style="text-align:center;padding:16px;font-size:11px;color:#94a3b8;">
  数据来源：Google Search Console · Google Analytics 4 · 实时技术检测 · SE Ranking（手动导入）· 每周一 09:00（马来西亚时间）自动更新
</div>

</div>
</body>
</html>'''

os.makedirs('docs', exist_ok=True)
with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("✅ Dashboard generated at docs/index.html")
