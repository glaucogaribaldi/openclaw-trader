"""
Webshare residential proxy client.
Docs: https://apidocs.webshare.io/proxy-list/list
"""
import time
import random
import json
import os
import requests

WEBSHARE_API = "https://proxy.webshare.io/api/v2/proxy/list/"
_cache = {"data": [], "ts": 0, "ttl": 300}


def list_proxies(api_key: str, country_code: str = None, page_size: int = 100) -> list:
    """List residential proxies from Webshare."""
    params = {"mode": "direct", "page": 1, "page_size": page_size, "valid": "true"}
    if country_code:
        params["country_code__in"] = country_code
    resp = requests.get(WEBSHARE_API, params=params, headers={"Authorization": f"Token {api_key}"}, timeout=15)
    resp.raise_for_status()
    return resp.json().get("results", [])


def get_random_proxy(api_key: str, pool_size: int = 100) -> dict:
    """Get a random proxy from the cached pool."""
    global _cache
    if not _cache["data"] or time.time() - _cache["ts"] > _cache["ttl"]:
        _cache["data"] = list_proxies(api_key, page_size=pool_size)
        _cache["ts"] = time.time()
    return random.choice(_cache["data"])


def to_proxy_string(proxy: dict) -> str:
    """Convert proxy dict to connection string."""
    return f"http://{proxy['username']}:{proxy['password']}@{proxy['proxy_address']}:{proxy['port']}"


def test_proxy(proxy_string: str, timeout: int = 10) -> bool:
    """Test if a proxy can reach the internet."""
    try:
        proxies = {"http": proxy_string, "https": proxy_string}
        resp = requests.get("https://ipinfo.io/json", proxies=proxies, timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def get_ip_info(ip: str, proxy_string: str = None) -> dict:
    """Get timezone and country info for an IP via ipinfo.io."""
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cached_ipinfo")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{ip}.json")
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)
    proxies = {}
    if proxy_string:
        proxies = {"http": proxy_string, "https": proxy_string}
    try:
        resp = requests.get(f"https://ipinfo.io/{ip}/json", proxies=proxies, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            with open(cache_file, "w") as f:
                json.dump(data, f)
            return data
    except Exception:
        pass
    return {}