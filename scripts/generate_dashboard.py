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

# Keyword rankings, refreshed daily independently of the weekly audit above
try:
    with open('data/keywords.json') as f:
        kws = json.load(f)
except Exception:
    kws = {}

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

# ── Issues checklist (only real, dynamically-detected issues) ──
issues = [
    # (category, title, status, severity, fix, effort)
    ('安全', f'REST API 用户账号外露（{tech.get("rest_api_users",0)}个账号公开）', not tech['rest_api_exposed'], '严重', 'functions.php 加入 REST API 过滤，或用 Wordfence 封锁 /wp-json/wp/v2/users', '15分钟'),
    ('安全', f'{5-tech["security_headers"]}个安全 Headers 缺失', tech['security_headers'] >= 5, '严重', 'Cloudflare → Transform Rules → Modify Response Header → 补齐缺失的 headers', '15分钟'),
    ('安全', 'WordPress 版本外露', not tech['wp_version_exposed'], '中', 'functions.php 加入 remove_action("wp_head","wp_generator")', '5分钟'),
    ('安全', 'xmlrpc.php 在 head 中广告', not tech['xmlrpc_advertised'], '中', 'functions.php 加入 remove_action("wp_head","rsd_link")，再用 Cloudflare WAF 封锁路径', '10分钟'),
    ('AI 可见度', 'ClaudeBot 被单独封锁（GPTBot 可进）', tech['claudebot_allowed'], '严重', 'Cloudflare → Security → WAF → 找封锁 ClaudeBot 的规则 → 删除', '5分钟'),
    ('AI 可见度', '/llms.txt 已创建', tech['has_llms_txt'], '高', 'WordPress functions.php 加入 llms.txt 代码', '完成'),
] + ([
    # SE Ranking issues (dynamic, from seranking.json — status is "fixed" when count is 0)
    ('链接健康', f'{ser["issues"].get("broken_4xx",{}).get("count",0)}个断链（4XX）', ser["issues"].get("broken_4xx",{}).get("count",0)==0, '严重', ser["issues"].get("broken_4xx",{}).get("fix","修复断链"), ser["issues"].get("broken_4xx",{}).get("effort","1小时")),
    ('链接健康', f'{ser["issues"].get("redirects_3xx",{}).get("count",0)}个内部链接经过3XX重定向', ser["issues"].get("redirects_3xx",{}).get("count",0)==0, '中', ser["issues"].get("redirects_3xx",{}).get("fix","更新链接"), ser["issues"].get("redirects_3xx",{}).get("effort","30分钟")),
    ('链接健康', f'{ser["issues"].get("internal_links_3xx",{}).get("count",0)}个内部链接指向重定向页', ser["issues"].get("internal_links_3xx",{}).get("count",0)==0, '中', ser["issues"].get("internal_links_3xx",{}).get("fix","更新链接"), ser["issues"].get("internal_links_3xx",{}).get("effort","30分钟")),
    ('页面质量', f'{ser["issues"].get("duplicate_titles",{}).get("count",0)}个页面标题重复', ser["issues"].get("duplicate_titles",{}).get("count",0)==0, '高', ser["issues"].get("duplicate_titles",{}).get("fix","改写重复标题"), ser["issues"].get("duplicate_titles",{}).get("effort","2小时")),
    ('页面质量', f'{ser["issues"].get("duplicate_descriptions",{}).get("count",0)}个 Meta Description 重复', ser["issues"].get("duplicate_descriptions",{}).get("count",0)==0, '高', ser["issues"].get("duplicate_descriptions",{}).get("fix","改写重复描述"), ser["issues"].get("duplicate_descriptions",{}).get("effort","2小时")),
    ('页面质量', f'{ser["issues"].get("duplicate_h1",{}).get("count",0)}个页面 H1 重复', ser["issues"].get("duplicate_h1",{}).get("count",0)==0, '中', ser["issues"].get("duplicate_h1",{}).get("fix","改写重复 H1"), ser["issues"].get("duplicate_h1",{}).get("effort","1小时")),
    ('页面质量', f'{ser["issues"].get("slow_pages",{}).get("count",0)}个页面加载速度慢', ser["issues"].get("slow_pages",{}).get("count",0)==0, '高', ser["issues"].get("slow_pages",{}).get("fix","优化加载速度"), ser["issues"].get("slow_pages",{}).get("effort","持续")),
    ('页面质量', f'{ser["issues"].get("sitemap_missing",{}).get("count",0)}个 XML Sitemap 问题', ser["issues"].get("sitemap_missing",{}).get("count",0)==0, '严重', ser["issues"].get("sitemap_missing",{}).get("fix","生成并提交 sitemap"), ser["issues"].get("sitemap_missing",{}).get("effort","10分钟")),
] if ser and ser.get('issues') else []) + ([
    ('域名', f'🚨 域名将于 {ser.get("domain_expiry")} 到期', False, '严重', '立即登入域名注册商续费！过期将导致网站完全下线', '立即'),
] if ser.get('domain_expiry') and ser.get('domain_expiry') != 'N/A' else [])

