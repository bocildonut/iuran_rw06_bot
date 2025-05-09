import os
import gspread
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials

from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)

# ======= GOOGLE SHEETS SETUP =======
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
client = gspread.authorize(CREDS)

# ======= CONVERSATION STATE =======
ALAMAT, HP = range(2)

# ======= LOGGING FUNCTION =======
def log_to_google_sheets(alamat, telegram_id):
    try:
        log_sheet = client.open("tagihan_rw06").worksheet("logs")
    except gspread.exceptions.WorksheetNotFound:
        log_sheet = client.open("tagihan_rw06").add_worksheet(title="logs", rows="100", cols="3")
        log_sheet.append_row(["Alamat", "Telegram ID", "Tanggal & Jam"])

    current_time = datetime.now() + timedelta(hours=7)
    current_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    log_sheet.append_row([alamat, str(telegram_id), current_time])

# ======= TELEGRAM HANDLERS =======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Ketik /cek untuk melihat tagihan iuran RW Anda.")

async def start_cek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📍 Masukkan Kode Alamat Anda (contoh: A-1):")
    return ALAMAT

async def input_alamat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['alamat'] = update.message.text.strip().upper()
    await update.message.reply_text("🔢 Masukkan 4 digit terakhir nomor HP Anda:")
    return HP

async def input_hp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hp_akhir = update.message.text.strip()
    alamat = context.user_data.get('alamat')
    telegram_id = update.message.from_user.id

    sheet = client.open("tagihan_rw06").worksheet("data_tagihan")
    data = sheet.get_all_records()

    for row in data:
        if row['Alamat'].strip().upper() == alamat:
            nohp_full = str(row.get('telp', '')).strip()
            nohp_last4 = nohp_full[-4:]
            if nohp_last4 == hp_akhir:
                msg = (
                    f"✅ <b>Data Tagihan Iuran Warga RW 06</b>\n"
                    f"✅ <b>Kel. Bulusan, Kec. Tembalang, Kota Semarang</b>\n\n"
                    f"👤 Nama : <b>{row['Nama']}</b>\n"
                    f"🏠 Alamat : {row['Alamat']}\n"
                    f"🏷️ RT : {row['RT']}\n"
                    f"💎 Golongan : {row['Golongan']}\n"
                    f"📅 Bulan : {row['bulan']}\n"
                    f"💰 Tagihan : <b>{row['Tagihan']}</b>\n\n"
                    f"Pembayaran dianggap SAH, bila melalui TRANSFER / QRIS\n"
                    f"No. Rekening Bank JATENG  2034 391 508 an. KAS GTR RW 06"
                )
                log_to_google_sheets(alamat, telegram_id)
                await update.message.reply_text(msg, parse_mode="HTML")
                return ConversationHandler.END
            else:
                await update.message.reply_text("❌ Nomor HP tidak cocok.")
                return ConversationHandler.END

    await update.message.reply_text("❌ Alamat tidak ditemukan.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Proses dibatalkan.")
    return ConversationHandler.END

# ======= MAIN BOT RUNNER =======
async def set_bot_commands(app):
    commands = [
        BotCommand("start", "Mulai bot"),
        BotCommand("cek", "Cek tagihan iuran RW Anda"),
        BotCommand("cancel", "Batalkan proses"),
    ]
    await app.bot.set_my_commands(commands)

def run_bot():
    BOT_TOKEN = os.getenv("BOT_TOKEN")  # atau langsung string
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("cek", start_cek)],
        states={
            ALAMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_alamat)],
            HP: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_hp)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)

    app.post_init = set_bot_commands
    app.run_polling()

if __name__ == '__main__':
    run_bot()
