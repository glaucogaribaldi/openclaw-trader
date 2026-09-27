# TikTok Account Management Project Plan

## Overview
Project to administer 5-6 TikTok accounts publishing video and post content in autonomy (automatically).

## Existing Solutions Found on GitHub

### 1. **DreamingWater/TiktokAutomation** (256 ⭐)
- Python-based comprehensive TikTok automation
- Features: proxy configuration, email accounts, account registration/login, video browsing, video download, video editing/pre-processing
- Last updated: 2023-08-29
- Status: Open-sourced project

### 2. **wkaisertexas/tiktok-uploader** (763 ⭐)
- Simple video uploader for TikTok
- Python-based
- Good for basic upload functionality

### 3. **chunhuduc/tiktok-multi-account-management-geelark** (1 ⭐) ⭐ **RECOMMENDED**
- Python scaffold for multi-account automation
- Uses Geelark cloud phones + Webshare proxies
- ffmpeg content pipeline with LUT color grading
- SQLite scheduler with organic cadence jitter
- OpenAI/Gemini caption rewriting per country
- In-app posting via Geelark task API (organic to TikTok detection)
- Designed for 50-100+ accounts per deployment
- **Best architectural reference for 5-6 account management**

### 4. **marouanedaouyny-prog/tiktok-dashboard**
- Multi-account management dashboard with scraping and analytics
- Basic functionality

### 5. **RayVentura/ShortGPT** (7,897 ⭐)
- AI framework for YouTube Shorts/TikTok channel automation
- Experimental but heavily starred
- Good for AI content generation base

### 6. **l-portet/tiktok-warmup-bot**
- Account warming/aging tool (one swipe at a time)
- Good for new account safety

## Selected Architecture

Based on the **chunhuduc/tiktok-multi-account-management-geelark** scaffold, I'm adapting the design for 5-6 accounts with these key components:

### Architecture Diagram
```
Geelark cloud phones (5-6 devices, unique IMEI/MAC per account)
  |
  +-- Webshare residential proxy (1 IP per account, country-matched)
  |     - Verified live before every post
  |     - 30-min quarantine on failure
  |
  +-- Content pipeline
  |     yt-dlp download from source channels
  |     ffmpeg: LUT color grade, speed/pitch jitter
  |     OpenAI/Gemini: caption rewrite per country
  |
  +-- Scheduler (SQLite)
  |     Slot times with 10% random jitter
  |     Prevents synchronized posting across accounts
  |     Tracks post history, slot assignments, proxy/country per phone
  |
  +-- Geelark Task API
        Posts video from inside cloud phone (in-app, organic)
        Scheduled at local timezone of each account
```

### Key Design Decisions (adapted for 5-6 accounts)

1. **One residential proxy per account** - country-matched to account SIM/region
2. **In-app posting via Geelark** - looks organic, avoids API detection
3. **Slot times with jitter** - each account has independent posting times
4. **Video uniquification** - random LUT + speed variation + AI caption per account
5. **Warmup tag system** - new accounts tagged "ngam", skipped until warmed
6. **SQLite scheduler** - lightweight, local, perfect for 5-6 accounts

### Project Structure (adapted)
```
/Users/zava/.openclaw/workspace/tiktok_fleet/
├── .env                     # API keys and proxy configs (gitignored)
├── config.yaml              # Account/proxy/schedule configuration
├── requirements.txt         # Python dependencies
├── tiktok_fleet.db          # SQLite database (auto-generated)
├── src/
│   ├── __init__.py
│   ├── auth.py              # Geelark authentication
│   ├── scheduler.py         # Post scheduling with jitter
│   ├── uploader.py          # Video upload logic (adapted from content.py)
│   ├── content.py           # Content pipeline (ffmpeg, AI captions)
│   ├── monitoring.py        # Status monitoring
│   └── dashboard.py         # Web dashboard (Flask/Streamlit)
├── data/
│   ├── accounts.json        # Account metadata (encrypted)
│   └── videos/              # Video files directory
├── logs/                    # Application logs
├── luts/                    # ffmpeg LUT color grading files
└── cached_ipinfo/           # IP geolocation cache
```

