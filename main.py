import gspread
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from aiohttp import web
import os

# ======= GOOGLE SHEETS SETUP =======
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
client = gspread.authorize(CREDS)

# ======= CONVERSATION STATE =======
ALAMAT = 0

# ======= LOGGING FUNCTION =======
def log_to_google_sheets(alamat, telegram_id):
    try:
        log_sheet = client.open("tagihan_rw06").worksheet("logs")
    except gspread.exceptions.WorksheetNotFound:
        log_sheet = client.open("tagihan_rw06").add_worksheet(title="logs", rows="100", cols="3")
        log_sheet.append_row(["Alamat", "Telegram ID", "Tanggal & Jam"])

    current_time = datetime.now() + timedelta(hours=7)
    log_sheet.append_row([alamat, str(telegram_id), current_time.strftime("%Y-%m-%d %H:%M:%S")])

# ======= HANDLERS =======
async def start_cek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📍 Masukkan Kode Alamat Anda (contoh: A-1):")
    return ALAMAT

async def input_alamat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alamat = update.message.text.strip().upper()
    context.user_data['alamat'] = alamat
    telegram_id = update.effective_user.id
    log_to_google_sheets(alamat, telegram_id)
    await update.message.reply_text(f"✅ Kode Alamat *{alamat}* sudah dicatat.\n\nKetik /cek untuk cek ulang atau /cancel untuk membatalkan.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Proses dibatalkan. Ketik /cek untuk mulai lagi.")
    return ConversationHandler.END

# ======= AIOHTTP HANDLER UNTUK WEBHOOK =======
async def webhook_handler(request):
    data = await request.json()
    update = Update.de_json(data, app.bot)
    await app.update_queue.put(update)
    return web.Response(text="OK")

# ======= MAIN FUNCTION =======
async def main():
    global app
    TOKEN = os.environ["BOT_TOKEN"]
    WEBHOOK_URL = os.environ["WEBHOOK_URL"]

    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("cek", start_cek)],
        states={ ALAMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_alamat)] },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("cancel", cancel))

    # Set webhook
    await app.bot.set_webhook(WEBHOOK_URL)

    # Jalankan web server untuk terima webhook
    web_app = web.Application()
    web_app.router.add_post("/", webhook_handler)
    runner = web.AppRunner(web_app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    print(f"Listening on port {port}...")
    await site.start()

    await app.run_webhook(stop_signals=None)  # Jangan tutup otomatis

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
