#!/usr/bin/env python3
"""
Zendesk Beta Ticket Dashboard Generator
Queries Zendesk API and generates a static HTML dashboard
"""
import os
import json
import requests
from datetime import datetime, timedelta

# Config from environment variables (set in GitHub Secrets)
ZENDESK_SUBDOMAIN = os.environ.get('ZENDESK_SUBDOMAIN', 'visitingmedia')
ZENDESK_EMAIL = os.environ.get('ZENDESK_EMAIL', '')
ZENDESK_TOKEN = os.environ.get('ZENDESK_TOKEN', '')

# Beta tags to track
BETA_TAGS = ['ux_assets', 'ux_feedback', 'ux_login', 'ux_redirect']


def zendesk_request(endpoint):
    """Make authenticated request to Zendesk API"""
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/{endpoint}"
    auth = (f"{ZENDESK_EMAIL}/token", ZENDESK_TOKEN)

    try:
        response = requests.get(url, auth=auth, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"API Error: {e}")
        return {'count': 0, 'error': str(e)}


def get_week_range():
    """Get this week's date range (Sunday to today)"""
    today = datetime.now()
    days_since_sunday = today.weekday() + 1
    if days_since_sunday == 7:
        days_since_sunday = 0
    start = today - timedelta(days=days_since_sunday)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')


def get_ticket_counts():
    """Get total and beta-tagged ticket counts for this week"""
    start_date, end_date = get_week_range()

    # Total tickets this week
    total_query = f"type:ticket created>={start_date} created<={end_date}"
    total_result = zendesk_request(f"search.json?query={requests.utils.quote(total_query)}")
    total = total_result.get('count', 0)

    # Beta-tagged tickets this week
    beta_tags_query = ' OR '.join([f'tags:{tag}' for tag in BETA_TAGS])
    beta_query = f"type:ticket created>={start_date} created<={end_date} ({beta_tags_query})"
    beta_result = zendesk_request(f"search.json?query={requests.utils.quote(beta_query)}")
    beta = beta_result.get('count', 0)

    return {
        'total': total,
        'beta': beta,
        'percentage': round((beta / total * 100), 1) if total > 0 else 0,
        'start_date': start_date,
        'end_date': end_date,
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    }


def generate_html(data):
    """Generate the dashboard HTML"""
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Beta Ticket Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }}
        .dashboard {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #fff;
            text-align: center;
            margin-bottom: 10px;
            font-size: 28px;
        }}
        .subtitle {{
            color: rgba(255,255,255,0.6);
            text-align: center;
            margin-bottom: 40px;
            font-size: 14px;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric {{
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px 15px;
            text-align: center;
        }}
        .metric-value {{
            font-size: 48px;
            font-weight: bold;
            margin-bottom: 8px;
        }}
        .metric-label {{
            color: rgba(255,255,255,0.7);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .beta .metric-value {{ color: #4285f4; }}
        .total .metric-value {{ color: #34a853; }}
        .percentage .metric-value {{ color: #ea4335; }}
        .formula {{
            text-align: center;
            color: rgba(255,255,255,0.5);
            font-size: 16px;
            margin-bottom: 20px;
        }}
        .updated {{
            text-align: center;
            color: rgba(255,255,255,0.4);
            font-size: 12px;
        }}
        .links {{
            margin-top: 30px;
            text-align: center;
        }}
        .links a {{
            color: #4285f4;
            text-decoration: none;
            margin: 0 10px;
            font-size: 14px;
        }}
        .links a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="dashboard">
        <h1>Beta Ticket Dashboard</h1>
        <div class="subtitle">Week: {data['start_date']} to {data['end_date']}</div>

        <div class="metrics">
            <div class="metric beta">
                <div class="metric-value">{data['beta']}</div>
                <div class="metric-label">Beta Tagged</div>
            </div>
            <div class="metric total">
                <div class="metric-value">{data['total']}</div>
                <div class="metric-label">Total Tickets</div>
            </div>
            <div class="metric percentage">
                <div class="metric-value">{data['percentage']}%</div>
                <div class="metric-label">Beta %</div>
            </div>
        </div>

        <div class="formula">{data['beta']} / {data['total']} = {data['percentage']}%</div>
        <div class="updated">Last updated: {data['updated']}</div>

        <div class="links">
            <a href="https://visitingmedia.zendesk.com/explore/studio#/dashboards" target="_blank">View in Zendesk Explore</a>
        </div>
    </div>
</body>
</html>'''
    return html


def main():
    print("Fetching Zendesk data...")
    data = get_ticket_counts()
    print(f"Beta: {data['beta']}, Total: {data['total']}, Percentage: {data['percentage']}%")

    print("Generating HTML...")
    html = generate_html(data)

    with open('index.html', 'w') as f:
        f.write(html)
    print("Dashboard saved to index.html")


if __name__ == '__main__':
    main()
