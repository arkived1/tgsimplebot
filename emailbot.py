import logging, random, string, requests, time, threading, io
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

BOT_TOKEN = "7995107883:AAFvH1DsxDLINPb6Wr88DgyEPTmr82MjNVU"
OWNER_ID = 7668204914
PASSWORD = "hiroprems"

user_mode = {}
mailtm_tokens = {}
mailtm_accounts = {}
create_usage = {}
create_timestamp = {}
autocheck_threads = {}

logging.basicConfig(level=logging.INFO)

def has_username(user): return bool(user.username)

def notify_owner(context: CallbackContext, text: str):
    try:
        context.bot.send_message(chat_id=OWNER_ID, text=text)
    except: pass

def show_mode_selector(update_or_query):
    keyboard = [
        [InlineKeyboardButton("👑 owner", callback_data='owner')],
        [InlineKeyboardButton("mail.tm", callback_data='mailtm'),
         InlineKeyboardButton("yopmail", callback_data='yopmail')],
        [InlineKeyboardButton("card generator", callback_data='ccgen')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if hasattr(update_or_query, "message"):
        update_or_query.message.reply_text("📥 choose a mode:", reply_markup=reply_markup)
    else:
        update_or_query.edit_message_text("📥 choose a mode:", reply_markup=reply_markup)

def start(update: Update, context: CallbackContext):
    if not has_username(update.effective_user):
        return update.message.reply_text("⛔ set a telegram username to use this bot.")
    show_mode_selector(update)

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    user = query.from_user
    uid = user.id

    if not has_username(user):
        query.answer("set a telegram username to use this bot.", show_alert=True)
        return

    if query.data == "back":
        user_mode.pop(uid, None)
        show_mode_selector(query)
        return

    if query.data == "owner":
        query.edit_message_text(
            "this bot is managed by @hiroprems\nmessage me for concerns or ideas.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("back", callback_data='back')]])
        )
        return

    user_mode[uid] = query.data
    query.answer()

    if query.data == "mailtm":
        text = (
            "you are now in mail.tm mode.\n\n"
            "commands:\n"
            "• /gen – generate a new mail.tm email\n"
            "• /inbox email – check inbox of the specified mail.tm email\n"
            "• /delete – delete a mail.tm account (reply to the prompt with email)\n"
            "• /autocheck email – monitor a mail.tm inbox for new messages\n"
            "• /stopcheck email – stop monitoring a mail.tm inbox\n"
            "• /accounts – view all mail.tm emails you’ve generated\n\n"
            "generated emails are safe and private"
        )
    elif query.data == "yopmail":
        text = (
            "you are now in yopmail mode.\n\n"
            "commands:\n"
            "• /gen domain – generate a random yopmail email\n"
            "• /inbox email – show all messages for that email\n"
            "• /inbox email keyword – check inbox filtered by keyword\n"
            "• /autocheck email – monitor a yopmail inbox for new messages\n"
            "• /stopcheck email – stop monitoring a yopmail inbox\n\n"
            "generated emails are safe and private"
        )
    elif query.data == "ccgen":
        text = (
            "you are now in card generator mode.\n\n"
            "commands:\n"
            "• /ccgen bin amount – generate cards from a bin\n"
            "• /bininfo bin – get card details\n\n"
            "generated cards or bins are safe and private"
        )

    query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("back", callback_data='back')]]))

def gen(update: Update, context: CallbackContext):
    user = update.effective_user
    uid = user.id
    username = user.username
    if not has_username(user):
        return update.message.reply_text("⛔ set a telegram username to use this bot.")
    mode = user_mode.get(uid)
    if not mode:
        return show_mode_selector(update)

    if mode == "mailtm":
        now = int(time.time())
        used = create_usage.get(uid, 0)
        last_reset = create_timestamp.get(uid, 0)
        if now - last_reset >= 3600:
            create_usage[uid] = 0
            create_timestamp[uid] = now
            used = 0
        if used >= 5:
            return update.message.reply_text("⛔ limit reached (5x per hour). try again later.")
        domain = requests.get("https://api.mail.tm/domains").json()["hydra:member"][0]["domain"]
        username_gen = ''.join(random.choices(string.ascii_lowercase, k=8))
        email = f"{username_gen}@{domain}"
        reg = requests.post("https://api.mail.tm/accounts", json={"address": email, "password": PASSWORD})
        if reg.status_code != 201:
            return update.message.reply_text("❌ failed to create mail.tm account.")
        token = requests.post("https://api.mail.tm/token", json={"address": email, "password": PASSWORD}).json().get("token")
        mailtm_tokens[uid] = {"email": email, "token": token}
        mailtm_accounts.setdefault(uid, []).append(email)
        create_usage[uid] += 1
        update.message.reply_text(f"📧 `{email}`\n🔑 password: `{PASSWORD}`", parse_mode="Markdown")
        notify_owner(context, f"📨 @{username} used /gen")
    elif mode == "yopmail":
        if not context.args:
            return update.message.reply_text("❌ example: /gen domain")
        domain_raw = context.args[0].replace("@", "")
        domain = domain_raw if "." in domain_raw else f"{domain_raw}.yopmail.com"
        email = ''.join(random.choices(string.ascii_lowercase, k=8)) + "@" + domain
        update.message.reply_text(f"📧 generated yopmail email: `{email}`", parse_mode="Markdown")
        notify_owner(context, f"📨 @{username} used /gen")
