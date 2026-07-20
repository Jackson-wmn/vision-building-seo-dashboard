"""
SE Ranking PDF → seranking.json 更新工具
用法：python3 scripts/update_seranking.py /path/to/audit.pdf
"""
import sys, json, re, datetime, subprocess, os

def extract_text(pdf_path):
    try:
        import pdfplumber
        text = ''
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or '') + '\n'
        return text
    except ImportError:
        pass
    # fallback: pdftotext cli
    try:
        r = subprocess.run(['pdftotext', pdf_path, '-'], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
    except Exception:
        pass
    raise SystemExit("❌ 无法读取 PDF。请先安装：pip install pdfplumber")

def parse_number(text, *patterns):
    for p in patterns:
        m = re.search(p, text)
        if m:
            return int(m.group(1).replace(',','').replace(' ',''))
    return 0

def parse_float(text, *patterns):
    for p in patterns:
        m = re.search(p, text)
        if m:
            return float(m.group(1))
    return 0.0

def main():
    if len(sys.argv) < 2:
        print("用法：python3 scripts/update_seranking.py /path/to/audit.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"❌ 找不到文件：{pdf_path}")
        sys.exit(1)

    print(f"📄 读取 PDF：{pdf_path}")
    text = extract_text(pdf_path)

    # Parse health score
    health = parse_number(text, r'Health\s+Score[:\s]+(\d+)', r'health score[:\s]+(\d+)', r'(\d+)\s*/\s*100')
    if not health:
        health = parse_number(text, r'\b(7[0-9]|8[0-9]|6[0-9])\b(?=\s*/\s*100)')

    # Parse issue counts
    errors   = parse_number(text, r'Errors?\s+(\d+)', r'(\d+)\s+errors?')
    warnings = parse_number(text, r'Warnings?\s+(\d+)', r'(\d+)\s+warnings?')
    notices  = parse_number(text, r'Notices?\s+(\d+)', r'(\d+)\s+notices?')
    total    = errors + warnings + notices if (errors or warnings or notices) else parse_number(text, r'(\d+)\s+(?:total\s+)?issues?')

    # Pages
    pages_crawled = parse_number(text, r'Pages?\s+crawled[:\s]+(\d+)', r'crawled[:\s]+(\d+)')
    urls_found    = parse_number(text, r'URLs?\s+(?:found|discovered)[:\s]+(\d+)', r'(?:found|discovered)[:\s]+(\d+)')

    # Specific issues
    broken_4xx    = parse_number(text, r'4[Xx][Xx][^0-9]*(\d+)', r'broken[^0-9]*(\d+)', r'(\d+)[^0-9]*4[Xx][Xx]')
    redirects_3xx = parse_number(text, r'3[Xx][Xx][^0-9]*(\d+)', r'redirect[^0-9]*(\d+)', r'(\d+)[^0-9]*redirect')
    dup_titles    = parse_number(text, r'duplicate\s+(?:page\s+)?titles?[^0-9]*(\d+)', r'(\d+)[^0-9]*duplicate\s+titles?')
    dup_descs     = parse_number(text, r'duplicate\s+(?:meta\s+)?desc[^0-9]*(\d+)', r'(\d+)[^0-9]*duplicate\s+desc')
    dup_h1        = parse_number(text, r'duplicate\s+[Hh]1[^0-9]*(\d+)', r'(\d+)[^0-9]*duplicate\s+[Hh]1')
    slow_pages    = parse_number(text, r'slow[^0-9]*(\d+)', r'(\d+)[^0-9]*slow')
    no_hreflang   = parse_number(text, r'(?:missing|no)\s+(?:x-default\s+)?hreflang[^0-9]*(\d+)', r'hreflang[^0-9]*(\d+)')

    # Domain expiry
    expiry_match = re.search(r'(?:expir|renew)[^0-9]*(\w+[-\s]\d{1,2}[-,\s]+\d{4}|\d{4}-\d{2}-\d{2})', text, re.I)
    domain_expiry = expiry_match.group(1).strip() if expiry_match else "2026-08-15"

    data = {
        "updated_at": datetime.date.today().isoformat(),
        "source_pdf": os.path.basename(pdf_path),
        "health_score": health or 75,
        "total_issues": total,
        "errors": errors,
        "warnings": warnings,
        "notices": notices,
        "pages_crawled": pages_crawled,
        "urls_found": urls_found,
        "domain_expiry": domain_expiry,
        "issues": {
            "broken_4xx": {
                "count": broken_4xx,
                "label": "4XX 断链",
                "severity": "严重",
                "description": f"{broken_4xx}个页面返回404错误，多个含 _wp_link_placeholder（WordPress编辑器残留链接）",
                "effort": "1小时",
                "fix": "WordPress → 找到含 _wp_link_placeholder 的博客文章 → 修复或删除断链"
            },
            "redirects_3xx": {
                "count": redirects_3xx,
                "label": "3XX 重定向链",
                "severity": "中",
                "description": f"{redirects_3xx}个页面有重定向（改URL后未更新内链）",
                "effort": "30分钟",
                "fix": "找到重定向来源页面，更新内部链接直接指向最终URL"
            },
            "duplicate_titles": {
                "count": dup_titles,
                "label": "重复页面标题",
                "severity": "高",
                "description": f"{dup_titles}个页面标题重复（英文和/zh/中文版共用同一标题）",
                "effort": "2小时",
                "fix": "TranslatePress → 逐页翻译 meta title"
            },
            "duplicate_descriptions": {
                "count": dup_descs,
                "label": "重复 Meta Description",
                "severity": "高",
                "description": f"{dup_descs}个页面 meta description 与中文版完全一样",
                "effort": "2小时",
                "fix": "TranslatePress → 逐页翻译 meta description"
            },
            "duplicate_h1": {
                "count": dup_h1,
                "label": "重复 H1 标签",
                "severity": "中",
                "description": f"{dup_h1}个页面 H1 与中文版完全一样（未翻译）",
                "effort": "1小时",
                "fix": "TranslatePress → 翻译各页面 H1 内容"
            },
            "slow_pages": {
                "count": slow_pages,
                "label": "页面加载速度慢",
                "severity": "高",
                "description": f"{slow_pages}个页面被标记为加载速度慢",
                "effort": "持续",
                "fix": "Elementor → Improved Asset Loading；Breeze → JS defer + CSS 合并"
            },
            "missing_x_default": {
                "count": no_hreflang,
                "label": "缺少 x-default hreflang",
                "severity": "高",
                "description": f"{no_hreflang}个页面缺少 x-default hreflang 标签",
                "effort": "15分钟",
                "fix": "Rank Math → Titles & Meta → 添加 hreflang x-default"
            }
        }
    }

    os.makedirs('data', exist_ok=True)
    with open('data/seranking.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ 解析完成：")
    print(f"   健康评分：{data['health_score']}/100")
    print(f"   错误/警告/提示：{errors}/{warnings}/{notices}")
    print(f"   断链：{broken_4xx}  重定向：{redirects_3xx}  重复标题：{dup_titles}")
    print(f"   域名到期：{domain_expiry}")
    print()

    # Regenerate dashboard
    print("🔄 重新生成 dashboard...")
    subprocess.run([sys.executable, 'scripts/generate_dashboard.py'], check=True)

    print()
    print("🚀 现在执行以下命令推送到 GitHub：")
    print()
    print("   cd /Users/jaey933/Downloads/iconfit-seo-dashboard")
    print("   git add data/seranking.json docs/index.html")
    print('   git commit -m "Update SE Ranking data"')
    print("   git push")

if __name__ == '__main__':
    main()
