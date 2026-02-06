#!/usr/bin/env python3
"""
Test Zendesk Explore API access
"""
import os
import json
import requests
import time

# You can set these manually for testing, or use env vars
ZENDESK_SUBDOMAIN = os.environ.get('ZENDESK_SUBDOMAIN', 'visitingmedia')
ZENDESK_EMAIL = os.environ.get('ZENDESK_EMAIL', '')
ZENDESK_TOKEN = os.environ.get('ZENDESK_TOKEN', '')

# Report IDs from the URLs you shared
REPORT_ALL_TIME = 248613961
REPORT_THIS_WEEK = 248613871

def explore_export(query_id):
    """Try to export an Explore report"""
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/explore/exports"
    auth = (f"{ZENDESK_EMAIL}/token", ZENDESK_TOKEN)

    payload = {
        "query_id": query_id
    }

    print(f"Attempting to export query {query_id}...")
    print(f"URL: {url}")

    try:
        response = requests.post(url, auth=auth, json=payload, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")

        if response.status_code == 200 or response.status_code == 201:
            return response.json()
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def check_export_status(export_id):
    """Check the status of an export job"""
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/explore/exports/{export_id}"
    auth = (f"{ZENDESK_EMAIL}/token", ZENDESK_TOKEN)

    try:
        response = requests.get(url, auth=auth, timeout=30)
        print(f"Export status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"Error: {e}")
        return None


def test_guide_analytics():
    """Test Help Center/Guide analytics API"""
    auth = (f"{ZENDESK_EMAIL}/token", ZENDESK_TOKEN)

    # Test 1: List articles
    print("\n--- Testing Help Center Articles API ---")
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/help_center/articles.json"
    try:
        response = requests.get(url, auth=auth, timeout=30)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            articles = data.get('articles', [])
            print(f"Found {len(articles)} articles")
            if articles:
                # Show first article details
                art = articles[0]
                print(f"Sample article: {art.get('title', 'N/A')[:50]}")
                print(f"  ID: {art.get('id')}")
                print(f"  Section ID: {art.get('section_id')}")
    except Exception as e:
        print(f"Error: {e}")

    # Test 2: Try Help Center stats endpoint
    print("\n--- Testing Help Center Stats API ---")
    stats_endpoints = [
        "help_center/stats.json",
        "help_center/articles/stats.json",
        "guide/stats.json",
    ]
    for endpoint in stats_endpoints:
        url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/{endpoint}"
        try:
            response = requests.get(url, auth=auth, timeout=10)
            print(f"{endpoint}: {response.status_code}")
            if response.status_code == 200:
                print(f"  Response: {response.text[:200]}")
        except Exception as e:
            print(f"{endpoint}: Error - {e}")

    # Test 3: List brands (to find beta help center brand ID)
    print("\n--- Testing Brands API ---")
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/brands.json"
    try:
        response = requests.get(url, auth=auth, timeout=30)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            brands = data.get('brands', [])
            print(f"Found {len(brands)} brands:")
            for brand in brands:
                print(f"  - {brand.get('name')}: ID={brand.get('id')}, subdomain={brand.get('subdomain')}")
    except Exception as e:
        print(f"Error: {e}")

    # Test 4: List sections (categories of articles)
    print("\n--- Testing Help Center Sections API ---")
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/help_center/sections.json"
    try:
        response = requests.get(url, auth=auth, timeout=30)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            sections = data.get('sections', [])
            print(f"Found {len(sections)} sections")
    except Exception as e:
        print(f"Error: {e}")


def main():
    if not ZENDESK_EMAIL or not ZENDESK_TOKEN:
        print("Please set ZENDESK_EMAIL and ZENDESK_TOKEN environment variables")
        print("Or edit this script to add them directly for testing")
        return

    print("=== Testing Zendesk Explore API ===\n")

    # Test Explore export
    result = explore_export(REPORT_ALL_TIME)

    if result:
        export_id = result.get('id')
        if export_id:
            print(f"\nExport job created: {export_id}")
            print("Waiting 5 seconds for processing...")
            time.sleep(5)
            check_export_status(export_id)

    # Also test Help Center API
    test_guide_analytics()


if __name__ == '__main__':
    main()
