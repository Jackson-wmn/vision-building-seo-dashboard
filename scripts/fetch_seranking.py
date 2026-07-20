"""
SE Ranking API → seranking.json 自动拉取脚本
在 GitHub Actions 每周自动运行，无需手动上传 PDF
"""
import os, json, datetime, urllib.request, urllib.error

API_KEY   = os.environ.get('SERANKING_API_KEY', '')
AUDIT_ID  = int(os.environ.get('SERANKING_AUDIT_ID', '700348552'))
BASE_URL  = 'https://api4.seranking.com'

def api(path):
    req = urllib.request.Request(
        f'{BASE_URL}{path}',
        headers={'Authorization': f'Token {API_KEY}', 'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def main():
    if not API_KEY:
        print("⚠️  SERANKING_API_KEY 未设置，跳过 SE Ranking 数据拉取")
        return

    print(f"📊 从 SE Ranking 拉取 audit #{AUDIT_ID} 数据...")

    try:
        report = api(f'/site/audit/{AUDIT_ID}/report/')
    except urllib.error.HTTPError as e:
        print(f"❌ SE Ranking API 错误：{e.code} {e.reason}")
        return

    # 提取各类问题数量
    def issue_val(section_uid, code):
        for s in report.get('sections', []):
            if s['uid'] == section_uid:
                return s['props'].get(code, {}).get('value', 0)
        return 0

    data = {
        'updated_at':        datetime.date.today().isoformat(),
        'source':            'SE Ranking API (自动)',
        'audit_id':          AUDIT_ID,
        'health_score':      report.get('score_percent', 0),
        'total_issues':      report.get('total_errors', 0) + report.get('total_warnings', 0) + report.get('total_notices', 0),
        'errors':            report.get('total_errors', 0),
        'warnings':          report.get('total_warnings', 0),
        'notices':           report.get('total_notices', 0),
        'pages_crawled':     report.get('total_pages', 0),
        'domain_expiry':     report.get('domain_props', {}).get('expdate', ''),
        'domain_trust':      report.get('domain_props', {}).get('dt', 0),
        'backlinks':         report.get('domain_props', {}).get('backlinks', 0),
        'referring_domains': report.get('domain_props', {}).get('domains', 0),
        'google_index':      report.get('domain_props', {}).get('index_google', 0),
        'issues': {
            'broken_4xx': {
                'count':       issue_val('crawling_v2', 'http4xx'),
                'label':       '4XX 断链',
                'severity':    '严重',
                'description': f"{issue_val('crawling_v2', 'http4xx')}个页面返回404错误",
                'effort':      '1小时',
                'fix':         '找到含 _wp_link_placeholder 的博客文章 → 修复或删除断链'
            },
            'redirects_3xx': {
                'count':       issue_val('redirects_v2', 'redirect3xx'),
                'label':       '3XX 重定向链',
                'severity':    '中',
                'description': f"{issue_val('redirects_v2', 'redirect3xx')}个页面有重定向",
                'effort':      '30分钟',
                'fix':         '更新内部链接直接指向最终URL'
            },
            'duplicate_titles': {
                'count':       issue_val('metatags_v2', 'title_duplicate'),
                'label':       '重复页面标题',
                'severity':    '高',
                'description': f"{issue_val('metatags_v2', 'title_duplicate')}个页面标题重复（EN/ZH版本相同）",
                'effort':      '2小时',
                'fix':         'TranslatePress → 逐页翻译 meta title'
            },
            'duplicate_descriptions': {
                'count':       issue_val('metatags_v2', 'description_duplicate'),
                'label':       '重复 Meta Description',
                'severity':    '高',
                'description': f"{issue_val('metatags_v2', 'description_duplicate')}个页面描述重复",
                'effort':      '2小时',
                'fix':         'TranslatePress → 逐页翻译 meta description'
            },
            'duplicate_h1': {
                'count':       issue_val('content_v2', 'h1_duplicate'),
                'label':       '重复 H1 标签',
                'severity':    '中',
                'description': f"{issue_val('content_v2', 'h1_duplicate')}个页面 H1 与中文版相同",
                'effort':      '1小时',
                'fix':         'TranslatePress → 翻译各页面 H1 内容'
            },
            'same_title_h1': {
                'count':       issue_val('content_v2', 'same_title_h1'),
                'label':       'Title 与 H1 完全相同',
                'severity':    '低',
                'description': f"{issue_val('content_v2', 'same_title_h1')}个页面 Title 和 H1 完全一样，浪费优化空间",
                'effort':      '持续',
                'fix':         '将 Title 改为包含关键词的完整句子，H1 保持简短'
            },
            'slow_pages': {
                'count':       issue_val('speed_performance_v2', 'loading_speed'),
                'label':       '页面加载速度慢',
                'severity':    '高',
                'description': f"{issue_val('speed_performance_v2', 'loading_speed')}个页面加载速度慢",
                'effort':      '持续',
                'fix':         'Elementor → Improved Asset Loading；Breeze → JS defer + CSS 合并'
            },
            'internal_links_3xx': {
                'count':       issue_val('links_v2', 'links3xx'),
                'label':       '内部链接指向重定向页',
                'severity':    '中',
                'description': f"{issue_val('links_v2', 'links3xx')}个内部链接指向3XX重定向页面",
                'effort':      '30分钟',
                'fix':         '更新内部链接直接指向最终目标URL'
            },
            'sitemap_missing': {
                'count':       issue_val('sitemaps_v2', 'sitemap_missing'),
                'label':       'XML Sitemap 缺失',
                'severity':    '严重',
                'description': 'XML sitemap 缺失，影响 Google 爬取效率',
                'effort':      '10分钟',
                'fix':         'Rank Math → Sitemap → 开启并提交到 GSC'
            }
        }
    }

    os.makedirs('data', exist_ok=True)
    with open('data/seranking.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ SE Ranking 数据已更新：")
    print(f"   健康评分：{data['health_score']}/100")
    print(f"   错误/警告/提示：{data['errors']}/{data['warnings']}/{data['notices']}")
    print(f"   域名到期：{data['domain_expiry']}")

if __name__ == '__main__':
    main()
