#!/usr/bin/env python3
"""
Zendesk Support Pulse: Beta Tags Generator
Queries Zendesk API and generates a static HTML dashboard
"""
import os
import json
import requests
from datetime import datetime, timedelta

# Import Gmail fetch for Help Center views
try:
    from gmail_fetch import fetch_help_center_views
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

# Config from environment variables (set in GitHub Secrets)
ZENDESK_SUBDOMAIN = os.environ.get('ZENDESK_SUBDOMAIN', 'visitingmedia')
ZENDESK_EMAIL = os.environ.get('ZENDESK_EMAIL', '')
ZENDESK_TOKEN = os.environ.get('ZENDESK_TOKEN', '')

# Beta tags to track
BETA_TAGS = ['ux_assets', 'ux_feedback', 'ux_login', 'ux_redirect']

# Groups to include (will be resolved to IDs)
TARGET_GROUPS = ['Billing', 'CX Success', 'Distribution', 'ENG - Support']

# Beta release date (when tracking started)
BETA_RELEASE_DATE = '2026-01-21'

# Cache for user and org lookups
user_cache = {}
org_cache = {}
group_ids_cache = None


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
    """Get IDs for the target groups (cached)"""
    global group_ids_cache
    if group_ids_cache is not None:
        return group_ids_cache

    result = zendesk_request('groups.json')
    groups = result.get('groups', [])

    group_ids = []
    for group in groups:
        if group['name'] in TARGET_GROUPS:
            group_ids.append(str(group['id']))
            print(f"  Found group: {group['name']} = {group['id']}")

    group_ids_cache = group_ids
    return group_ids


def get_week_range():
    """Get this week's date range (Monday to today)"""
    today = datetime.now()
    days_since_monday = today.weekday()  # Monday = 0
    start = today - timedelta(days=days_since_monday)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')


def get_alltime_range():
    """Get all-time range (beta release to today)"""
    today = datetime.now()
    return BETA_RELEASE_DATE, today.strftime('%Y-%m-%d')


def get_weekly_ranges():
    """Get date ranges from beta release through end date (Monday to Sunday)"""
    today = datetime.now()
    weeks = []

    # Start from the Monday of the beta release week
    beta_start = datetime.strptime(BETA_RELEASE_DATE, '%Y-%m-%d')
    days_since_monday = beta_start.weekday()
    first_monday = beta_start - timedelta(days=days_since_monday)

    # End date: March 8, 2026
    end_date = datetime(2026, 3, 8)

    current_monday = first_monday
    while current_monday <= end_date:
        week_end = current_monday + timedelta(days=6)  # Sunday

        # For past/current weeks, cap at today if needed
        display_end = week_end
        if week_end > today:
            display_end = today if current_monday <= today else week_end

        weeks.append({
            'start': current_monday.strftime('%Y-%m-%d'),
            'end': week_end.strftime('%Y-%m-%d'),
            'label': current_monday.strftime('%b %d'),
            'is_future': current_monday > today
        })

        current_monday += timedelta(weeks=1)

    return weeks


def fetch_tickets_for_range(start_date, end_date, group_ids):
    """Fetch and filter tickets for a date range"""
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

    # Get beta-tagged tickets
    beta_tickets = [t for t in filtered_tickets if any(tag in t.get('tags', []) for tag in BETA_TAGS)]

    return filtered_tickets, beta_tickets


def enrich_tickets(beta_tickets):
    """Add user/org names to tickets"""
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
    return beta_ticket_details


