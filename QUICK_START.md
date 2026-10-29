# TikTok Fleet Daemon - Quick Start Guide

## Prerequisites

1. **Python 3.11+** installed
2. **ffmpeg** installed and on system PATH (`which ffmpeg` should return a path)
3. **Geelark account** with cloud phones created
4. **Webshare account** with residential proxies
5. **OpenAI API key** for caption rewriting

## Installation

```bash
# 1. Create workspace directory
mkdir -p ~/openclaw/workspace
cd ~/openclaw/workspace

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install openai requests yt-dlp python-dotenv

# 4. Verify ffmpeg
ffmpeg -version  # should show version info
```

## Configuration

### 1. Set up API keys
```bash
cat > .env << 'EOF'
GEELARK_API_KEY=your_geelark_api_key_here
GEELARK_API_SECRET=your_geelark_api_secret_here
WEBSHARE_API_KEY=your_webshare_api_key_here
POST_AHEAD_HOURS=2
POLL_INTERVAL_SECONDS=30
EOF
```

### 2. Verify configuration
```bash
source .venv/bin/activate
PYTHONPATH=src python3 -c "
from src import db, geelark, webshare, scheduler, content, monitoring
db.init()
print('✓ Database initialized')
print('✓ All modules loaded successfully')
"
```

## Running the Daemon

### Single Test Run
```bash
PYTHONPATH=src python3 << 'PYEOF'
import db
import scheduler
import monitoring
import time
from datetime import datetime

# Initialize
db.init()
monitoring.init_quarantine_table()

# Test phone registration
test_phone = {
    "serial_no": "demo_account_1",
    "serial_name": "DemoAccount1",
    "group_name": "tiktok_fleet",
    "proxy": "http://demo-proxy:12345",
    "timezone": "Europe/Rome",
    "country": "IT"
}
db.upsert_phone(test_phone)
print(f"✓ Registered: {test_phone['serial_name']}")

# Test eligibility
is_eligible = scheduler.is_eligible(
    {"serialNo": "demo_account_1", "group": {"name": "tiktok_fleet"}, "tags": [{"name": "8h"}]},
    set()
)
print(f"✓ Eligible: {is_eligible}")

# Test interval
interval = scheduler.get_interval_hours(
    {"serialNo": "demo_account_1", "group": {"name": "tiktok_fleet"}, "tags": [{"name": "8h"}]}
)
print(f"✓ Interval: {interval}h")

# Test quarantine
monitoring.mark_quarantined("demo_account_1")
print(f"✓ Quarantined: {monitoring.is_quarantined('demo_account_1')}")
monitoring.cleanup_quarantines()
print("✓ Quarantine cleaned")

print("\n✅ Basic test suite passed!")
PYEOF
```

### Run Full Daemon
```bash
# In the workspace, with virtual environment active
source .venv/bin/activate
PYTHONPATH=src python3 -m src.main
```

The daemon will run indefinitely, polling every 30 seconds (configurable via POLL_INTERVAL_SECONDS):
- Fetches phone status from Geelark
- Checks proxy health
- Schedules posts with jitter
- Tracks post history
- Quarantines failing accounts

## Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `POST_AHEAD_HOURS` | `2` | How far ahead to schedule posts (hours) |
| `POLL_INTERVAL_SECONDS` | `30` | How often the daemon checks for new posts (seconds) |
| `proxy` per account | required | Webshare residential proxy per account |
| `country` per account | required | Must match proxy country for TikTok geo-compliance |
| Tag `8h`, `12h`, etc. | optional | Posting interval in hours (read by scheduler) |
| Tag `ngam` | optional | Warmup tag - accounts skip posting until tag removed |

## Safety Checklist

Before running with real accounts, verify:

- [ ] Geelark API keys work (test with `list_phones`)
- [ ] Webshare proxies work (test with `test_proxy`)
- [ ] Each account has a unique proxy IP
- [ ] Proxy country matches account country (e.g., IT proxy for Italy account)
- [ ] OpenAI API key valid (test caption rewriting)
- [ ] ffmpeg works (`ffmpeg -version`)
- [ ] yt-dlp works (`yt-dlp --version`)
- [ ] Database initialized without errors
- [ ] At least one phone registered in SQLite

## Troubleshooting

### Common Issues

1. **Geelark API auth failed**
   - Check GEELARK_API_KEY and GEELARK_API_SECRET
   - Ensure hash signature is correct
   - Verify API keys are active on Geelark dashboard

2. **Proxy test failed**
   - Verify WEBSHARE_API_KEY
   - Check proxy format: `http://username:password@host:port`
   - Ensure proxy can reach internet

3. **Caption generation fails**
   - Verify OpenAI API key in .env
   - Check internet connectivity
   - Ensure model "gpt-4o-mini" is available

4. **Database errors**
   - Delete tiktok_fleet.db and re-run `db.init()` to recreate
   - Check file permissions on workspace directory

5. **Posts not scheduling**
   - Check phone has `group.name` set
   - Check for `ngam` warmup tag - remove when account is warmed up
   - Verify `content_key` is set for video sourcing
   - Check `post_at` time is in the future but within `POST_AHEAD_HOURS`

6. **IP geolocation mismatch**
   - Use `webshare.get_ip_info(ip)` to verify proxy country
   - Ensure `country` field in phone config matches proxy geolocation
   - Mismatch will trigger TikTok geographic flags

## Next Steps After Basic Setup

1. Register 5-6 actual Geelark cloud phone accounts
2. Assign 5-6 unique Webshare residential proxies (country-matched)
3. Test single-account posting flow end-to-end
4. Scale to multi-account with scheduler jitter
5. Build web dashboard for monitoring and manual override
6. Implement automatic warmup tag management
7. Add analytics and post performance tracking

## Getting Help

- Check `logs/errors.log` for error details
- Run `python3 -c "from src import monitoring; monitoring.cleanup_quarantines()"` to reset quarantine state
- Re-run `db.init()` to reset database if needed
- Check SYSTEM_STATUS.md for full architecture documentation

---
*TikTok Fleet Daemon v1.0 - Multi-account autonomous publishing system*
*Adapted from chunhuduc/tiktok-multi-account-management-geelark (GitHub)*