def mailtm_inbox(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    username = update.effective_user.username
    token_data = mailtm_tokens.get(uid)
    if not token_data:
        return update.message.reply_text("❗ no mail.tm session. use /gen first.")
    headers = {"Authorization": f"Bearer {token_data['token']}"}
    inbox = requests.get("https://api.mail.tm/messages", headers=headers).json().get("hydra:member", [])
    if not inbox:
        return update.message.reply_text("📭 no messages yet.")
    subjects = "\n".join([f"• {msg['subject']}" for msg in inbox])
    update.message.reply_text(f"✉️ inbox for `{token_data['email']}`:\n\n{subjects}", parse_mode="Markdown")
    notify_owner(context, f"📬 @{username} used /inbox")

def yopmail_inbox(update: Update, context: CallbackContext):
    username = update.effective_user.username
    if not context.args:
        return update.message.reply_text("❌ please specify an email.")
    email = context.args[0]
    keyword = context.args[1] if len(context.args) > 1 else None
    html = requests.get(f"https://yopmail.com/en/inbox?login={email.split('@')[0]}").text
    soup = BeautifulSoup(html, "html.parser")
    divs = soup.select("div.m")
    messages = [d.text.strip() for d in divs]
    if keyword:
        messages = [m for m in messages if keyword.lower() in m.lower()]
    if not messages:
        return update.message.reply_text("📭 no matching messages.")
    out = "\n".join([f"• {s}" for s in messages])
    update.message.reply_text(f"🎯 results for `{email}`:\n\n{out}", parse_mode="Markdown")
    notify_owner(context, f"📬 @{username} used /inbox")

def handle_inbox(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if not user_mode.get(uid):
        return show_mode_selector(update)
    if user_mode[uid] == "mailtm":
        mailtm_inbox(update, context)
    elif user_mode[uid] == "yopmail":
        yopmail_inbox(update, context)

def delete_prompt(update: Update, context: CallbackContext):
    update.message.reply_text("🗑 reply to this message with the mail.tm email you want to delete.\nwarning: this will remove your session for that email.")

def handle_reply(update: Update, context: CallbackContext):
    if not update.message.reply_to_message: return
    if "you want to delete" not in update.message.reply_to_message.text.lower(): return
    uid = update.effective_user.id
    email = update.message.text.strip()
    if email in mailtm_accounts.get(uid, []):
        mailtm_accounts[uid].remove(email)
        if mailtm_tokens.get(uid, {}).get("email") == email:
            mailtm_tokens.pop(uid)
        update.message.reply_text(f"✅ mail.tm session for {email} deleted.")
    else:
        update.message.reply_text("⚠️ no matching mail.tm account found.")

def list_accounts(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    accs = mailtm_accounts.get(uid)
    if not accs:
        return update.message.reply_text("📭 you haven’t created any mail.tm accounts yet.")
    rows = "\n".join([f"{i+1}. {e}" for i, e in enumerate(accs)])
    update.message.reply_text(f"📂 your mail.tm accounts:\n{rows}\n\n🔑 password: {PASSWORD}")

def autocheck(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if not context.args:
        return update.message.reply_text("❌ please specify an email.")
    email = context.args[0]
    mode = user_mode.get(uid)
    if mode == "mailtm":
        token = mailtm_tokens.get(uid, {}).get("token")
        if not token or mailtm_tokens.get(uid, {}).get("email") != email:
            return update.message.reply_text("⚠️ not your generated mail.tm email.")
        def check_loop():
            last = None
            while autocheck_threads.get(email):
                headers = {"Authorization": f"Bearer {token}"}
                inbox = requests.get("https://api.mail.tm/messages", headers=headers).json().get("hydra:member", [])
                if inbox and inbox[0]["id"] != last:
                    last = inbox[0]["id"]
                    update.message.reply_text(f"📥 new mail in `{email}`:\n{inbox[0]['subject']}", parse_mode="Markdown")
                time.sleep(60)
        autocheck_threads[email] = True
        threading.Thread(target=check_loop).start()
        update.message.reply_text(f"🔄 now checking `{email}` every minute.", parse_mode="Markdown")
    elif mode == "yopmail":
        def check_loop_yop():
            last = None
            while autocheck_threads.get(email):
                html = requests.get(f"https://yopmail.com/en/inbox?login={email.split('@')[0]}").text
                soup = BeautifulSoup(html, "html.parser")
                divs = soup.select("div.m")
                if divs:
                    subject = divs[0].text.strip()
                    if subject != last:
                        last = subject
                        update.message.reply_text(f"📥 new mail in `{email}`:\n{subject}", parse_mode="Markdown")
                time.sleep(60)
        autocheck_threads[email] = True
        threading.Thread(target=check_loop_yop).start()
        update.message.reply_text(f"🔄 now checking `{email}` every minute.", parse_mode="Markdown")

def stopcheck(update: Update, context: CallbackContext):
    if not context.args:
        return update.message.reply_text("❌ please specify an email.")
    email = context.args[0]
    autocheck_threads[email] = False
    update.message.reply_text(f"🛑 stopped checking `{email}`.", parse_mode="Markdown")
def ccgen_handler(update: Update, context: CallbackContext):
    user = update.effective_user
    uid = user.id
    username = user.username or "unknown"

    if user_mode.get(uid) != "ccgen":
        return show_mode_selector(update)

    if not context.args or len(context.args) < 1:
        return update.message.reply_text("❌ example: /ccgen bin amount")

    bin_prefix = context.args[0]
    try:
        amount = int(context.args[1]) if len(context.args) > 1 else 10
        if amount <= 0 or amount > 1000:
            return update.message.reply_text("⚠️ amount must be between 1 and 1000")
    except ValueError:
        return update.message.reply_text("❌ invalid amount")

    url = f"https://lookup.binlist.net/{bin_prefix}"
    headers = {"Accept-Version": "3"}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            brand = data.get("scheme", "unknown").title()
            type_ = data.get("type", "unknown")
            country = data.get("country", {}).get("name", "unknown")
            bank = data.get("bank", {}).get("name", "unknown")
            brand_name = data.get("brand", "").title()
            bin_info = (
                f"🔎 BIN {bin_prefix}\n"
                f"• Country: {country}\n"
                f"• Type: {type_}\n"
                f"• Brand: {brand_name or brand}\n"
                f"• Bank: {bank}\n\n"
            )
        else:
            bin_info = f"🔎 BIN {bin_prefix}\n• info not found\n\n"
    except Exception:
        bin_info = f"🔎 BIN {bin_prefix}\n• failed to fetch info\n\n"

    now = time.localtime()
    current_year = now.tm_year
    current_month = now.tm_mon

    def generate_valid_expiry():
        while True:
            mm = f"{random.randint(1, 12):02d}"
            yy = random.randint(current_year, current_year + 4)
            if yy == current_year and int(mm) < current_month + 1:
                continue
            return mm, str(yy)

    cards = []
    for _ in range(amount):
        cc = bin_prefix + ''.join(random.choices(string.digits, k=16 - len(bin_prefix)))
        mm, yy = generate_valid_expiry()
        cvv = f"{random.randint(100, 999)}"
        cards.append(f"{cc}|{mm}|{yy}|{cvv}")

    result = "\n".join(cards)
    full_output = bin_info + "💳 generated cards:\n\n" + result

    if amount > 11:
        file = io.BytesIO(full_output.encode())
        file.name = "ccgen_result.txt"
        update.message.reply_document(InputFile(file))
    else:
        update.message.reply_text(full_output)

    notify_owner(context, f"💳 @{username} used /ccgen")

def bininfo(update: Update, context: CallbackContext):
    if not context.args:
        return update.message.reply_text("❌ example: /bininfo 489504")
    bin_number = context.args[0]
    url = f"https://lookup.binlist.net/{bin_number}"
    headers = {"Accept-Version": "3"}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            return update.message.reply_text("❌ bin not found or invalid.")
        data = res.json()
        brand = data.get("scheme", "unknown").title()
        type_ = data.get("type", "unknown")
        country = data.get("country", {}).get("name", "unknown")
        bank = data.get("bank", {}).get("name", "unknown")
        brand_name = data.get("brand", "").title()
        msg = (
            f"🔎 BIN {bin_number}\n"
            f"• Country: {country}\n"
            f"• Type: {type_}\n"
            f"• Brand: {brand_name or brand}\n"
            f"• Bank: {bank}"
        )
        update.message.reply_text(msg)
    except Exception:
        update.message.reply_text("⚠️ failed to fetch BIN info.")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(CommandHandler("gen", gen))
    dp.add_handler(CommandHandler("inbox", handle_inbox))
    dp.add_handler(CommandHandler("delete", delete_prompt))
    dp.add_handler(CommandHandler("accounts", list_accounts))
    dp.add_handler(CommandHandler("autocheck", autocheck))
    dp.add_handler(CommandHandler("stopcheck", stopcheck))
    dp.add_handler(CommandHandler("ccgen", ccgen_handler))
    dp.add_handler(CommandHandler("bininfo", bininfo))
    dp.add_handler(MessageHandler(Filters.reply, handle_reply))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