def get_ticket_data():
    """Get ticket data for both this week and all-time"""
    # Get group IDs
    print("Fetching group IDs...")
    group_ids = set(get_group_ids())
    print(f"Target group IDs: {group_ids}")

    # This week data
    week_start, week_end = get_week_range()
    print(f"\n--- THIS WEEK ({week_start} to {week_end}) ---")
    week_filtered, week_beta = fetch_tickets_for_range(week_start, week_end, group_ids)
    week_beta_details = enrich_tickets(week_beta)

    # All-time data
    alltime_start, alltime_end = get_alltime_range()
    print(f"\n--- SINCE BETA RELEASE ({alltime_start} to {alltime_end}) ---")
    alltime_filtered, alltime_beta = fetch_tickets_for_range(alltime_start, alltime_end, group_ids)
    alltime_beta_details = enrich_tickets(alltime_beta)

    # Historical weekly data for chart
    print(f"\n--- WEEKLY HISTORY ---")
    weekly_ranges = get_weekly_ranges()
    weekly_data = []
    today = datetime.now()
    for wr in weekly_ranges:
        if wr.get('is_future'):
            # Future week - no data yet
            print(f"  {wr['label']} (future)")
            weekly_data.append({
                'label': wr['label'],
                'start': wr['start'],
                'end': wr['end'],
                'total': None,
                'beta': None,
                'percentage': None
            })
        else:
            print(f"  Fetching {wr['label']}...")
            filtered, beta = fetch_tickets_for_range(wr['start'], wr['end'], group_ids)
            total = len(filtered)
            beta_count = len(beta)
            pct = round((beta_count / total * 100), 1) if total > 0 else 0
            weekly_data.append({
                'label': wr['label'],
                'start': wr['start'],
                'end': wr['end'],
                'total': total,
                'beta': beta_count,
                'percentage': pct
            })

    week_total = len(week_filtered)
    week_beta_count = len(week_beta)
    alltime_total = len(alltime_filtered)
    alltime_beta_count = len(alltime_beta)

    # Fetch Help Center article views from Gmail
    help_center_views = None
    if GMAIL_AVAILABLE:
        print("\n--- HELP CENTER VIEWS ---")
        try:
            result = fetch_help_center_views('Dashboard_auto')
            if result:
                help_center_views = result['views']
                print(f"Help Center views: {help_center_views}")
            else:
                print("No Help Center data found in email")
        except Exception as e:
            print(f"Error fetching Help Center data: {e}")

    return {
        'week': {
            'total': week_total,
            'beta': week_beta_count,
            'percentage': round((week_beta_count / week_total * 100), 1) if week_total > 0 else 0,
            'start_date': week_start,
            'end_date': week_end,
            'beta_tickets': week_beta_details
        },
        'alltime': {
            'total': alltime_total,
            'beta': alltime_beta_count,
            'percentage': round((alltime_beta_count / alltime_total * 100), 1) if alltime_total > 0 else 0,
            'start_date': alltime_start,
            'end_date': alltime_end,
            'beta_tickets': alltime_beta_details
        },
        'history': weekly_data,
        'help_center_views': help_center_views,
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    }


def generate_ticket_rows(tickets):
    """Generate HTML table rows for tickets"""
    rows = ""
    for ticket in tickets:
        tags_html = ' '.join([f'<span class="tag">{tag}</span>' for tag in ticket['beta_tags']])
        subject = ticket['subject'][:50] + ('...' if len(ticket['subject']) > 50 else '')
        rows += f'''
            <tr>
                <td><a href="{ticket['url']}" target="_blank">{subject}</a></td>
                <td>{ticket['account']}</td>
                <td>{ticket['requester']}</td>
                <td>{tags_html}</td>
                <td>{ticket['created']}</td>
            </tr>'''
    return rows


def generate_tag_summary(tickets):
    """Generate tag count summary from tickets"""
    tag_counts = {}
    for ticket in tickets:
        for tag in ticket['beta_tags']:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Sort by count descending
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

    rows = ""
    for tag, count in sorted_tags:
        rows += f'''
            <tr>
                <td><span class="tag">{tag}</span></td>
                <td style="text-align: center;">{count}</td>
            </tr>'''
    return rows, len(tickets)


