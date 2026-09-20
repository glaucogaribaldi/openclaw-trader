# TikTok Fleet Daemon - System Status

## Project Overview
Autonomous management system for 5-6 TikTok accounts with video publishing and posting.

## Architecture
- **Python 3.11+** core daemon
- **Geelark cloud phones** for in-app posting (organic, API-free)
- **Webshare residential proxies** (1 IP per account, country-matched)
- **SQLite** state store for accounts, videos, and post history
- **OpenAI GPT-4o-mini** for caption rewriting per country
- **ffmpeg** for video uniquification (LUT color grading, speed/pitch jitter)
- **yt-dlp** for video sourcing from TikTok channels
- **APScheduler-style scheduling** with 10% random jitter

## Directory Structure
```
/Users/zava/.openclaw/workspace/
├── .env                     # API keys (gitignored)
├── requirements.txt         # Python dependencies
├── tiktok_fleet.db          # SQLite database (auto-generated)
├── src/
│   ├── __init__.py          # Package init
│   ├── db.py               # SQLite state store
│   ├── geelark.py          # Geelark API client (raw HTTP)
│   ├── webshare.py         # Webshare proxy client
│   ├── scheduler.py        # Post scheduling with jitter
│   ├── content.py          # Content pipeline (ffmpeg, AI captions)
│   ├── monitoring.py       # Account health & quarantine
│   └── main.py             # Main daemon loop
├── data/
│   └── videos/             # Video files directory
├── logs/                   # Application logs
└── luts/                   # ffmpeg LUT color grading files
```

## Installed Dependencies
- openai>=1.0.0
- requests>=2.32.0
- yt-dlp>=2025.1.0
- python-dotenv>=1.0.0
- ffmpeg (system binary required)

## Database Schema
### phones table
- serial_no (PK, TEXT) - Phone serial number
- serial_name (TEXT) - Human-readable account name
- group_name (TEXT) - Account group/fleet assignment
- proxy (TEXT) - Webshare proxy connection string
- timezone (TEXT) - Account timezone (e.g., Europe/Rome)
- country (TEXT) - Account country code (IT, US, UK, etc.)
- slot_times (TEXT) - Scheduled post slots
- content_key (TEXT) - Source channel identifier
- video_posts (INTEGER) - Total posts made
- profiled_at (INTEGER) - Last profiling timestamp

### videos table
- id (PK, TEXT) - Video unique identifier
- source_channel (TEXT) - TikTok channel @handle
- original_url (TEXT) - Source video URL
- edited_path (TEXT) - Local edited video path
- resource_url (TEXT) - Geelark upload URL
- description (TEXT) - Video description/caption
- posted (INTEGER) - 0=unposted, 1=posted
- created_at (INTEGER) - Creation timestamp

### post_history table
- id (PK, AUTOINCREMENT)
- serial_no (TEXT) - Account phone serial
- video_id (TEXT) - Posted video ID
- task_id (TEXT) - Geelark task ID
- scheduled_at (INTEGER) - Scheduled post time
- slot (INTEGER) - Slot number
- posted_at (INTEGER) - Actual post time

## Key Features Implemented

### 1. Account Management
- Phone registration and configuration in SQLite
- Proxy assignment per account
- Country matching (IP geolocation for TikTok geo-tags)
- Video posts counting and tracking

### 2. Scheduling System
- Per-account posting intervals (configured via Geelark tags like "8h", "12h")
- 10% random jitter to prevent synchronized posting
- Warmup tag system ("ngam" - accounts tagged skip until warmed)
- Eligibility filtering (has group, not in warmup, not quarantined)
- Next post time calculation with jitter

### 3. Content Pipeline
- yt-dlp integration for video sourcing from TikTok channels
- ffmpeg LUT color grading (random .cube file from library)
- Speed/pitch variation (0.95x-1.05x random factor)
- OpenAI GPT-4o-mini caption rewriting per country:
  - US/MX: "casual American hook-first TikTok style"
  - UK/EU: "British English, slightly more formal, local references"