fixed_count = sum(1 for i in issues if i[2])
total_count = len(issues)
progress_pct = round(fixed_count / total_count * 100)

# Group by category
from collections import defaultdict
by_cat = defaultdict(list)
for issue in issues:
    by_cat[issue[0]].append(issue)

cat_html = ''
cat_colors = {'安全':'#ef4444','AI 可见度':'#8b5cf6','链接健康':'#0ea5e9','页面质量':'#a855f7','域名':'#dc2626'}

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

# ── Keyword rankings (daily, from keywords.json) ────────────────
def kw_delta_badge(delta):
    if delta > 0:  return f'<span style="color:#16a34a;font-weight:700;">▲ {delta}</span>'
    if delta < 0:  return f'<span style="color:#ef4444;font-weight:700;">▼ {abs(delta)}</span>'
    return '<span style="color:#888;">– 0</span>'

def kw_row(k):
    page = (k.get('landing_page','') or '-').replace(SITE_URL, '') or '/'
    return f'''<tr style="border-bottom:1px solid #f3f4f6;">
        <td style="padding:7px 8px;font-size:12px;">{k['keyword']}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;font-weight:700;">#{k['position']}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;">{kw_delta_badge(k['delta'])}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;">{k.get('volume',0)}</td>
        <td style="padding:7px 8px;font-size:11px;color:#888;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{page}</td>
    </tr>'''

def opp_row(k):
    action = f"排名 #{k['position']}，月搜索量 {k.get('volume',0)}，已进前30名，加强内链/更新内容有机会冲进前10"
    return f'''<tr style="border-bottom:1px solid #f3f4f6;">
        <td style="padding:7px 8px;font-size:12px;">{k['keyword']}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;font-weight:700;color:#f59e0b;">#{k['position']}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;">{k.get('volume',0)}</td>
        <td style="padding:7px 8px;font-size:11px;color:#555;">{action}</td>
    </tr>'''

def sel_row(k):
    page = (k.get('landing_page','') or '-').replace(SITE_URL, '') or '/'
    if k['position'] <= 10:
        status = '<span style="background:#dcfce7;color:#16a34a;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">✅ Top10</span>'
    else:
        status = f'<span style="background:#fef2f2;color:#ef4444;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">距前10还差{k["position"]-10}名</span>'
    return f'''<tr style="border-bottom:1px solid #f3f4f6;">
        <td style="padding:7px 8px;font-size:12px;">{k['keyword']}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;font-weight:700;">#{k['position']}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;">{kw_delta_badge(k['delta'])}</td>
        <td style="text-align:center;padding:7px 8px;font-size:12px;">{k.get('volume',0)}</td>
        <td style="text-align:center;padding:7px 8px;">{status}</td>
        <td style="padding:7px 8px;font-size:11px;color:#888;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{page}</td>
    </tr>'''

no_kw_row5 = '<tr><td colspan="5" style="padding:10px;font-size:12px;color:#888;">暂无数据</td></tr>'
movers_up_rows      = "".join(kw_row(k) for k in kws.get('movers_up', [])) or no_kw_row5
movers_down_rows    = "".join(kw_row(k) for k in kws.get('movers_down', [])) or no_kw_row5
opportunities_rows  = "".join(opp_row(k) for k in kws.get('opportunities', [])) or '<tr><td colspan="4" style="padding:10px;font-size:12px;color:#888;">暂无符合条件的机会词</td></tr>'
kw_updated = kws.get('updated_at','')[:10]

