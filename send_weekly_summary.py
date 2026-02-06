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

# Recipients - Slack channels via email integration + direct email
RECIPIENT_EMAILS = [
    "gtm-weekly-aaaapge7b6q4al6kkvmraq7qd4@visiting-media.slack.com",  # #gtm-weekly
    "support-internal-aaaak23zhhincvkilre7nnm2ty@visiting-media.slack.com",  # #support-internal
    "lucas@visitingmedia.com",  # Direct email
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
    """Get this week's date range (Monday to today)"""
    today = datetime.now()
    days_since_monday = today.weekday()
    start = today - timedelta(days=days_since_monday)
    return start.strftime('%b %d'), today.strftime('%b %d, %Y')


def create_summary_email(week_beta, week_pct, alltime_beta, alltime_pct, tags_summary):
    """Create the summary email content"""
    week_start, week_end = get_week_dates()

    # Build tags line
    if tags_summary:
        tags_line = ", ".join([f"{count} {tag}" for tag, count in tags_summary.items()])
    else:
        tags_line = "No new beta tags this week"

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
            <h1 style="margin: 0 0 5px 0; font-size: 24px;">Weekly Beta Summary</h1>
            <p style="margin: 0; color: rgba(255,255,255,0.6); font-size: 14px;">{week_start} - {week_end}</p>
        </div>

        <div style="padding: 30px 0;">
            <p style="font-size: 16px; color: #333; margin-bottom: 20px;">{status}</p>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr>
                    <td style="padding: 15px; background: #f5f5f5; border-radius: 8px; text-align: center; width: 50%;">
                        <div style="font-size: 32px; font-weight: bold; color: #4a9aa8;">{week_beta}</div>
                        <div style="font-size: 12px; color: #666; text-transform: uppercase;">This Week</div>
                    </td>
                    <td style="width: 20px;"></td>
                    <td style="padding: 15px; background: #f5f5f5; border-radius: 8px; text-align: center; width: 50%;">
                        <div style="font-size: 32px; font-weight: bold; color: #1a2332;">{week_pct}%</div>
                        <div style="font-size: 12px; color: #666; text-transform: uppercase;">Beta %</div>
                    </td>
                </tr>
            </table>

            <p style="font-size: 14px; color: #666; margin-bottom: 10px;"><strong>Tags this week:</strong> {tags_line}</p>
            <p style="font-size: 14px; color: #666;"><strong>Since launch:</strong> {alltime_beta} total ({alltime_pct}% of support volume)</p>
        </div>

        <div style="border-top: 1px solid #eee; padding-top: 20px;">
            <a href="{DASHBOARD_URL}" style="display: inline-block; background: #4a9aa8; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 500;">View Full Dashboard →</a>
        </div>

        <p style="font-size: 12px; color: #999; margin-top: 30px;">This summary is automatically generated every Friday.</p>
    </div>
    """

    plain_content = f"""
Weekly Beta Summary
{week_start} - {week_end}

{status}

This Week: {week_beta} beta-tagged tickets ({week_pct}%)
Tags: {tags_line}
Since Launch: {alltime_beta} total ({alltime_pct}%)

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

    # Create email content
    week_start, week_end = get_week_dates()
    subject = f"Weekly Beta Summary: {week_start} - {week_end}"
    html_content, plain_content = create_summary_email(
        week_beta, week_pct, alltime_beta, alltime_pct, tags_summary
    )

    # Determine recipients
    if test_mode:
        recipients = [TEST_RECIPIENT]
        print(f"TEST MODE - sending only to: {TEST_RECIPIENT}")
    else:
        recipients = RECIPIENT_EMAILS
        print(f"Sending to {len(recipients)} recipients...")

    # Send to all recipients
    all_success = True
    for recipient in recipients:
        print(f"  Sending to {recipient}...")
        success = send_email(service, recipient, subject, html_content, plain_content)
        if not success:
            all_success = False

    return all_success


if __name__ == '__main__':
    import sys
    test_mode = '--test' in sys.argv
    success = main(test_mode=test_mode)
    exit(0 if success else 1)