- Caption under 150 characters

### 4. Proxy & Safety System
- Webshare residential proxy integration
- Proxy health check before every post
- 30-minute quarantine on proxy failure
- IP geolocation verification (proxy country must match account country)
- Error logging to logs/errors.log

### 5. Monitoring & Quarantine
- Quarantine state tracking in SQLite
- Automatic cleanup of expired quarantines
- Error logging with account context
- Real-time eligibility filtering

## How to Run

### 1. Setup
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install openai requests yt-dlp python-dotenv

# Ensure ffmpeg is installed and on PATH
which ffmpeg
```

### 2. Configure
```bash
# Create .env file with your API keys
cat > .env << 'EOF'
GEELARK_API_KEY=your_geelark_api_key
GEELARK_API_SECRET=your_geelark_api_secret
WEBSHARE_API_KEY=your_webshare_api_key
POST_AHEAD_HOURS=2
POLL_INTERVAL_SECONDS=30
EOF
```

### 3. Initialize
```bash
# In the workspace directory
source .venv/bin/activate
PYTHONPATH=src python3 -c "from src import db; db.init(); print('Database ready')"
```

### 4. Run the Daemon
```bash
PYTHONPATH=src python3 -m src.main
```

The daemon will:
- Fetch all phones from Geelark API
- Filter eligible accounts
- Verify proxy health
- Pick unposted videos
- Rewrite captions per country
- Schedule posts via Geelark Task API
- Repeat every 30 seconds (configurable)

## Safety & Compliance

⚠️ **Critical TikTok Automation Safeguards:**

1. **Rate Limits**: Max 1-2 posts per account per day
2. **Geographic Match**: Proxy country MUST match account country/region
3. **Warmup System**: New accounts tagged "ngam" skip posting until manually removed
4. **Proxy Quarantine**: 30-minute quarantine on proxy failure before retry
5. **Post Ahead**: System only schedules posts within POST_AHEAD_HOURS (default 2h)
6. **Manual Override**: Dashboard capability for manual posting if needed
7. **Audit Log**: All posts recorded in post_history with task IDs and timestamps

8. **Backup Manual Posting**: Always maintain ability to post manually as backup

## Next Development Phases

### Phase 1: Geelark Authentication (This Week)
- [ ] Test Geelark API authentication with real API keys
- [ ] Register 5-6 cloud phone accounts
- [ ] Assign Webshare residential proxies per account
- [ ] Test phone/proxy pairing and IP geolocation

### Phase 2: Basic Posting Flow (Week 2)
- [ ] Test single-account video upload via Geelark
- [ ] Test caption rewriting with OpenAI
- [ ] Test ffmpeg LUT application
- [ ] End-to-end single account posting

### Phase 3: Multi-Account Scheduling (Week 3)
- [ ] Test scheduler with 5-6 accounts
- [ ] Implement jitter per account
- [ ] Prevent overlapping posts
- [ ] Post history tracking

### Phase 4: Web Dashboard (Week 4)
- [ ] Flask web interface
- [ ] Real-time account status
- [ ] Post history viewing
- [ ] Manual override capabilities
- [ ] Error alerts and retry controls

### Phase 5: Content Management (Week 5)
- [ ] yt-dlp channel subscription
- [ ] Automatic video downloading
- [ ] LUT library management
- [ ] Multi-language caption support

## Reference Implementations Studied
- chunhuduc/tiktok-multi-account-management-geelark (GitHub ⭐1)
- DreamingWater/TiktokAutomation (GitHub ⭐256)
- wkaisertexas/tiktok-uploader (GitHub ⭐763)
- RayVentura/ShortGPT (GitHub ⭐7,897)

## Contact & Support
- Project: TikTok Fleet Daemon
- Developer: TRE (OpenClaw assistant)
- Target: 5-6 TikTok accounts, autonomous publishing
- timezone: Europe/Rome