sel = kws.get('selected')
selected_keyword_html = ''
if sel and sel.get('keywords'):
    sel_rows = "".join(sel_row(k) for k in sel['keywords'])
    selected_keyword_html = f'''<div class="card">
  <h2>🎯 重点关键词监控 <span id="sel-date-label" style="font-size:11px;color:#888;font-weight:400;">（客户指定关键词 · {kw_updated} 数据）</span></h2>
  <div class="g4" style="margin-bottom:16px;">
    <div style="text-align:center;background:#f8fafc;border-radius:8px;padding:12px;">
      <div id="sel-stat-total" style="font-size:24px;font-weight:800;color:#4f46e5;">{sel["total"]}</div>
      <div style="font-size:11px;color:#888;">重点关键词数</div>
    </div>
    <div style="text-align:center;background:#f0fdf4;border-radius:8px;padding:12px;">
      <div id="sel-stat-top10" style="font-size:24px;font-weight:800;color:#16a34a;">{sel["top10_count"]}</div>
      <div style="font-size:11px;color:#888;">已进前10</div>
    </div>
    <div style="text-align:center;background:#fef2f2;border-radius:8px;padding:12px;">
      <div id="sel-stat-remaining" style="font-size:24px;font-weight:800;color:#ef4444;">{sel["total"]-sel["top10_count"]}</div>
      <div style="font-size:11px;color:#888;">尚未进前10</div>
    </div>
    <div style="text-align:center;background:#f8fafc;border-radius:8px;padding:12px;">
      <div id="sel-stat-avg" style="font-size:24px;font-weight:800;color:#f59e0b;">#{sel["avg_position"]}</div>
      <div style="font-size:11px;color:#888;">平均排名</div>
    </div>
  </div>
  <table>
    <tr><th>关键词</th><th style="text-align:center;">排名</th><th style="text-align:center;">变化</th><th style="text-align:center;">搜索量</th><th style="text-align:center;">状态</th><th>落地页</th></tr>
    <tbody id="sel-kw-rows">{sel_rows}</tbody>
  </table>
</div>'''

keyword_section_html = ''
if kws.get('total_keywords'):
    keyword_section_html = f'''<div class="card">
  <h2>🔑 关键词排名走向 <span id="kw-date-label" style="font-size:11px;color:#888;font-weight:400;">（{kw_updated} 数据 · 每天更新）</span></h2>

  <div style="max-width:280px;margin-bottom:16px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
      <button id="kw-cal-prev" type="button" style="border:none;background:#f1f5f9;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:13px;">‹</button>
      <span id="kw-cal-month-label" style="font-size:12px;font-weight:700;color:#555;"></span>
      <button id="kw-cal-next" type="button" style="border:none;background:#f1f5f9;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:13px;">›</button>
    </div>
    <div id="kw-cal-grid" style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px;font-size:11px;text-align:center;"></div>
    <div style="font-size:10px;color:#aaa;margin-top:6px;">点击有数据的日期查看当天的关键词报告</div>
  </div>

  <div class="g4" style="margin-bottom:16px;">
    <div style="text-align:center;background:#f8fafc;border-radius:8px;padding:12px;">
      <div id="kw-stat-total" style="font-size:24px;font-weight:800;color:#4f46e5;">{kws.get("total_keywords",0)}</div>
      <div style="font-size:11px;color:#888;">追踪关键词数</div>
    </div>
    <div style="text-align:center;background:#f8fafc;border-radius:8px;padding:12px;">
      <div id="kw-stat-avg" style="font-size:24px;font-weight:800;color:#f59e0b;">#{kws.get("avg_position","-")}</div>
      <div style="font-size:11px;color:#888;">平均排名</div>
    </div>
    <div style="text-align:center;background:#f0fdf4;border-radius:8px;padding:12px;">
      <div id="kw-stat-top10" style="font-size:24px;font-weight:800;color:#16a34a;">{kws.get("top10_count",0)}</div>
      <div style="font-size:11px;color:#888;">Top 10 关键词数</div>
    </div>
    <div style="text-align:center;background:#f8fafc;border-radius:8px;padding:12px;">
      <div id="kw-stat-opp" style="font-size:24px;font-weight:800;color:#8b5cf6;">{len(kws.get("opportunities",[]))}</div>
      <div style="font-size:11px;color:#888;">潜力机会词</div>
    </div>
  </div>
  <div class="g2" style="margin-bottom:16px;">
    <div>
      <h2 style="font-size:12px;color:#16a34a;margin-bottom:8px;">📈 排名上升最多（近7天）</h2>
      <table>
        <tr><th>关键词</th><th style="text-align:center;">排名</th><th style="text-align:center;">变化</th><th style="text-align:center;">搜索量</th><th>落地页</th></tr>
        <tbody id="kw-movers-up">{movers_up_rows}</tbody>
      </table>
    </div>
    <div>
      <h2 style="font-size:12px;color:#ef4444;margin-bottom:8px;">📉 排名下降最多（近7天）</h2>
      <table>
        <tr><th>关键词</th><th style="text-align:center;">排名</th><th style="text-align:center;">变化</th><th style="text-align:center;">搜索量</th><th>落地页</th></tr>
        <tbody id="kw-movers-down">{movers_down_rows}</tbody>
      </table>
    </div>
  </div>
  <h2 style="font-size:12px;color:#8b5cf6;margin-bottom:8px;">🎯 潜力机会词（排名11-30名，有搜索量）</h2>
  <table>
    <tr><th>关键词</th><th style="text-align:center;">当前排名</th><th style="text-align:center;">搜索量</th><th>建议行动</th></tr>
    <tbody id="kw-opportunities">{opportunities_rows}</tbody>
  </table>
</div>'''

