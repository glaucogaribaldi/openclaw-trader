"""
TikTok Fleet Daemon - Main entry point for multi-account autonomous publishing.

This daemon manages 5-6 TikTok accounts publishing video and post content in autonomy.
Uses Geelark cloud phones, Webshare residential proxies, ffmpeg content pipeline,
and OpenAI caption rewriting.

Run: source .venv/bin/activate && python -m src.main
"""
import os
import sys
import time
import json
from datetime import datetime, timedelta

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import geelark, webshare, scheduler, content, db, monitoring

# Load configuration
def load_config():
    import dotenv
    dotenv.load_dotenv()
    
    return {
        "geelark_api_key": os.environ.get("GEELARK_API_KEY", ""),
        "geelark_api_secret": os.environ.get("GEELARK_API_SECRET", ""),
        "webs_api_key": os.environ.get("WEBSHARE_API_KEY", ""),
        "post_ahead_hours": int(os.getenv("POST_AHEAD_HOURS", "2")),
        "poll_interval_seconds": int(os.getenv("POLL_INTERVAL_SECONDS", "30")),
    }

def init_database():
    """Initialize SQLite database and register phones."""
    db.init()
    print("Database initialized.")

def register_accounts(phones: list):
    """Register phones in the database if not already present."""
    for phone in phones:
        serial_no = phone.get("serialNo", "")
        serial_name = phone.get("serialName", "")
        group_name = phone.get("group", {}).get("name", "") if phone.get("group") else ""
        proxy = phone.get("proxy", "")
        timezone = phone.get("timezone", "")
        country = phone.get("country", "")
        
        db.upsert_phone({
            "serial_no": serial_no,
            "serial_name": serial_name,
            "group_name": group_name,
            "proxy": proxy,
            "timezone": timezone,
            "country": country,
        })
        print(f"Registered phone: {serial_name} ({serial_no})")

def tick(config: dict):
    """One polling tick: check phones, schedule posts."""
    import src.geelark as geelark_client
    
    # Fetch all phones from Geelark
    phones = geelark_client.list_phones(
        config["geelark_api_key"],
        config["geelark_api_secret"]
    )
    
    print(f"{datetime.now():%H:%M:%S} - {len(phones)} phones fetched")
    
    # Register accounts in DB
    register_accounts(phones)
    
    # Get blocked/quarantined phones
    blocked = monitoring.get_quarantined()
    eligible = scheduler.filter_eligible(phones, temporarily_blocked=blocked)
    print(f"  {len(eligible)} eligible phones (out of {len(phones)})")
    
    for phone in eligible:
        try:
            process_phone(phone, config)
        except Exception as e:
            print(f"  {phone.get('serialNo')}: error — {e}")
            monitoring.mark_quarantined(phone.get("serialNo"))
    
    # Clean up completed quarantines
    monitoring.cleanup_quarantines()

def process_phone(phone: dict, config: dict):
    """Process a single phone: verify proxy, schedule post."""
    serial_no = phone["serialNo"]
    
    # Check if quarantined
    if monitoring.is_quarantined(serial_no):
        print(f"  {serial_no}: quarantined, skipping")
        return
    
    # Get phone from DB
    db_phone = db.get_phone(serial_no)
    if not db_phone:
        print(f"  {serial_no}: not in DB, skipping")
        return
    
    # Verify proxy
    proxy_str = db_phone.get("proxy")
    if not proxy_str or not webshare.test_proxy(proxy_str):
        print(f"  {serial_no}: proxy dead — quarantine 30m")
        monitoring.quarantine(serial_no, minutes=30)
        return
    
    # Get last post time and calculate next post
    last = db.get_last_post(serial_no)
    last_dt = datetime.fromtimestamp(last["scheduled_at"]) if last else None
    interval = scheduler.get_interval_hours(phone)
    post_at = scheduler.next_post_time(last_dt, interval)
    
    # Check if we should post ahead
    if post_at > datetime.now() + timedelta(hours=config["post_ahead_hours"]):
        return  # Not time yet
    
    # Get content key and pick unposted video
    content_key = db_phone.get("content_key")
    if not content_key:
        return
    
    video = db.pick_unposted_video(content_key)
    if not video:
        print(f"  {serial_no}: no unposted video for key={content_key}")
        return
    
    # Rewrite caption for the account's country
    country = db_phone.get("country", "US")
    caption = content.rewrite_caption(video.get("description", ""), country=country)
    
    # Get video resource URL
    resource_url = video.get("resource_url")
    if not resource_url:
        print(f"  {serial_no}: no resource_url for video {video['id']}, skipping")
        return
    
    # Create post task via Geelark
    result = geelark.create_post_task(
        config["geelark_api_key"],
        config["geelark_api_secret"],
        env_id=phone["id"],
        video_url=resource_url,
        description=caption,
        schedule_at=int(post_at.timestamp()),
    )
    
    if result.get("error"):
        print(f"  {serial_no}: post task failed — {result['error']}")
        return
    
    # Mark video as posted in DB
    db.mark_video_posted(
        video_id=video["id"],
        serial_no=serial_no,
        task_id=result.get("task_id", ""),
        scheduled_at=int(post_at.timestamp()),
        slot=0,
    )
    
    post_time = datetime.fromtimestamp(post_at.timestamp())
    print(f"  {serial_no}: scheduled at {post_time.strftime('%Y-%m-%d %H:%M')} local")

def main():
    config = load_config()
    init_database()
    
    print("TikTok Fleet Daemon started. Polling every {} seconds.".format(
        config["poll_interval_seconds"]))
    
    while True:
        try:
            tick(config)
            time.sleep(config["poll_interval_seconds"])
        except Exception as e:
            print(f"{datetime.now():%H:%M:%S} - unhandled error: {e}")
            print("Retrying in 15 minutes...")
            time.sleep(900)

if __name__ == "__main__":
    main()