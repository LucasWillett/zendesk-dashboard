#!/usr/bin/env python3
"""
Send weekly beta summary email via Gmail API
"""
import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]

DASHBOARD_URL = "https://lucaswillett.github.io/zendesk-dashboard/"

# Recipients - summary only (no feedback digest)
SUMMARY_RECIPIENTS = [
    "gtm-weekly-aaaapge7b6q4al6kkvmraq7qd4@visiting-media.slack.com",  # #gtm-weekly
    "lucas@visitingmedia.com",  # Direct email
]

# Recipients - summary + feedback digest
FULL_RECIPIENTS = [
    "support-internal-aaaak23zhhincvkilre7nnm2ty@visiting-media.slack.com",  # #support-internal
]

# For testing only
TEST_RECIPIENT = "support-internal-aaaak23zhhincvkilre7nnm2ty@visiting-media.slack.com"


def get_gmail_service():
    """Create Gmail API service using OAuth credentials from environment"""
    client_id = os.environ.get('GMAIL_CLIENT_ID')
    client_secret = os.environ.get('GMAIL_CLIENT_SECRET')
    refresh_token = os.environ.get('GMAIL_REFRESH_TOKEN')

    if not all([client_id, client_secret, refresh_token]):
        print("Gmail credentials not found in environment")
        return None

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )

    return build('gmail', 'v1', credentials=creds)


def get_week_dates():
    """Get last week's date range (Monday to Sunday) for Monday morning reports"""
    today = datetime.now()
    # Go back to last Monday
    days_since_monday = today.weekday()
    if days_since_monday == 0:  # If today is Monday, report on previous week
        days_since_monday = 7
    last_monday = today - timedelta(days=days_since_monday)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday.strftime('%b %d'), last_sunday.strftime('%b %d, %Y')


def get_product_area(tag):
    """Map beta tags to Instant Insights product areas"""
    mapping = {
        'ux_assets': 'Asset Library',
        'ux_login': 'Sign in / Sign up',
        'ux_redirect': 'Public Viewer',
        'ux_feedback': 'UI/UX',
    }
    return mapping.get(tag, 'Other')


def create_feedback_digest(tickets):
    """Create ready-to-submit feedback entries for each ticket"""
    if not tickets:
        return '', ''

    html_entries = []
    plain_entries = []

    for i, ticket in enumerate(tickets, 1):
        subject = ticket.get('subject', 'No subject')
        account = ticket.get('account', 'Unknown')
        requester = ticket.get('requester', 'Unknown')
        ticket_url = ticket.get('url', '')
        tags = ticket.get('beta_tags', [])
        product_area = get_product_area(tags[0]) if tags else 'Other'

        # Create a summary (max 120 chars)
        summary = subject[:117] + '...' if len(subject) > 120 else subject

        html_entry = f'''
        <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px; margin-bottom: 15px;">
            <div style="font-weight: bold; color: #856404; margin-bottom: 10px;">📋 Feedback #{i}</div>
            <div style="font-size: 13px; color: #333; margin-bottom: 8px;">
                <strong>Full feedback:</strong> {subject}
            </div>
            <div style="font-size: 13px; color: #333; margin-bottom: 8px;">
                <strong>Summary:</strong> {summary}
            </div>
            <div style="font-size: 13px; color: #333; margin-bottom: 8px;">
                <strong>Reference link:</strong> <a href="{ticket_url}">{ticket_url}</a>
            </div>
            <div style="font-size: 13px; color: #333; margin-bottom: 8px;">
                <strong>Received from:</strong> {account} ({requester})
            </div>
            <div style="font-size: 13px; color: #333; margin-bottom: 8px;">
                <strong>Product area:</strong> {product_area}
            </div>
            <div style="font-size: 13px; color: #333;">
                <strong>Tags:</strong> {', '.join(tags)}
            </div>
        </div>
        '''
        html_entries.append(html_entry)

        plain_entry = f'''
--- Feedback #{i} ---
Full feedback: {subject}
Summary: {summary}
Reference link: {ticket_url}
Received from: {account} ({requester})
Product area: {product_area}
Tags: {', '.join(tags)}
'''
        plain_entries.append(plain_entry)

    html_section = f'''
    <div style="border-top: 2px solid #ffc107; margin-top: 30px; padding-top: 20px;">
        <h3 style="color: #856404; margin-bottom: 15px;">📝 Ready to Submit to Product</h3>
        <p style="font-size: 13px; color: #666; margin-bottom: 15px;">
            Copy each entry below into <a href="https://instant-insights.app/feedback/submit">Instant Insights</a>
        </p>
        {''.join(html_entries)}
    </div>
    '''

    plain_section = f'''

========================================
📝 READY TO SUBMIT TO PRODUCT
========================================
Copy each entry into: https://instant-insights.app/feedback/submit

{''.join(plain_entries)}
'''

    return html_section, plain_section