# Plain (non-f) string: the calendar/history JS is written once and reused verbatim,
# so its own { } braces never need escaping.
keyword_calendar_script = '' if not kws.get('total_keywords') else '''<script>
(function(){
  var availableDates = [];
  var calYear, calMonth;

  function pad(n){ return n<10 ? '0'+n : ''+n; }
  function fmtDate(y,m,d){ return y+'-'+pad(m+1)+'-'+pad(d); }
  function escapeHtml(s){
    return String(s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function deltaBadge(delta){
    if (delta > 0) return '<span style="color:#16a34a;font-weight:700;">▲ '+delta+'</span>';
    if (delta < 0) return '<span style="color:#ef4444;font-weight:700;">▼ '+Math.abs(delta)+'</span>';
    return '<span style="color:#888;">– 0</span>';
  }
  function noRow(cols){ return '<tr><td colspan="'+cols+'" style="padding:10px;font-size:12px;color:#888;">暂无数据</td></tr>'; }
  function kwRow(k){
    var page = (k.landing_page || '-').replace(location.origin, '') || '/';
    return '<tr style="border-bottom:1px solid #f3f4f6;">' +
      '<td style="padding:7px 8px;font-size:12px;">'+escapeHtml(k.keyword)+'</td>' +
      '<td style="text-align:center;padding:7px 8px;font-size:12px;font-weight:700;">#'+k.position+'</td>' +
      '<td style="text-align:center;padding:7px 8px;font-size:12px;">'+deltaBadge(k.delta)+'</td>' +
      '<td style="text-align:center;padding:7px 8px;font-size:12px;">'+(k.volume||0)+'</td>' +
      '<td style="padding:7px 8px;font-size:11px;color:#888;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'+escapeHtml(page)+'</td>' +
      '</tr>';
  }
  function oppRow(k){
    var action = '排名 #'+k.position+'，月搜索量 '+(k.volume||0)+'，已进前30名，加强内链/更新内容有机会冲进前10';
    return '<tr style="border-bottom:1px solid #f3f4f6;">' +
      '<td style="padding:7px 8px;font-size:12px;">'+escapeHtml(k.keyword)+'</td>' +
      '<td style="text-align:center;padding:7px 8px;font-size:12px;font-weight:700;color:#f59e0b;">#'+k.position+'</td>' +
      '<td style="text-align:center;padding:7px 8px;font-size:12px;">'+(k.volume||0)+'</td>' +
      '<td style="padding:7px 8px;font-size:11px;color:#555;">'+action+'</td>' +
      '</tr>';
  }
  function selRow(k){
    var page = (k.landing_page || '-').replace(location.origin, '') || '/';
    var status = k.position <= 10
      ? '<span style="background:#dcfce7;color:#16a34a;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">✅ Top10</span>'
      : '<span style="background:#fef2f2;color:#ef4444;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">距前10还差'+(k.position-10)+'名</span>';
    return '<tr style="border-bottom:1px solid #f3f4f6;">' +
      '<td style="padding:7px 8px;font-size:12px;">'+escapeHtml(k.keyword)+'</td>' +
      '<td style="text-align:center;padding:7px 8px;font-size:12px;font-weight:700;">#'+k.position+'</td>' +
      '<td style="text-align:center;padding:7px 8px;font-size:12px;">'+deltaBadge(k.delta)+'</td>' +
      '<td style="text-align:center;padding:7px 8px;font-size:12px;">'+(k.volume||0)+'</td>' +
      '<td style="text-align:center;padding:7px 8px;">'+status+'</td>' +
      '<td style="padding:7px 8px;font-size:11px;color:#888;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'+escapeHtml(page)+'</td>' +
      '</tr>';
  }
  function renderData(data, dateStr){
    document.getElementById('kw-stat-total').textContent = data.total_keywords || 0;
    document.getElementById('kw-stat-avg').textContent = '#' + (data.avg_position != null ? data.avg_position : '-');
    document.getElementById('kw-stat-top10').textContent = data.top10_count || 0;
    document.getElementById('kw-stat-opp').textContent = (data.opportunities || []).length;
    document.getElementById('kw-movers-up').innerHTML = (data.movers_up||[]).map(kwRow).join('') || noRow(5);
    document.getElementById('kw-movers-down').innerHTML = (data.movers_down||[]).map(kwRow).join('') || noRow(5);
    document.getElementById('kw-opportunities').innerHTML = (data.opportunities||[]).map(oppRow).join('') || noRow(4);
    document.getElementById('kw-date-label').textContent = '（' + dateStr + ' 数据）';

    var sel = data.selected;
    var selRows = document.getElementById('sel-kw-rows');
    if (sel && selRows){
      document.getElementById('sel-stat-total').textContent = sel.total || 0;
      document.getElementById('sel-stat-top10').textContent = sel.top10_count || 0;
      document.getElementById('sel-stat-remaining').textContent = (sel.total||0) - (sel.top10_count||0);
      document.getElementById('sel-stat-avg').textContent = '#' + (sel.avg_position != null ? sel.avg_position : '-');
      selRows.innerHTML = (sel.keywords||[]).map(selRow).join('') || noRow(6);
      var selLabel = document.getElementById('sel-date-label');
      if (selLabel) selLabel.textContent = '（客户指定关键词 · ' + dateStr + ' 数据）';
    }
  }
  function loadDate(dateStr){
    fetch('keywords-history/' + dateStr + '.json')
      .then(function(r){ return r.json(); })
      .then(function(data){ renderData(data, dateStr); })
      .catch(function(){});
  }
  function renderCalendar(){
    var grid = document.getElementById('kw-cal-grid');
    var first = new Date(calYear, calMonth, 1);
    var startDay = first.getDay();
    var daysInMonth = new Date(calYear, calMonth+1, 0).getDate();
    document.getElementById('kw-cal-month-label').textContent = calYear + '年' + (calMonth+1) + '月';
    var html = '';
    ['日','一','二','三','四','五','六'].forEach(function(d){
      html += '<div style="color:#888;font-weight:600;padding:4px 0;">'+d+'</div>';
    });
    for (var i=0;i<startDay;i++){ html += '<div></div>'; }
    for (var d=1; d<=daysInMonth; d++){
      var ds = fmtDate(calYear, calMonth, d);
      if (availableDates.indexOf(ds) !== -1){
        html += '<div class="kw-cal-day" data-date="'+ds+'" style="cursor:pointer;padding:5px 0;border-radius:6px;background:#eef2ff;color:#4f46e5;font-weight:600;">'+d+'</div>';
      } else {
        html += '<div style="padding:5px 0;color:#d1d5db;">'+d+'</div>';
      }
    }
    grid.innerHTML = html;
    var days = grid.querySelectorAll('.kw-cal-day');
    for (var i=0;i<days.length;i++){
      days[i].addEventListener('click', function(){ loadDate(this.getAttribute('data-date')); });
    }
  }
  document.getElementById('kw-cal-prev').addEventListener('click', function(){
    calMonth--; if (calMonth<0){ calMonth=11; calYear--; }
    renderCalendar();
  });
  document.getElementById('kw-cal-next').addEventListener('click', function(){
    calMonth++; if (calMonth>11){ calMonth=0; calYear++; }
    renderCalendar();
  });
  var today = new Date();
  calYear = today.getFullYear();
  calMonth = today.getMonth();
  fetch('keywords-history/index.json')
    .then(function(r){ return r.json(); })
    .then(function(idx){ availableDates = idx.dates || []; renderCalendar(); })
    .catch(function(){ renderCalendar(); });
})();
</script>'''

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
    <div style="font-size:12px;color:#94a3b8;margin-top:4px;">{SITE_URL} · 完整报告更新：{gen_at}（每周一）· 关键词排名每天更新 · 统计：过去90天</div>
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

<!-- Keyword rankings (refreshed daily) -->
{keyword_section_html}
{selected_keyword_html}
{keyword_calendar_script}

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
  数据来源：Google Search Console · Google Analytics 4 · 实时技术检测 · SE Ranking 网站健康报告（每周一自动更新）· SE Ranking 关键词排名（每天自动更新）
</div>

</div>
</body>
</html>'''

os.makedirs('docs', exist_ok=True)
with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("✅ Dashboard generated at docs/index.html")
