"""
Geelark API client - raw HTTP implementation.
Based on the reference scaffold from chunhuduc/tiktok-multi-account-management-geelark.
Docs: https://openapi.geelark.com
"""
import time
import hmac
import hashlib
import requests
import os

BASE_URL = "https://openapi.geelark.com/open/v1"
GEELARK_API_KEY = os.environ.get("GEELARK_API_KEY", "")
GEELARK_API_SECRET = os.environ.get("GEELARK_API_SECRET", "")


def _make_header(api_key: str, api_secret: str) -> dict:
    ts = str(int(time.time() * 1000))
    sign_str = api_key + ts
    sign = hmac.new(api_secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "akey": api_key,
        "ts": ts,
        "sign": sign,
    }


def list_phones(api_key: str, api_secret: str, group_name: str = None, tags: list = None) -> list:
    """Return all phones, paginating automatically."""
    url = f"{BASE_URL}/phone/list"
    page, page_size, all_phones = 1, 100, []
    while True:
        payload = {"page": page, "pageSize": page_size}
        if group_name:
            payload["groupName"] = group_name
        if tags:
            payload["tags"] = tags
        resp = requests.post(url, headers=_make_header(api_key, api_secret), json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(data.get("msg", "Geelark API error"))
        items = data.get("data", {}).get("items", [])
        all_phones.extend(items)
        if len(items) < page_size:
            break
        page += 1
    return all_phones


def create_post_task(api_key: str, api_secret: str, env_id: str, video_url: str, description: str, schedule_at: int) -> dict:
    """
    Schedule a TikTok post on a cloud phone via Geelark task API.
    schedule_at: Unix timestamp (seconds) for when to post.
    Returns task dict or raises on error.
    """
    url = f"{BASE_URL}/tiktok/video/publish"
    payload = {
        "envId": env_id,
        "resourceUrl": video_url,
        "desc": description,
        "scheduleAt": schedule_at,
    }
    resp = requests.post(url, headers=_make_header(api_key, api_secret), json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        return {"error": data.get("msg", "task creation failed")}
    return {"posted": True, "task_id": data.get("data", {}).get("taskId")}


def add_tag(api_key: str, api_secret: str, phone_id: str, tag_name: str) -> bool:
    """Add a tag to a phone (e.g. warmup tag 'ngam')."""
    url = f"{BASE_URL}/phone/tag/add"
    payload = {"id": phone_id, "tagName": tag_name}
    resp = requests.post(url, headers=_make_header(api_key, api_secret), json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json().get("code") == 0


def remove_tag(api_key: str, api_secret: str, phone_id: str, tag_ids: list) -> bool:
    """Remove tags from a phone by tag ID list."""
    url = f"{BASE_URL}/phone/detail/update"
    payload = {"id": phone_id, "tagIDs": tag_ids}
    resp = requests.post(url, headers=_make_header(api_key, api_secret), json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json().get("code") == 0


def upload_temp_file(api_key: str, api_secret: str, file_path: str) -> str:
    """Upload an mp4 to Geelark temp storage. Returns resource_url."""
    url = f"{BASE_URL}/resource/upload"
    with open(file_path, "rb") as f:
        resp = requests.post(url, headers=_make_header(api_key, api_secret), files={"file": f}, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Upload failed: {data.get('msg')}")
    return data["data"]["url"]