## Implementation Phases

### Phase 1: Foundation (Days 1-2)
- [ ] Set up Python project structure
- [ ] Install dependencies (geelark, webshare, openai, ffmpeg, yt-dlp)
- [ ] Configure .env with API keys
- [ ] Test single-account authentication flow
- [ ] Verify proxy connectivity per country

### Phase 2: Database & Account Registry (Days 3-4)
- [ ] Initialize SQLite schema (phones, videos, post_history tables)
- [ ] Register 5-6 Geelark cloud phone accounts
- [ ] Assign residential proxies per account (country-matched)
- [ ] Test phone/proxy pairing and IP geolocation

### Phase 3: Scheduling System (Days 5-6)
- [ ] Implement APScheduler-style interval scheduling
- [ ] Add 10% random jitter per account
- [ ] Prevent overlapping posts across accounts
- [ ] Track last post time per account
- [ ] Support Europe/Rome timezone handling

### Phase 4: Content Pipeline (Days 7-8)
- [ ] Integrate yt-dlp for video sourcing
- [ ] ffmpeg LUT color grade integration
- [ ] Random speed/pitch variation (0.95x-1.05x)
- [ ] OpenAI caption rewriting per country
- [ ] Test end-to-end video upload flow

### Phase 5: Dashboard & Monitoring (Days 9-10)
- [ ] Flask web interface
- [ ] Real-time account status
- [ ] Post history logging
- [ ] Error alerts and retry log
- [ ] Manual override capabilities

## Safety & Compliance (Critical for TikTok Automation)

⚠️ **TikTok Automation Risks & Mitigations:**

1. **Account Bans** - Use residential proxies only, never datacenter
   - Rotate IPs, 30-min quarantine on failure
   - Max 1-2 posts per account per day

2. **Geographic Mismatch** - Country IP must match account region
   - UK accounts → UK proxies, US accounts → US proxies
   - Auto-verify proxy country before every post

3. **Rate Limiting** - Implement organic cadence
   - Default interval: 8 hours between posts per account
   - +10% jitter to avoid batch synchronization
   - Warmup period: skip "ngam" tagged accounts

4. **Content Uniqueness** - Each post must be distinct
   - Random LUT from 40+ .cube files
   - Optional flip, speed variation
   - AI-rewritten caption per country

5. **Manual Backup** - Always have manual posting capability
   - System logs task IDs for manual follow-up
   - Dashboard can trigger manual posts
   - Never 100% automated without oversight

## Next Actions

### Immediate (Today):
1. **Set up Python environment** - `python3 -m venv .venv && source .venv/bin/activate`
2. **Install dependencies** - `pip install geelark requests openai yt-dlp python-dotenv ffmpeg`
3. **Create .env file** with your Geelark and Webshare API keys
4. **Clone the reference scaffold** - already done at `/tmp/tiktok-multi-account-management-geelark/`

### This Week:
1. Register 5-6 Geelark cloud phone accounts
2. Subscribe to Webshare residential proxies (minimum 5-6 IPs)
3. Set up ffmpeg LUT library (download 40+ .cube files)
4. Test single-account: `python -m src.main` with one phone

### Prototype Goal (End of Week 1):
- [ ] Successfully authenticate 1 account via Geelark
- [ ] Verify proxy country matching
- [ ] Schedule first post with jitter
- [ ] Upload and post first video
- [ ] Dashboard shows account status

## Long-term Enhancements
- AI thumbnail generation per video
- Multi-language caption translation
- Analytics integration (views, engagement per account)
- Automatic account warmup routines
- Failover/backup proxy system
- Integration with TikTok Business API (where available)

---
*Project adapted from chunhuduc/tiktok-multi-account-management-geelark (GitHub)*
*Designed for 5-6 TikTok accounts with autonomous publishing*