def create_summary_email(week_beta, week_pct, alltime_beta, alltime_pct, tags_summary, week_tickets=None):
    """Create the summary email content"""
    week_start, week_end = get_week_dates()

    # Build tags line
    if tags_summary:
        tags_line = ", ".join([f"{count} {tag}" for tag, count in tags_summary.items()])
    else:
        tags_line = "No new beta tags this week"

    # Generate feedback digest
    feedback_html, feedback_plain = create_feedback_digest(week_tickets or [])

    # Determine status message
    if week_beta == 0:
        status = "No beta-tagged tickets this week - looking good! 🎉"
    elif week_beta <= 2:
        status = f"{week_beta} beta-tagged ticket{'s' if week_beta > 1 else ''} this week."
    else:
        status = f"{week_beta} beta-tagged tickets this week - worth monitoring."

    html_content = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1a2332; color: white; padding: 30px; border-radius: 12px;">
            <h1 style="margin: 0 0 5px 0; font-size: 24px;">Support Pulse Weekly</h1>
            <p style="margin: 0; color: rgba(255,255,255,0.6); font-size: 14px;">{week_start} - {week_end}</p>
        </div>

        <div style="padding: 30px 0;">
            <p style="font-size: 16px; color: #333; margin-bottom: 25px;">{status}</p>

            <div style="background: #f5f5f5; border-radius: 8px; padding: 20px; margin-bottom: 15px;">
                <div style="font-size: 14px; color: #666; margin-bottom: 5px;">This Week</div>
                <div style="font-size: 24px; font-weight: bold; color: #4a9aa8;">{week_beta} beta-tagged ({week_pct}%)</div>
            </div>

            <div style="background: #f5f5f5; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                <div style="font-size: 14px; color: #666; margin-bottom: 5px;">Since Launch (Jan 21)</div>
                <div style="font-size: 24px; font-weight: bold; color: #1a2332;">{alltime_beta} beta-tagged ({alltime_pct}%)</div>
            </div>

            <p style="font-size: 14px; color: #666;"><strong>Tags this week:</strong> {tags_line}</p>
        </div>

        {feedback_html}

        <div style="border-top: 1px solid #eee; padding-top: 20px;">
            <a href="{DASHBOARD_URL}" style="display: inline-block; background: #4a9aa8; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 500;">View Full Dashboard →</a>
        </div>

        <p style="font-size: 12px; color: #999; margin-top: 30px;">This summary is automatically generated every Monday.</p>
    </div>
    """

    plain_content = f"""
Support Pulse Weekly
{week_start} - {week_end}

{status}

This Week: {week_beta} beta-tagged ({week_pct}%)
Since Launch (Jan 21): {alltime_beta} beta-tagged ({alltime_pct}%)

Tags this week: {tags_line}
{feedback_plain}
View Dashboard: {DASHBOARD_URL}
"""

    return html_content, plain_content


def send_email(service, to_email, subject, html_content, plain_content):
    """Send an email via Gmail API"""
    message = MIMEMultipart('alternative')
    message['to'] = to_email
    message['subject'] = subject

    # Attach plain text and HTML versions
    part1 = MIMEText(plain_content, 'plain')
    part2 = MIMEText(html_content, 'html')
    message.attach(part1)
    message.attach(part2)

    # Encode the message
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

    try:
        sent = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        print(f"Email sent successfully! Message ID: {sent['id']}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def main(test_mode=False):
    """Generate and send the weekly summary email"""
    print("=== Weekly Beta Summary Email ===\n")

    # Get Gmail service
    service = get_gmail_service()
    if not service:
        print("Failed to initialize Gmail service")
        return False

    # Import dashboard data (reuse existing code)
    try:
        from update_dashboard import get_ticket_data
        print("Fetching dashboard data...")
        data = get_ticket_data()
    except Exception as e:
        print(f"Error fetching data: {e}")
        # Use placeholder data if fetch fails
        data = {
            'week': {'beta': 0, 'percentage': 0, 'beta_tickets': []},
            'alltime': {'beta': 0, 'percentage': 0}
        }

    # Extract metrics
    week_beta = data['week']['beta']
    week_pct = data['week']['percentage']
    alltime_beta = data['alltime']['beta']
    alltime_pct = data['alltime']['percentage']

    # Count tags from this week's tickets
    tags_summary = {}
    for ticket in data['week'].get('beta_tickets', []):
        for tag in ticket.get('beta_tags', []):
            tags_summary[tag] = tags_summary.get(tag, 0) + 1

    # Get this week's tickets for feedback digest
    week_tickets = data['week'].get('beta_tickets', [])

    # Create email content
    week_start, week_end = get_week_dates()
    subject = f"Support Pulse Weekly: {week_start} - {week_end}"

    # Summary only (for GTM + email)
    summary_html, summary_plain = create_summary_email(
        week_beta, week_pct, alltime_beta, alltime_pct, tags_summary, week_tickets=None
    )

    # Full content with feedback digest (for support-internal)
    full_html, full_plain = create_summary_email(
        week_beta, week_pct, alltime_beta, alltime_pct, tags_summary, week_tickets
    )

    all_success = True

    # Test mode - send full content to test recipient
    if test_mode:
        print(f"TEST MODE - sending full content to: {TEST_RECIPIENT}")
        success = send_email(service, TEST_RECIPIENT, subject, full_html, full_plain)
        return success

    # Send summary to GTM + email
    print(f"Sending summary to {len(SUMMARY_RECIPIENTS)} recipients...")
    for recipient in SUMMARY_RECIPIENTS:
        print(f"  Sending to {recipient}...")
        success = send_email(service, recipient, subject, summary_html, summary_plain)
        if not success:
            all_success = False

    # Send full content (with feedback digest) to support-internal
    print(f"Sending full content to {len(FULL_RECIPIENTS)} recipients...")
    for recipient in FULL_RECIPIENTS:
        print(f"  Sending to {recipient}...")
        success = send_email(service, recipient, subject, full_html, full_plain)
        if not success:
            all_success = False

    return all_success


if __name__ == '__main__':
    import sys
    test_mode = '--test' in sys.argv
    success = main(test_mode=test_mode)
    exit(0 if success else 1)
