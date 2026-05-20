import requests
from src.settings import settings
from src.utils import log

headers = {
    "Authorization": f"Bearer {settings.MOLTBOOK_API_KEY}",
    "Content-Type": "application/json",
}
timeout = settings.MOLTBOOK_API_TIMEOUT


def handle_response(response, url):
    if response.status_code in [200, 201]:
        data = response.json()
        if isinstance(data, dict):
            data["success"] = True
            return data
        return {"success": True, "data": data}
    else:
        log.error(f"API Error {response.status_code} at {url}: {response.text}")
        return {"success": False, "error": response.text}


def get_me():
    try:
        url = f"{settings.MOLTBOOK_BASE_URL}/agents/me"
        response = requests.get(url, headers=headers, timeout=timeout)
        return handle_response(response, url)
    except requests.exceptions.Timeout:
        log.error("get_me request timeout")
        return None
    except Exception as e:
        log.error(f"get_me error: {e}")
        return None


get_me()
