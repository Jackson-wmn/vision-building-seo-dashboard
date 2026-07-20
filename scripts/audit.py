"""
Weekly SEO Audit — fetches GSC, GA4, and technical data.
All brand config comes from environment variables / GitHub Secrets.
"""
import os, json, datetime, subprocess, re

from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric, OrderBy

CREDS_FILE = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '/tmp/service-account.json')
GA4_ID     = os.environ.get('GA4_PROPERTY_ID', '')
GSC_URL    = os.environ.get('GSC_SITE_URL', '')
SITE       = os.environ.get('SITE_URL', '')

SCOPES_GSC = ['https://www.googleapis.com/auth/webmasters.readonly']
SCOPES_GA4 = ['https://www.googleapis.com/auth/analytics.readonly']

def gsc_service():
    creds = service_account.Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES_GSC)
    return build('webmasters', 'v3', credentials=creds)

def ga4_client():
    creds = service_account.Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES_GA4)
    return BetaAnalyticsDataClient(credentials=creds)

def fetch_gsc(service, days=90):
    end   = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    def query(body):
        return service.searchanalytics().query(siteUrl=GSC_URL, body=body).execute()

    totals     = query({'startDate': start, 'endDate': end, 'dimensions': []})
    total_row  = totals.get('rows', [{}])[0]
    top_queries = query({'startDate': start, 'endDate': end, 'dimensions': ['query'], 'rowLimit': 20,
                         'orderBy': [{'fieldName': 'impressions', 'sortOrder': 'DESCENDING'}]}).get('rows', [])
    top_pages   = query({'startDate': start, 'endDate': end, 'dimensions': ['page'], 'rowLimit': 10,
                         'orderBy': [{'fieldName': 'clicks', 'sortOrder': 'DESCENDING'}]}).get('rows', [])
    countries   = query({'startDate': start, 'endDate': end, 'dimensions': ['country'], 'rowLimit': 5,
                         'orderBy': [{'fieldName': 'clicks', 'sortOrder': 'DESCENDING'}]}).get('rows', [])
    devices     = query({'startDate': start, 'endDate': end, 'dimensions': ['device'], 'rowLimit': 3}).get('rows', [])

    return {
        'total_clicks':      total_row.get('clicks', 0),
        'total_impressions': total_row.get('impressions', 0),
        'avg_ctr':           round(total_row.get('ctr', 0) * 100, 2),
        'avg_position':      round(total_row.get('position', 0), 1),
        'top_queries': [{'query': r['keys'][0], 'clicks': r['clicks'], 'impressions': r['impressions'],
                         'ctr': round(r['ctr']*100, 2), 'position': round(r['position'], 1)} for r in top_queries],
        'top_pages':  [{'page': r['keys'][0].replace(SITE,'') or '/', 'clicks': r['clicks'],
                        'impressions': r['impressions'], 'position': round(r['position'], 1)} for r in top_pages],
        'countries':  [{'country': r['keys'][0].upper(), 'clicks': r['clicks']} for r in countries],
        'devices':    [{'device': r['keys'][0], 'clicks': r['clicks'], 'impressions': r['impressions']} for r in devices],
    }

def fetch_ga4(client, days=90):
    dr = [DateRange(start_date=f"{days}daysAgo", end_date="today")]
    resp = client.run_report(RunReportRequest(
        property=GA4_ID,
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[Metric(name="sessions"), Metric(name="totalUsers"),
                 Metric(name="bounceRate"), Metric(name="averageSessionDuration")],
        date_ranges=dr,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)]
    ))
    channels, total_sessions = [], 0
    for row in resp.rows:
        s = int(row.metric_values[0].value)
        total_sessions += s
        channels.append({'channel': row.dimension_values[0].value, 'sessions': s,
                         'users': int(row.metric_values[1].value),
                         'bounce': round(float(row.metric_values[2].value)*100, 1),
                         'duration': round(float(row.metric_values[3].value))})

    resp2 = client.run_report(RunReportRequest(
        property=GA4_ID,
        dimensions=[Dimension(name="pagePath")],
        metrics=[Metric(name="sessions"), Metric(name="bounceRate"), Metric(name="averageSessionDuration")],
        date_ranges=dr,
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=10
    ))
    pages = [{'page': row.dimension_values[0].value, 'sessions': int(row.metric_values[0].value),
              'bounce': round(float(row.metric_values[1].value)*100, 1),
              'duration': round(float(row.metric_values[2].value))} for row in resp2.rows]

    return {'total_sessions': total_sessions, 'channels': channels, 'top_pages': pages}