def generate_html(data):
    """Generate the dashboard HTML"""
    week = data['week']
    alltime = data['alltime']
    history = data['history']
    help_center_views = data.get('help_center_views')

    week_rows = generate_ticket_rows(week['beta_tickets'])
    tag_summary_rows, tag_total = generate_tag_summary(alltime['beta_tickets'])

    # Chart data - convert to JSON for proper null handling
    chart_labels = json.dumps([w['label'] for w in history])
    chart_beta = json.dumps([w['beta'] for w in history])
    chart_total = json.dumps([w['total'] for w in history])
    chart_pct = json.dumps([w['percentage'] for w in history])

    # Help Center widget HTML
    if help_center_views is not None:
        help_center_html = f'''
        <div class="dashboard" style="background: rgba(74, 154, 168, 0.2);">
            <div class="section-label">Help Center</div>
            <h2>Article Views</h2>
            <div class="metrics" style="grid-template-columns: 1fr;">
                <div class="metric">
                    <div class="metric-value" style="color: #6bc5d2;">{help_center_views:,}</div>
                    <div class="metric-label">Total Views (Since Beta Release)</div>
                </div>
            </div>
        </div>
        '''
    else:
        help_center_html = ''

    # Pre-compute conditional HTML sections to avoid f-string nesting issues
    if week['beta_tickets']:
        week_table_html = f'''<table class="ticket-table">
                    <thead>
                        <tr>
                            <th>Subject</th>
                            <th>Account</th>
                            <th>Requester</th>
                            <th>Tags</th>
                            <th>Created</th>
                        </tr>
                    </thead>
                    <tbody>{week_rows}</tbody>
                </table>'''
    else:
        week_table_html = '<div class="no-tickets">No beta-tagged tickets this week</div>'

    if alltime['beta_tickets']:
        tag_summary_html = f'''<table class="ticket-table" style="max-width: 300px;">
                    <thead>
                        <tr>
                            <th>Tag</th>
                            <th style="text-align: center;">Count</th>
                        </tr>
                    </thead>
                    <tbody>{tag_summary_rows}</tbody>
                </table>'''
    else:
        tag_summary_html = '<div class="no-tickets">No beta-tagged tickets yet</div>'

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Support Pulse: Beta Tags</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a2332;
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
        .dashboard.alltime {{
            background: rgba(255,255,255,0.05);
        }}
        h1 {{
            color: #fff;
            text-align: center;
            margin-bottom: 10px;
            font-size: 32px;
        }}
        h2 {{
            color: #fff;
            margin-bottom: 20px;
            font-size: 22px;
        }}
        h3 {{
            color: rgba(255,255,255,0.8);
            margin-bottom: 15px;
            font-size: 16px;
        }}
        .subtitle {{
            color: rgba(255,255,255,0.6);
            text-align: center;
            margin-bottom: 40px;
            font-size: 14px;
        }}
        .section-label {{
            color: rgba(255,255,255,0.5);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 10px;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 20px;
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
        .beta .metric-value {{ color: #4a9aa8; }}
        .total .metric-value {{ color: #6bc5d2; }}
        .percentage .metric-value {{ color: #ffffff; }}
        .formula {{
            text-align: center;
            color: rgba(255,255,255,0.5);
            font-size: 14px;
            margin-bottom: 15px;
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
            color: #4a9aa8;
            text-decoration: none;
            margin: 0 10px;
            font-size: 14px;
        }}
        .links a:hover {{
            text-decoration: underline;
        }}
        .ticket-section {{
            margin-top: 30px;
        }}
        .ticket-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        .ticket-table th {{
            background: rgba(255,255,255,0.1);
            color: rgba(255,255,255,0.9);
            padding: 12px 15px;
            text-align: left;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .ticket-table td {{
            padding: 12px 15px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            color: rgba(255,255,255,0.8);
            font-size: 13px;
        }}
        .ticket-table tr:hover {{
            background: rgba(255,255,255,0.05);
        }}
        .ticket-table a {{
            color: #4a9aa8;
            text-decoration: none;
        }}
        .ticket-table a:hover {{
            text-decoration: underline;
        }}
        .tag {{
            display: inline-block;
            background: #4a9aa8;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 10px;
            margin: 2px;
        }}
        .no-tickets {{
            text-align: center;
            color: rgba(255,255,255,0.5);
            padding: 30px;
            font-style: italic;
        }}
        .divider {{
            height: 1px;
            background: rgba(255,255,255,0.1);
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="dashboard" style="text-align: center;">
            <img src="https://media.licdn.com/dms/image/v2/D560BAQF3gD_CaXzIBg/company-logo_200_200/B56ZVIqG4kHoAI-/0/1740680752906/visiting_media_logo?e=2147483647&v=beta&t=djoZIpPoPVhvn_sO_LBSXyjGT-Hn906UWsbIARtiiLU" alt="Visiting Media" style="width: 60px; height: 60px; border-radius: 12px; margin-bottom: 15px;">
            <h1>Support Pulse: Beta Tags</h1>
            <div class="updated">Last updated: {data['updated']}</div>
            <div class="links">
                <a href="https://visitingmedia.zendesk.com/explore/studio#/dashboards/precanned/9425F76AF99EC760E6FDE83C5A99EE472407CBD6B0D5A3DA700AB5DDE040C541" target="_blank">View in Zendesk Explore</a>
            </div>
        </div>

        <!-- This Week -->
        <div class="dashboard">
            <div class="section-label">This Week</div>
            <h2>{week['start_date']} to {week['end_date']}</h2>

            <div class="metrics">
                <div class="metric beta">
                    <div class="metric-value">{week['beta']}</div>
                    <div class="metric-label">Beta Tagged</div>
                </div>
                <div class="metric percentage">
                    <div class="metric-value">{week['percentage']}%</div>
                    <div class="metric-label">Beta %</div>
                </div>
            </div>
            
            <div class="ticket-section">
                <h3>Tagged Tickets</h3>
                {week_table_html}
            </div>
        </div>

        <!-- Since Beta Release -->
        <div class="dashboard alltime">
            <div class="section-label">Since Beta Release</div>
            <h2>{alltime['start_date']} to {alltime['end_date']}</h2>

            <div class="metrics">
                <div class="metric beta">
                    <div class="metric-value">{alltime['beta']}</div>
                    <div class="metric-label">Beta Tagged</div>
                </div>
                <div class="metric percentage">
                    <div class="metric-value">{alltime['percentage']}%</div>
                    <div class="metric-label">Beta %</div>
                </div>
            </div>
        </div>

        <!-- Help Center Views -->
        {help_center_html}

        <!-- Weekly Trend Chart -->
        <div class="dashboard">
            <div class="section-label">Weekly Trend</div>
            <h2>Jan 19 - Mar 8, 2026</h2>
            <div style="height: 300px; margin-top: 20px;">
                <canvas id="trendChart"></canvas>
            </div>

            <div class="ticket-section" style="margin-top: 40px;">
                <h3>Beta Tickets by Tag (Jan 21 - Mar 8, 2026)</h3>
                <p style="color: rgba(255,255,255,0.6); margin-bottom: 15px;">
                    {alltime['beta']} beta-tagged tickets ({alltime['percentage']}% of support volume)
                </p>
                {tag_summary_html}
            </div>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('trendChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {chart_labels},
                datasets: [
                    {{
                        label: 'Beta Tagged',
                        data: {chart_beta},
                        backgroundColor: '#4a9aa8',
                        borderRadius: 6,
                        order: 2
                    }},
                    {{
                        label: 'Total Tickets',
                        data: {chart_total},
                        backgroundColor: 'rgba(107, 197, 210, 0.3)',
                        borderRadius: 6,
                        order: 3
                    }},
                    {{
                        label: 'Beta %',
                        data: {chart_pct},
                        type: 'line',
                        borderColor: '#ffffff',
                        backgroundColor: 'transparent',
                        tension: 0.3,
                        yAxisID: 'y1',
                        order: 1
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        labels: {{ color: 'rgba(255,255,255,0.7)' }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: 'rgba(255,255,255,0.6)' }},
                        grid: {{ color: 'rgba(255,255,255,0.1)' }}
                    }},
                    y: {{
                        position: 'left',
                        ticks: {{ color: 'rgba(255,255,255,0.6)' }},
                        grid: {{ color: 'rgba(255,255,255,0.1)' }},
                        title: {{ display: true, text: 'Tickets', color: 'rgba(255,255,255,0.6)' }}
                    }},
                    y1: {{
                        position: 'right',
                        ticks: {{ color: 'rgba(255,255,255,0.6)' }},
                        grid: {{ display: false }},
                        title: {{ display: true, text: 'Beta %', color: 'rgba(255,255,255,0.6)' }},
                        min: 0,
                        max: 100
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>'''
    return html


def main():
    print("Fetching Zendesk data...")
    data = get_ticket_data()

    print(f"\n--- SUMMARY ---")
    print(f"This Week: {data['week']['beta']} / {data['week']['total']} = {data['week']['percentage']}%")
    print(f"All Time:  {data['alltime']['beta']} / {data['alltime']['total']} = {data['alltime']['percentage']}%")

    print("\nGenerating HTML...")
    html = generate_html(data)

    with open('index.html', 'w') as f:
        f.write(html)
    print("Dashboard saved to index.html")


if __name__ == '__main__':
    main()
