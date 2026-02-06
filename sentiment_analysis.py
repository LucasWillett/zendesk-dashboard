#!/usr/bin/env python3
"""
Sentiment analysis for support tickets using Claude Haiku
"""
import os
import json
import anthropic


def analyze_ticket_sentiment(tickets):
    """
    Analyze sentiment of beta-tagged tickets using Claude Haiku

    Returns dict with:
    - overall_sentiment: positive/neutral/negative
    - sentiment_scores: breakdown by category
    - ticket_sentiments: individual ticket analysis
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("ANTHROPIC_API_KEY not found")
        return None

    if not tickets:
        print("No tickets to analyze")
        return {
            'overall_sentiment': 'neutral',
            'sentiment_breakdown': {'positive': 0, 'neutral': 0, 'negative': 0},
            'ticket_sentiments': [],
            'summary': 'No beta-tagged tickets to analyze'
        }

    client = anthropic.Anthropic(api_key=api_key)

    # Prepare ticket summaries for analysis
    ticket_texts = []
    for i, ticket in enumerate(tickets):
        ticket_texts.append(f"Ticket {i+1}: {ticket.get('subject', 'No subject')}")

    tickets_str = "\n".join(ticket_texts)

    prompt = f"""Analyze the sentiment of these support tickets. For each ticket, determine if the customer sentiment is positive, neutral, or negative based on the subject line.

Tickets:
{tickets_str}

Respond in JSON format:
{{
    "ticket_sentiments": [
        {{"ticket_num": 1, "sentiment": "positive/neutral/negative", "reason": "brief reason"}}
    ],
    "overall_sentiment": "positive/neutral/negative",
    "summary": "1-2 sentence summary of overall customer sentiment"
}}

Only respond with valid JSON, no other text."""

    try:
        print(f"Analyzing sentiment for {len(tickets)} tickets...")

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()

        # Parse JSON response
        result = json.loads(result_text)

        # Calculate breakdown
        sentiments = [t['sentiment'] for t in result.get('ticket_sentiments', [])]
        breakdown = {
            'positive': sentiments.count('positive'),
            'neutral': sentiments.count('neutral'),
            'negative': sentiments.count('negative')
        }
        result['sentiment_breakdown'] = breakdown

        # Add ticket details back
        for i, ts in enumerate(result.get('ticket_sentiments', [])):
            if i < len(tickets):
                ts['subject'] = tickets[i].get('subject', '')
                ts['id'] = tickets[i].get('id', '')

        print(f"Sentiment analysis complete: {result['overall_sentiment']}")
        print(f"Breakdown: {breakdown}")

        return result

    except json.JSONDecodeError as e:
        print(f"Error parsing sentiment response: {e}")
        print(f"Raw response: {result_text}")
        return None
    except Exception as e:
        print(f"Error analyzing sentiment: {e}")
        return None


def main():
    """Test sentiment analysis"""
    # Test with sample tickets
    test_tickets = [
        {'id': 1, 'subject': 'Cannot login to my account - very frustrated!'},
        {'id': 2, 'subject': 'Question about uploading assets'},
        {'id': 3, 'subject': 'Love the new interface, just need help with one thing'},
    ]

    result = analyze_ticket_sentiment(test_tickets)
    if result:
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
