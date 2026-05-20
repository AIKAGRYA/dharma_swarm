import requests
from src.settings import settings

api_key = str(settings.MOLTBOOK_API_KEY).strip()
url = "https://www.moltbook.com/api/v1/agents/me/setup-owner-email"
payload = {"email": settings.EMAIL_MOLTBOOK_AGENT_OWNER}

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

response = requests.post(url, json=payload, headers=headers)

if response.status_code == 401:
    print("Trying without 'Bearer' prefix...")
    headers["Authorization"] = api_key
    response = requests.post(url, json=payload, headers=headers)

print(f"Final Status: {response.status_code}")
print(f"Final Response: {response.json()}")
