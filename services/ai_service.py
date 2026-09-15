import json
import os

import requests


AI_API_KEY = os.getenv('AI_API_KEY', '').strip()
AI_API_BASE = os.getenv('AI_API_BASE', 'https://api.openai.com/v1').rstrip('/')
AI_MODEL = os.getenv('AI_MODEL', 'gpt-4o-mini')


def extract_document_with_ai(raw_text, filename=None):
    if not raw_text:
        return None

    if not AI_API_KEY:
        return None

    try:
        prompt = (
            'Extract the following fields from this document text. '
            'Return valid JSON only with keys: name, date, time, organization. '
            'Use null if a value is not found. Do not add extra keys.\n\n'
            f'Filename: {filename or "unknown"}\n\nText:\n{raw_text[:12000]}'
        )

        response = requests.post(
            f'{AI_API_BASE}/chat/completions',
            headers={
                'Authorization': f'Bearer {AI_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': AI_MODEL,
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are a helpful document extraction assistant. Extract structured fields from the text and return strict JSON.',
                    },
                    {'role': 'user', 'content': prompt},
                ],
                'temperature': 0.1,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload['choices'][0]['message']['content']
        data = json.loads(content)
        return {
            'name': data.get('name'),
            'date': data.get('date'),
            'time': data.get('time'),
            'organization': data.get('organization'),
        }
    except Exception:
        return None
