#!/usr/bin/env python3
"""
Fetch Zendesk Explore report from Gmail
"""
import os
import base64
import csv
import io
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Gmail API scope
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


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


def search_emails(service, query, max_results=5):
    """Search for emails matching query"""
    try:
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        return results.get('messages', [])
    except Exception as e:
        print(f"Error searching emails: {e}")
        return []


def get_email_details(service, msg_id):
    """Get full email details including attachments"""
    try:
        message = service.users().messages().get(
            userId='me',
            id=msg_id,
            format='full'
        ).execute()
        return message
    except Exception as e:
        print(f"Error getting email: {e}")
        return None


def get_attachment(service, msg_id, attachment_id):
    """Download an email attachment"""
    try:
        attachment = service.users().messages().attachments().get(
            userId='me',
            messageId=msg_id,
            id=attachment_id
        ).execute()
        data = attachment.get('data', '')
        return base64.urlsafe_b64decode(data)
    except Exception as e:
        print(f"Error getting attachment: {e}")
        return None


def parse_csv_attachment(csv_data):
    """Parse CSV data and extract the view count"""
    try:
        content = csv_data.decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))

        total_views = 0
        rows = list(reader)

        print(f"CSV has {len(rows)} rows")
        if rows:
            print(f"Columns: {list(rows[0].keys())}")

        for row in rows:
            # Look for view count column - adjust based on actual CSV format
            # Common column names: 'Count', 'Views', 'Count (Articles viewed)', etc.
            for key in row:
                if 'count' in key.lower() or 'view' in key.lower():
                    try:
                        total_views += int(float(row[key]))
                    except (ValueError, TypeError):
                        pass

        return total_views, rows
    except Exception as e:
        print(f"Error parsing CSV: {e}")
        return 0, []


def fetch_help_center_views(report_name='Dashboard_auto'):
    """
    Fetch Help Center article views from Zendesk Explore email report
    """
    service = get_gmail_service()
    if not service:
        return None

    # Search for Zendesk Explore emails
    query = f'from:no-reply@zendeskexplore.com subject:"Your delivery of {report_name}" has:attachment newer_than:2d'

    print(f"Searching for emails: {query}")
    messages = search_emails(service, query)

    if not messages:
        # Try a broader search
        query = 'from:no-reply@zendeskexplore.com has:attachment newer_than:7d'
        print(f"No results, trying broader search: {query}")
        messages = search_emails(service, query)

    if not messages:
        print("No Zendesk report emails found")
        return None

    print(f"Found {len(messages)} matching emails")

    # Get the most recent email
    for msg in messages:
        email = get_email_details(service, msg['id'])
        if not email:
            continue

        # Get email subject for debugging
        headers = email.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No subject')
        print(f"Checking email: {subject}")

        # Look for CSV attachment
        parts = email.get('payload', {}).get('parts', [])
        for part in parts:
            filename = part.get('filename', '')
            if filename.endswith('.csv'):
                print(f"Found CSV attachment: {filename}")
                attachment_id = part.get('body', {}).get('attachmentId')
                if attachment_id:
                    csv_data = get_attachment(service, msg['id'], attachment_id)
                    if csv_data:
                        views, rows = parse_csv_attachment(csv_data)
                        return {
                            'views': views,
                            'rows': rows,
                            'filename': filename,
                            'subject': subject
                        }

    print("No CSV attachments found in emails")
    return None


def main():
    """Test the Gmail fetch functionality"""
    print("=== Testing Gmail Fetch ===\n")

    # Try to fetch all-time report
    print("--- Fetching Help Center Views ---")
    result = fetch_help_center_views('all_time')

    if result:
        print(f"\nSuccess!")
        print(f"Email subject: {result['subject']}")
        print(f"CSV file: {result['filename']}")
        print(f"Total views: {result['views']}")
        print(f"Data rows: {len(result['rows'])}")
    else:
        print("\nNo data found. Make sure:")
        print("1. Zendesk Explore report is scheduled to email")
        print("2. The email has been delivered")
        print("3. Search query matches your email subject")


if __name__ == '__main__':
    main()
