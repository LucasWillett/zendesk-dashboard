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

# Groups to include (will be resolved to IDs)
TARGET_GROUPS = ['Billing', 'CX Success', 'Distribution', 'ENG - Support']

# Cache for user and org lookups
user_cache = {}
org_cache = {}


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
        return {}


def get_user_name(user_id):
    """Get user name by ID (cached)"""
    if not user_id:
        return "Unknown"
    if user_id in user_cache:
        return user_cache[user_id]

    result = zendesk_request(f"users/{user_id}.json")
    name = result.get('user', {}).get('name', 'Unknown')
    user_cache[user_id] = name
    return name


def get_org_name(org_id):
    """Get organization name by ID (cached)"""
    if not org_id:
        return "No Account"
    if org_id in org_cache:
        return org_cache[org_id]

    result = zendesk_request(f"organizations/{org_id}.json")
    name = result.get('organization', {}).get('name', 'No Account')
    org_cache[org_id] = name
    return name


def get_group_ids():
    """Get IDs for the target groups"""
    result = zendesk_request('groups.json')
    groups = result.get('groups', [])

    group_ids = []
    for group in groups:
        if group['name'] in TARGET_GROUPS:
            group_ids.append(str(group['id']))
            print(f"  Found group: {group['name']} = {group['id']}")

    return group_ids


def get_week_range():
    """Get this week's date range (Sunday to today)"""
    today = datetime.now()
    days_since_sunday = today.weekday() + 1
    if days_since_sunday == 7:
        days_since_sunday = 0
    start = today - timedelta(days=days_since_sunday)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')


def get_ticket_data():
    """Get total and beta-tagged ticket counts for this week"""
    start_date, end_date = get_week_range()

    # Get group IDs for filtering
    print("Fetching group IDs...")
    group_ids = set(get_group_ids())
    print(f"Target group IDs: {group_ids}")

    # Fetch all tickets this week
    total_query = f"type:ticket created>={start_date} created<={end_date}"
    print(f"Fetching tickets: {total_query}")

    all_tickets = []
    page = 1
    while True:
        result = zendesk_request(f"search.json?query={requests.utils.quote(total_query)}&per_page=100&page={page}")
        tickets = result.get('results', [])
        if not tickets:
            break
        all_tickets.extend(tickets)
        if len(tickets) < 100:
            break
        page += 1

    print(f"Total tickets fetched: {len(all_tickets)}")

    # Filter by target groups
    if group_ids:
        filtered_tickets = [t for t in all_tickets if str(t.get('group_id', '')) in group_ids]
    else:
        filtered_tickets = all_tickets

    print(f"Tickets in target groups: {len(filtered_tickets)}")

    # Get beta-tagged tickets with full details
    beta_tickets = [t for t in filtered_tickets if any(tag in t.get('tags', []) for tag in BETA_TAGS)]

    # Enrich beta tickets with user/org names
    print(f"Enriching {len(beta_tickets)} beta tickets with details...")
    beta_ticket_details = []
    for ticket in beta_tickets:
        beta_tags_on_ticket = [tag for tag in ticket.get('tags', []) if tag in BETA_TAGS]
        beta_ticket_details.append({
            'id': ticket.get('id'),
            'subject': ticket.get('subject', 'No Subject'),
            'requester': get_user_name(ticket.get('requester_id')),
            'account': get_org_name(ticket.get('organization_id')),
            'beta_tags': beta_tags_on_ticket,
            'all_tags': ticket.get('tags', []),
            'created': ticket.get('created_at', '')[:10],
            'url': f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/agent/tickets/{ticket.get('id')}"
        })

    total = len(filtered_tickets)
    beta = len(beta_tickets)

    return {
        'total': total,
        'beta': beta,
        'percentage': round((beta / total * 100), 1) if total > 0 else 0,
        'start_date': start_date,
        'end_date': end_date,
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
        'beta_tickets': beta_ticket_details
    }


def generate_html(data):
    """Generate the dashboard HTML"""

    # Generate ticket table rows
    ticket_rows = ""
    for ticket in data['beta_tickets']:
        tags_html = ' '.join([f'<span class="tag">{tag}</span>' for tag in ticket['beta_tags']])
        ticket_rows += f'''
            <tr>
                <td><a href="{ticket['url']}" target="_blank">{ticket['subject'][:50]}{'...' if len(ticket['subject']) > 50 else ''}</a></td>
                <td>{ticket['account']}</td>
                <td>{ticket['requester']}</td>
                <td>{tags_html}</td>
                <td>{ticket['created']}</td>
            </tr>'''

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
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .dashboard {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #fff;
            text-align: center;
            margin-bottom: 10px;
            font-size: 28px;
        }}
        h2 {{
            color: #fff;
            margin-bottom: 20px;
            font-size: 20px;
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

        /* Table styles */
        .ticket-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        .ticket-table th {{
            background: rgba(255,255,255,0.1);
            color: rgba(255,255,255,0.9);
            padding: 12px 15px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .ticket-table td {{
            padding: 12px 15px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            color: rgba(255,255,255,0.8);
            font-size: 14px;
        }}
        .ticket-table tr:hover {{
            background: rgba(255,255,255,0.05);
        }}
        .ticket-table a {{
            color: #4285f4;
            text-decoration: none;
        }}
        .ticket-table a:hover {{
            text-decoration: underline;
        }}
        .tag {{
            display: inline-block;
            background: #4285f4;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            margin: 2px;
        }}
        .no-tickets {{
            text-align: center;
            color: rgba(255,255,255,0.5);
            padding: 40px;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="container">
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

        <div class="dashboard">
            <h2>Beta Tagged Tickets This Week</h2>
            {f'''<table class="ticket-table">
                <thead>
                    <tr>
                        <th>Subject</th>
                        <th>Account</th>
                        <th>Requester</th>
                        <th>Beta Tags</th>
                        <th>Created</th>
                    </tr>
                </thead>
                <tbody>
                    {ticket_rows}
                </tbody>
            </table>''' if data['beta_tickets'] else '<div class="no-tickets">No beta-tagged tickets this week</div>'}
        </div>
    </div>
</body>
</html>'''
    return html


def main():
    print("Fetching Zendesk data...")
    data = get_ticket_data()
    print(f"Beta: {data['beta']}, Total: {data['total']}, Percentage: {data['percentage']}%")

    print("Generating HTML...")
    html = generate_html(data)

    with open('index.html', 'w') as f:
        f.write(html)
    print("Dashboard saved to index.html")


if __name__ == '__main__':
    main()
