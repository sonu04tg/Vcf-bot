import json
import os
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ================= CONFIG =================

TOKEN = "8590482605:AAHBNwosaLK0rOae2GvydOpldiQJqIKIiS8"
ADMIN_ID = 7888066934

SUPPORT_ID = "@Rule_Breakerz"

UPI_ID = "swatireceiver@fam"
BINANCE_ID = "915935365"

UPI_QR = "https://t.me/sourcephotos1/13"
BINANCE_QR = "https://t.me/sourcephotos1/7"

# ================= FILES =================

USERS_FILE = "users.json"
STEPS_FILE = "steps.json"

# ================= JSON =================

def load_json(file, default):
    if not os.path.exists(file):
        return default
    with open(file) as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    users = load_json(USERS_FILE, [])

    if user.id not in users:
        users.append(user.id)
        save_json(USERS_FILE, users)

    keyboard = [
        [KeyboardButton("🇮🇳 UPI Deposit"), KeyboardButton("🟡 Binance Deposit")],
        [KeyboardButton("🌐 Crypto Deposit")],
        [KeyboardButton("🆘 Help & Support")]
    ]

    text = """
<b>💳 PAYMENT RECEIVER BOT</b>

<b>Select your preferred payment method below.</b>

<b>Fast • Secure • Reliable 🚀</b>
"""

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ================= HELP =================

async def help_support(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = f"""
<b>🆘 HELP & SUPPORT</b>

<b>If you also want a bot like this, contact:</b>

<b>👉 {SUPPORT_ID}</b>

<b>We provide custom Telegram bots with premium UI 🚀</b>
"""

    await update.message.reply_text(text, parse_mode="HTML")

# ================= PAYMENT =================

async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = str(update.effective_user.id)
    text = update.message.text
    steps = load_json(STEPS_FILE, {})

    # UPI
    if text == "🇮🇳 UPI Deposit":

        msg = f"""
<b>🇮🇳 UPI DEPOSIT</b>

<b>UPI ID:</b>
<code>{UPI_ID}</code>

<b>Scan QR or copy UPI ID above.</b>

<b>Then send Transaction ID.</b>
"""

        await update.message.reply_photo(
            UPI_QR,
            caption=msg,
            parse_mode="HTML"
        )

        steps[user_id] = {"step": "txn", "method": "UPI"}
        save_json(STEPS_FILE, steps)

    # BINANCE
    elif text == "🟡 Binance Deposit":

        msg = f"""
<b>🟡 BINANCE DEPOSIT</b>

<b>Binance ID:</b>
<code>{BINANCE_ID}</code>

<b>Send payment and send Transaction ID.</b>
"""

        await update.message.reply_photo(
            BINANCE_QR,
            caption=msg,
            parse_mode="HTML"
        )

        steps[user_id] = {"step": "txn", "method": "BINANCE"}
        save_json(STEPS_FILE, steps)

    # CRYPTO
    elif text == "🌐 Crypto Deposit":

        msg = """
<b>🌐 CRYPTO DEPOSIT</b>

<b>Available Networks:</b>

<b>USDT (BEP20)</b>
<code>0x60deFd9Cffed1F181AeC547D64B360E9A86A0876</code>

<b>USDT (TRC20)</b>
<code>TPfyQV5mKu4dPasSPnyv5ikd4jvhC4qdiZ</code>

<b>USDT (Polygon)</b>
<code>0x964F57152b11b40f9A83C56b3AB65ec8729210AD</code>

<b>Send Transaction ID after payment.</b>
"""

        await update.message.reply_text(msg, parse_mode="HTML")

        steps[user_id] = {"step": "txn", "method": "CRYPTO"}
        save_json(STEPS_FILE, steps)

# ================= TXN =================

async def txn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = str(update.effective_user.id)
    steps = load_json(STEPS_FILE, {})

    if user_id in steps and steps[user_id]["step"] == "txn":

        steps[user_id]["txn"] = update.message.text
        steps[user_id]["step"] = "photo"

        save_json(STEPS_FILE, steps)

        await update.message.reply_text(
            "<b>📸 Send Payment Screenshot now.</b>",
            parse_mode="HTML"
        )

# ================= SCREENSHOT =================

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    user_id = str(user.id)

    steps = load_json(STEPS_FILE, {})

    if user_id not in steps:
        return

    if steps[user_id]["step"] != "photo":
        return

    txn = steps[user_id]["txn"]
    method = steps[user_id]["method"]

    photo = update.message.photo[-1].file_id

    caption = f"""
<b>🚨 NEW PAYMENT REQUEST</b>

<b>User:</b> {user.first_name}
<b>User ID:</b> <code>{user.id}</code>

<b>Method:</b> {method}
<b>Transaction ID:</b>
<code>{txn}</code>
"""

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve|{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject|{user.id}")
        ]
    ])

    await context.bot.send_photo(
        ADMIN_ID,
        photo,
        caption=caption,
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await update.message.reply_text(
        f"""
<b>✅ Payment proof received!</b>

<b>Please also send screenshot to support:</b>
{SUPPORT_ID}

<b>For faster approval 🥰🚀</b>
""",
        parse_mode="HTML"
    )

    del steps[user_id]
    save_json(STEPS_FILE, steps)

# ================= APPROVE / REJECT =================

async def decision_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split("|")

    if action == "approve":

        text = """
<b>✅ PAYMENT APPROVED</b>

<b>Your payment has been verified successfully.</b>

<b>Thank you! 🚀</b>
"""

    else:

        text = f"""
<b>❌ PAYMENT REJECTED</b>

<b>Please contact support:</b>
{SUPPORT_ID}
"""

    await context.bot.send_message(
        int(user_id),
        text,
        parse_mode="HTML"
    )

    await query.edit_message_caption(
        query.message.caption + f"\n\n<b>{action.upper()} ✅</b>",
        parse_mode="HTML"
    )

# ================= ADMIN =================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    users = load_json(USERS_FILE, [])

    keyboard = [
        [KeyboardButton("📊 Stats")],
        [KeyboardButton("📢 Broadcast")]
    ]

    await update.message.reply_text(
        f"<b>Admin Panel</b>\n\n<b>Total Users:</b> {len(users)}",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ================= STATS =================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    users = load_json(USERS_FILE, [])

    await update.message.reply_text(
        f"<b>Total Users:</b> {len(users)}",
        parse_mode="HTML"
    )

# ================= BROADCAST =================

broadcast_mode = set()

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    broadcast_mode.add(update.effective_user.id)

    await update.message.reply_text("<b>Send message to broadcast</b>", parse_mode="HTML")

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id not in broadcast_mode:
        return

    users = load_json(USERS_FILE, [])

    for user in users:
        try:
            await context.bot.send_message(user, update.message.text, parse_mode="HTML")
        except:
            pass

    broadcast_mode.remove(update.effective_user.id)

    await update.message.reply_text("<b>Broadcast sent successfully ✅</b>", parse_mode="HTML")

# ================= MAIN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin))

app.add_handler(MessageHandler(filters.Regex("Help"), help_support))
app.add_handler(MessageHandler(filters.Regex("Deposit"), payment_handler))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, txn_handler))
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

app.add_handler(CallbackQueryHandler(decision_handler))

app.add_handler(MessageHandler(filters.Regex("Stats"), stats))
app.add_handler(MessageHandler(filters.Regex("Broadcast"), broadcast))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send))

print("Bot running...")
app.run_polling()