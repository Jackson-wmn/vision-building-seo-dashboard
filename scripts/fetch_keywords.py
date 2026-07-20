"""
SE Ranking Project API → keywords.json 每日关键词排名走向脚本
在 GitHub Actions 每天自动运行
"""
import os, json, datetime, urllib.request, urllib.error

API_KEY   = os.environ.get('SERANKING_API_KEY', '')
SITE_ID   = os.environ.get('SERANKING_SITE_ID', '')
BASE_URL  = 'https://api.seranking.com/v1'

def api(path):
    req = urllib.request.Request(
        f'{BASE_URL}{path}',
        headers={'Authorization': f'Token {API_KEY}', 'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def find_selected_group_id(site_id):
    """Look up the keyword group the client has marked as their priority list (name contains 'selected')."""
    try:
        groups = api(f'/project-management/keywords/groups?site_id={site_id}')
    except urllib.error.HTTPError as e:
        print(f"⚠️  无法读取关键词分组：{e.code} {e.reason}，跳过重点关键词监控")
        return None
    groups = groups if isinstance(groups, list) else groups.get('data', [])
    for g in groups:
        if 'selected' in g.get('name', '').lower():
            try:
                return int(g.get('id'))  # group id here is a string; keyword.group_id is an int
            except (TypeError, ValueError):
                return g.get('id')
    return None

def build_snapshot(all_keywords, selected_group_id=None):
    """Turn a raw SE Ranking positions response into the dashboard's keywords.json shape."""
    processed = []
    for kw in all_keywords:
        positions = [p for p in kw.get('positions', []) if p.get('pos')]
        if not positions:
            continue
        positions.sort(key=lambda p: p['date'])
        latest, earliest = positions[-1], positions[0]
        landing = kw.get('landing_pages', [])
        processed.append({
            'keyword':          kw.get('name', ''),
            'position':         latest['pos'],
            'position_7d_ago':  earliest['pos'],
            'delta':            earliest['pos'] - latest['pos'],  # positive = moved up (better)
            'volume':           kw.get('volume', 0),
            'landing_page':     landing[-1]['url'] if landing else '',
            'group_id':         kw.get('group_id'),
        })

    movers_up   = sorted([k for k in processed if k['delta'] > 0], key=lambda k: -k['delta'])[:8]
    movers_down = sorted([k for k in processed if k['delta'] < 0], key=lambda k: k['delta'])[:8]
    opportunities = sorted(
        [k for k in processed if 11 <= k['position'] <= 30 and k['volume'] > 0],
        key=lambda k: -k['volume']
    )[:8]

    avg_position = round(sum(k['position'] for k in processed) / len(processed), 1) if processed else 0
    top10_count  = sum(1 for k in processed if k['position'] <= 10)

    selected = None
    if selected_group_id is not None:
        sel = [k for k in processed if k['group_id'] == selected_group_id]
        sel.sort(key=lambda k: k['position'])
        selected = {
            'total':        len(sel),
            'top10_count':  sum(1 for k in sel if k['position'] <= 10),
            'avg_position': round(sum(k['position'] for k in sel) / len(sel), 1) if sel else 0,
            'keywords':     [{k2: v for k2, v in k.items() if k2 != 'group_id'} for k in sel],
        }

    for k in processed:
        k.pop('group_id', None)

    return {
        'total_keywords':  len(processed),
        'avg_position':    avg_position,
        'top10_count':     top10_count,
        'movers_up':       movers_up,
        'movers_down':     movers_down,
        'opportunities':   opportunities,
        'selected':        selected,
    }

def main():
    if not API_KEY or not SITE_ID:
        print("⚠️  SERANKING_API_KEY 或 SERANKING_SITE_ID 未设置，跳过关键词走向拉取")
        return

    today = datetime.date.today()
    date_from = (today - datetime.timedelta(days=7)).isoformat()
    date_to = today.isoformat()

    print(f"📈 从 SE Ranking 拉取项目 #{SITE_ID} 的关键词走向（{date_from} ~ {date_to}）...")

    try:
        resp = api(f'/project-management/sites/positions?site_id={SITE_ID}&date_from={date_from}&date_to={date_to}&with_landing_pages=1')
    except urllib.error.HTTPError as e:
        print(f"❌ SE Ranking Project API 错误：{e.code} {e.reason}")
        return

    # The API returns a bare list of per-search-engine groups (not wrapped in {"data": ...})
    engines = resp if isinstance(resp, list) else resp.get('data', [])
    all_keywords = []
    for engine in engines:
        all_keywords.extend(engine.get('keywords', []))

    selected_group_id = find_selected_group_id(SITE_ID)
    snapshot = build_snapshot(all_keywords, selected_group_id)

    output = {
        'updated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'date_from':  date_from,
        'date_to':    date_to,
        **snapshot,
    }

    os.makedirs('data', exist_ok=True)
    with open('data/keywords.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Archive today's snapshot under docs/ so the dashboard's calendar can fetch it client-side
    # (only files inside docs/ are served by GitHub Pages)
    history_dir = 'docs/keywords-history'
    os.makedirs(history_dir, exist_ok=True)
    with open(f'{history_dir}/{today.isoformat()}.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    index_path = f'{history_dir}/index.json'
    try:
        with open(index_path) as f:
            index = json.load(f)
    except Exception:
        index = {'dates': []}
    if today.isoformat() not in index['dates']:
        index['dates'].append(today.isoformat())
        index['dates'].sort()
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)

    sel_msg = f"，重点关键词 {snapshot['selected']['top10_count']}/{snapshot['selected']['total']} 进前10" if snapshot['selected'] else ""
    print(f"✅ 关键词走向已更新：追踪 {snapshot['total_keywords']} 个关键词，平均排名 {snapshot['avg_position']}，Top10 有 {snapshot['top10_count']} 个{sel_msg}")

if __name__ == '__main__':
    main()