def fetch_technical():
    results = {}
    def curl(url, extra_args=None):
        cmd = ['curl', '-s', '-m', '10'] + (extra_args or []) + [url]
        try: return subprocess.run(cmd, capture_output=True, text=True).stdout
        except: return ''

    headers = curl(SITE, ['-I'])
    results['has_hsts']         = 'strict-transport-security' in headers.lower()
    results['has_xframe']       = 'x-frame-options' in headers.lower()
    results['has_xcontent']     = 'x-content-type-options' in headers.lower()
    results['has_csp']          = 'content-security-policy' in headers.lower()
    results['has_permissions']  = 'permissions-policy' in headers.lower()
    results['security_headers'] = sum([results['has_hsts'], results['has_xframe'],
                                       results['has_xcontent'], results['has_csp'], results['has_permissions']])

    import json as _json
    users_resp = curl(f'{SITE}/wp-json/wp/v2/users')
    try:
        users = _json.loads(users_resp)
        results['rest_api_exposed'] = isinstance(users, list) and len(users) > 0
        results['rest_api_users']   = len(users) if isinstance(users, list) else 0
    except:
        results['rest_api_exposed'] = False
        results['rest_api_users']   = 0

    llms = curl(f'{SITE}/llms.txt')
    results['has_llms_txt'] = len(llms) > 50

    gptbot_h    = curl(SITE, ['-sI', '-A', 'GPTBot'])
    claudebot_h = curl(SITE, ['-sI', '-A', 'ClaudeBot'])
    results['gptbot_allowed']    = 'HTTP/2 200' in gptbot_h or 'HTTP/1.1 200' in gptbot_h
    results['claudebot_allowed'] = 'HTTP/2 200' in claudebot_h or 'HTTP/1.1 200' in claudebot_h

    homepage = curl(SITE)
    wp_gen = re.search(r'WordPress ([0-9.]+)', homepage)
    results['wp_version_exposed'] = wp_gen is not None
    results['wp_version']         = wp_gen.group(1) if wp_gen else ''
    results['xmlrpc_advertised']  = 'xmlrpc.php' in homepage

    return results

def calculate_scores(tech):
    tech_score = 54
    if not tech['rest_api_exposed']:   tech_score += 8
    if tech['security_headers'] >= 5:  tech_score += 10
    if not tech['wp_version_exposed']: tech_score += 5
    if not tech['xmlrpc_advertised']:  tech_score += 3
    tech_score = min(tech_score, 100)

    ai_score = 28
    if tech['has_llms_txt']:       ai_score += 15
    if tech['claudebot_allowed']:  ai_score += 20
    if tech['gptbot_allowed']:     ai_score += 10
    ai_score = min(ai_score, 100)

    overall = round(tech_score*0.22 + 58*0.23 + 55*0.20 + 42*0.10 + 50*0.10 + ai_score*0.10 + 75*0.05)
    return {'overall': overall, 'technical': tech_score, 'content': 58, 'on_page': 55,
            'schema': 42, 'performance': 50, 'ai': ai_score, 'images': 75}

def main():
    print("🔍 Fetching GSC data...")
    gsc = fetch_gsc(gsc_service())
    print(f"   ✓ {gsc['total_clicks']} clicks, {gsc['total_impressions']} impressions")

    print("📊 Fetching GA4 data...")
    ga4 = fetch_ga4(ga4_client())
    print(f"   ✓ {ga4['total_sessions']} sessions")

    print("🔧 Running technical checks...")
    tech = fetch_technical()
    print(f"   ✓ Security headers: {tech['security_headers']}/5")

    scores = calculate_scores(tech)
    print(f"📈 Overall score: {scores['overall']}/100")

    output = {
        'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'site': SITE, 'period_days': 90,
        'scores': scores, 'gsc': gsc, 'ga4': ga4, 'technical': tech
    }

    os.makedirs('data', exist_ok=True)
    with open('data/latest.json', 'w') as f:
        json.dump(output, f, indent=2)
    with open(f'data/{datetime.date.today().isoformat()}.json', 'w') as f:
        json.dump(output, f, indent=2)
    print("✅ Saved to data/latest.json")

if __name__ == '__main__':
    main()
