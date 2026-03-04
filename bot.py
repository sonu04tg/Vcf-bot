import telebot
import sqlite3
import re
import os
import time
from io import BytesIO
from datetime import datetime, timedelta
from telebot import types
import pandas as pd

# ================= CONFIGURATION =================
TOKEN = "8377450293:AAFPc9FY9_Tc_0a8q2K7obGc7UQICNcFrK8"  # Apna Token Yahan Dalein
MAIN_ADMIN_ID = 7888066934   # Aapki Admin ID
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ================= DATABASE SETUP =================
def init_db():
    conn = sqlite3.connect('rulebreakerz_pro_max.db', check_same_thread=False)
    c = conn.cursor()
    # Note: caption_pref default is now 'OFF'
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, sub_type TEXT, sub_start TEXT, sub_end TEXT, is_admin INTEGER DEFAULT 0, caption_pref TEXT DEFAULT 'OFF')''')
    c.execute('''CREATE TABLE IF NOT EXISTS channels (username TEXT PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Defaults
    c.execute("INSERT OR IGNORE INTO settings VALUES ('bot_status', 'ON')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('auto_plus', 'ON')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('total_vcf', '0')")
    
    # Register Main Admin
    c.execute("INSERT OR IGNORE INTO users (id, sub_type, sub_start, sub_end, is_admin, caption_pref) VALUES (?, 'Admin', ?, 'Permanent', 1, 'ON')", 
              (MAIN_ADMIN_ID, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    return conn

db = init_db()
user_data = {}

# ================= DATABASE HELPERS =================
def is_admin(uid):
    if uid == MAIN_ADMIN_ID: return True
    c = db.cursor()
    res = c.execute("SELECT is_admin FROM users WHERE id=?", (uid,)).fetchone()
    return True if res and res[0] == 1 else False

def check_sub(uid):
    if is_admin(uid): return True
    c = db.cursor()
    res = c.execute("SELECT sub_type, sub_end FROM users WHERE id=?", (uid,)).fetchone()
    if not res: return False
    if res[0] in ['Permanent', 'Admin']: return True
    try:
        expiry = datetime.strptime(res[1], '%Y-%m-%d %H:%M:%S')
        return expiry > datetime.now()
    except: return False

def check_force_join(uid):
    if is_admin(uid): return True
    c = db.cursor()
    for ch in c.execute("SELECT username FROM channels").fetchall():
        try:
            if bot.get_chat_member(ch[0], uid).status in ['left', 'kicked']: return False
        except: continue
    return True

def get_join_kb():
    c = db.cursor()
    kb = types.InlineKeyboardMarkup()
    for ch in c.execute("SELECT username FROM channels").fetchall():
        kb.add(types.InlineKeyboardButton(f"Join {ch[0]}", url=f"https://t.me/{ch[0].replace('@','')}"))
    kb.add(types.InlineKeyboardButton("🔄 Verify Joined", callback_data="verify_join"))
    return kb

def extract_numbers(text):
    return re.findall(r'\b\d{7,15}\b', text)

def increment_vcf_count():
    c = db.cursor()
    c.execute("UPDATE settings SET value = CAST(value AS INTEGER) + 1 WHERE key='total_vcf'")
    db.commit()

def get_caption_pref(uid):
    c = db.cursor()
    res = c.execute("SELECT caption_pref FROM users WHERE id=?", (uid,)).fetchone()
    return res[0] if res else 'OFF'

def is_auto_plus_on():
    c = db.cursor()
    return c.execute("SELECT value FROM settings WHERE key='auto_plus'").fetchone()[0] == 'ON'

# ================= MIDDLEWARE =================
def access_required(func):
    def wrapper(message):
        uid = message.from_user.id
        c = db.cursor()
        
        if c.execute("SELECT value FROM settings WHERE key='bot_status'").fetchone()[0] == 'OFF' and not is_admin(uid):
            return bot.send_message(uid, "❌ <b>Bot is currently OFF for maintenance.</b>")
        
        if not check_force_join(uid):
            return bot.send_message(uid, "⚠️ <b>Join our official channels to use the bot!</b>", reply_markup=get_join_kb())
        
        if not check_sub(uid):
            text = (
                "🚫 <b>Subscription Expired or Not Found!</b>\n\n"
                "You cannot use any bot services right now.\n\n"
                "🛒 <b>Please buy a subscription from Admin:</b>\n"
                "👉 @Rule_Breakerz"
            )
            return bot.send_message(uid, text)
        
        return func(message)
    return wrapper

# ================= KEYBOARDS =================
def main_menu():
    kb = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.add("📁 Text to VCF", "📄 VCF to Text")
    kb.add("⚓ Admin/Navy VCF", "🔄 Merge VCF")
    kb.add("✏️ VCF Editor", "🆔 Get Name")
    kb.add("💳 My Subscription")
    return kb

# ================= COMMANDS =================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    uid = message.from_user.id
    c = db.cursor()
    user = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    
    # 24H FREE TRIAL LOGIC (Caption defaults to OFF)
    if not user:
        now = datetime.now()
        expiry = now + timedelta(days=1)
        c.execute("INSERT INTO users (id, sub_type, sub_start, sub_end, caption_pref) VALUES (?, 'Trial', ?, ?, 'OFF')", 
                  (uid, now.strftime('%Y-%m-%d %H:%M:%S'), expiry.strftime('%Y-%m-%d %H:%M:%S')))
        db.commit()
        bot.send_message(uid, "🎉 <b>Welcome! You got a 24-Hour Free Trial!</b>\nEnjoy premium features for 1 day. 🚀")

    user_data[uid] = {'state': 'IDLE'}
    welcome = (
        "🔥 <b>WELCOME TO VCF TOOL BOT</b> 🔥\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Advanced VCF Management Tool.\n"
        "Owner: <b>@Rule_Breakerz</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Select a service from the menu below:</i>"
    )
    bot.send_message(uid, welcome, reply_markup=main_menu())

@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    uid = message.from_user.id
    if not is_admin(uid): 
        return bot.send_message(uid, "❌ <b>You are not an Admin!</b>")
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("➕ Add Sub", callback_data="adm_sub_add"),
           types.InlineKeyboardButton("➖ Rem Sub", callback_data="adm_sub_rem"))
    kb.add(types.InlineKeyboardButton("➕ Add Admin", callback_data="adm_add_admin"),
           types.InlineKeyboardButton("➖ Rem Admin", callback_data="adm_rem_admin"))
    kb.add(types.InlineKeyboardButton("➕ Add Channel", callback_data="adm_ch_add"),
           types.InlineKeyboardButton("➖ Rem Channel", callback_data="adm_ch_rem"))
    kb.add(types.InlineKeyboardButton("📢 Broadcast", callback_data="adm_bc"),
           types.InlineKeyboardButton("📊 Statistics", callback_data="adm_stats"))
    kb.add(types.InlineKeyboardButton("⚙️ Bot Power ON/OFF", callback_data="adm_power"),
           types.InlineKeyboardButton("➕ Auto Plus (+)", callback_data="adm_autoplus"))
    
    bot.send_message(uid, "🛠 <b>RULE BREAKERZ ADMIN PANEL</b>\n━━━━━━━━━━━━━━━━━━━━━━", reply_markup=kb)

@bot.message_handler(commands=['caption'])
@access_required
def caption_cmd(message):
    uid = message.from_user.id
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Yes", callback_data="cap_yes"),
           types.InlineKeyboardButton("❌ No", callback_data="cap_no"))
    
    try:
        # Copies the exact message (photo + its original caption) from the channel
        bot.copy_message(chat_id=uid, from_chat_id="@sourcephotos1", message_id=14)
    except:
        bot.send_message(uid, "⚠️ Could not load preview photo from channel, but you can still select your preference below.")

    bot.send_message(uid, "📸 <b>Do you want a caption like the above on your VCF files?</b>\n\nChoose your preference:", reply_markup=kb)

# ================= SERVICE ROUTERS =================
@bot.message_handler(func=lambda m: m.text in ["📁 Text to VCF", "📄 VCF to Text", "🔄 Merge VCF", "✏️ VCF Editor", "⚓ Admin/Navy VCF"])
@access_required
def service_router(message):
    uid = message.chat.id
    txt = message.text
    
    if txt == "📁 Text to VCF":
        user_data[uid] = {'state': 'COLLECT_T2V', 'nums': [], 'count': 0}
        bot.send_message(uid, "📂 <b>Send numbers or upload .txt/.xlsx files.</b>\nType <code>/done</code> when finished.")
    elif txt == "📄 VCF to Text":
        user_data[uid] = {'state': 'COLLECT_V2T', 'nums': [], 'count': 0}
        bot.send_message(uid, "📤 <b>Upload VCF file(s).</b>\nType <code>/done</code> when finished.")
    elif txt == "🔄 Merge VCF":
        user_data[uid] = {'state': 'COLLECT_MERGE', 'vcf_data': "", 'vcf_count': 0}
        bot.send_message(uid, "📤 <b>Upload VCF files to merge.</b>\nType <code>/done</code> when finished.")
    elif txt == "✏️ VCF Editor":
        user_data[uid] = {'state': 'COLLECT_EDIT', 'nums': [], 'count': 0}
        bot.send_message(uid, "📤 <b>Upload VCF file(s) to edit.</b>\nType <code>/done</code> when finished.")
    elif txt == "⚓ Admin/Navy VCF":
        user_data[uid] = {'state': 'COLLECT_NAVY_ADM', 'adm_nums': [], 'nav_nums': [], 'count': 0}
        bot.send_message(uid, "👑 <b>Step 1: Send ADMIN numbers/files</b>\n(Type <code>skip</code> to skip, or <code>/done</code> when finished):")

@bot.message_handler(func=lambda m: m.text == "🆔 Get Name")
@access_required
def get_contact_names(message):
    user_data[message.chat.id] = {'state': 'WAIT_VCF_NAME'}
    bot.send_message(message.chat.id, "📤 <b>Upload a VCF file to see its details:</b>")

@bot.message_handler(func=lambda m: m.text == "💳 My Subscription")
def my_sub(message):
    c = db.cursor()
    res = c.execute("SELECT sub_type, sub_start, sub_end, is_admin FROM users WHERE id=?", (message.from_user.id,)).fetchone()
    if not res: return bot.send_message(message.chat.id, "No data found.")
    
    role = "👑 Admin" if res[3] == 1 else "👤 User"
    msg = (f"💳 <b>YOUR SUBSCRIPTION</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n"
           f"🏷 <b>Role:</b> <code>{role}</code>\n"
           f"🌟 <b>Plan:</b> <code>{res[0]}</code>\n"
           f"📅 <b>Start:</b> <code>{res[1]}</code>\n"
           f"⏳ <b>Expiry:</b> <code>{res[2]}</code>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"<i>🛒 Buy/Renew from @Rule_Breakerz</i>")
    bot.send_message(message.chat.id, msg)

# ================= UNIVERSAL STATE HANDLER (ANTI-SPAM) =================
@bot.message_handler(content_types=['text', 'document'])
def universal_handler(message):
    uid = message.chat.id
    if uid not in user_data: return
    state = user_data[uid].get('state', 'IDLE')
    txt = message.text.strip() if message.text else ""

    if txt.lower() == '/cancel':
        user_data[uid] = {'state': 'IDLE'}
        return bot.send_message(uid, "❌ <b>Operation Cancelled.</b>")

    # ---- Extract File/Text Data ----
    extracted = []
    file_content = b""
    is_vcf = False
    file_name_uploaded = "Unknown"
    
    if message.document:
        try:
            file_name_uploaded = message.document.file_name
            file_info = bot.get_file(message.document.file_id)
            file_content = bot.download_file(file_info.file_path)
            if file_name_uploaded.endswith('.xlsx'):
                df = pd.read_excel(BytesIO(file_content))
                extracted = extract_numbers(" ".join(df.astype(str).values.flatten()))
            else:
                extracted = extract_numbers(file_content.decode('utf-8', errors='ignore'))
            if file_name_uploaded.endswith('.vcf'): is_vcf = True
        except: bot.send_message(uid, "❌ Error reading file.")
    elif txt and txt.lower() not in ['/done', 'skip']:
        extracted = extract_numbers(txt)

    # ---- COLLECTION LOGIC WITH ANTI-SPAM (THROTTLE) ----
    now = time.time()
    
    def send_throttled_msg(text_msg):
        # Only send a status message if 1.5 seconds have passed since the last one.
        if now - user_data[uid].get('last_update', 0) > 1.5:
            # Try to delete the old message
            if 'last_msg_id' in user_data[uid]:
                try: bot.delete_message(uid, user_data[uid]['last_msg_id'])
                except: pass
            
            # Send the new message
            try:
                msg = bot.send_message(uid, text_msg)
                user_data[uid]['last_msg_id'] = msg.message_id
                user_data[uid]['last_update'] = now
            except: pass

    if state == 'COLLECT_T2V':
        if txt.lower() == '/done':
            if not user_data[uid]['nums']: return bot.send_message(uid, "❌ No contacts collected.")
            user_data[uid]['state'] = 'T2V_STEP_1'
            return bot.send_message(uid, "1️⃣ <b>VCF File Name?</b>\n(Example: <code>Brazil</code>)")
        user_data[uid]['nums'].extend(extracted)
        send_throttled_msg(f"📥 Added <code>{len(user_data[uid]['nums'])}</code> contacts so far.\nSend more or type <code>/done</code>")

    elif state == 'COLLECT_V2T':
        if txt.lower() == '/done':
            user_data[uid]['state'] = 'V2T_NAME'
            return bot.send_message(uid, "📝 <b>Enter the name for your .txt file:</b>\n(Example: <code>ExtractedList</code>)")
        user_data[uid]['nums'].extend(extracted)
        send_throttled_msg(f"📥 Extracted <code>{len(user_data[uid]['nums'])}</code> numbers so far.\nSend more VCFs or type <code>/done</code>")

    elif state == 'COLLECT_MERGE':

        if txt.lower() == '/done':
            if user_data[uid]['vcf_count'] == 0:
                return bot.send_message(uid, "❌ No VCF files uploaded.")

            user_data[uid]['state'] = 'MERGE_NAME'
            return bot.send_message(uid, "📝 <b>Enter the name for merged .vcf file:</b>")

        if is_vcf:
            user_data[uid]['vcf_data'] += file_content.decode('utf-8', errors='ignore') + "\n"
            user_data[uid]['vcf_count'] += 1

            progress_text = (
                "🔄 <b>Merging VCF Files...</b>\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"📂 <b>Uploaded:</b> <code>{user_data[uid]['vcf_count']}</code> files\n\n"
                "Send more VCFs or type <code>/done</code>"
            )

            if 'merge_msg_id' not in user_data[uid]:
                msg = bot.send_message(uid, progress_text)
                user_data[uid]['merge_msg_id'] = msg.message_id
            else:
                try:
                    bot.edit_message_text(
                        progress_text,
                        uid,
                        user_data[uid]['merge_msg_id']
                    )
                except:
                    pass

    elif state == 'COLLECT_EDIT':
        if txt.lower() == '/done':
            user_data[uid]['state'] = 'EDIT_PREFIX'
            return bot.send_message(uid, "🆔 <b>Enter New Contact Name Prefix:</b>\n(Example: <code>Rule Test</code>)")
        user_data[uid]['nums'].extend(extracted)
        send_throttled_msg(f"📥 Extracted <code>{len(user_data[uid]['nums'])}</code> numbers so far.\nSend more VCFs or type <code>/done</code>")

    elif state == 'COLLECT_NAVY_ADM':
        if txt.lower() in ['/done', 'skip']:
            user_data[uid]['state'] = 'COLLECT_NAVY_NAV'
            return bot.send_message(uid, "⚓ <b>Step 2: Send NAVY numbers/files</b>\n(Type <code>skip</code> or <code>/done</code>):")
        user_data[uid]['adm_nums'].extend(extracted)
        send_throttled_msg(f"📥 Admin Added: <code>{len(user_data[uid]['adm_nums'])}</code>.\nSend more, skip, or <code>/done</code>")

    elif state == 'COLLECT_NAVY_NAV':
        if txt.lower() in ['/done', 'skip']:
            user_data[uid]['state'] = 'NAVY_ADM_PREF'
            return bot.send_message(uid, "🖋 <b>Step 3: Admin Name Prefix?</b>\n(Example: <code>Admin Test</code>)")
        user_data[uid]['nav_nums'].extend(extracted)
        send_throttled_msg(f"📥 Navy Added: <code>{len(user_data[uid]['nav_nums'])}</code>.\nSend more, skip, or <code>/done</code>")

    # ---- TEXT TO VCF (5 STEPS) ----
    elif state == 'T2V_STEP_1':
        user_data[uid]['vname'] = txt
        user_data[uid]['state'] = 'T2V_STEP_2'
        bot.send_message(uid, "2️⃣ <b>Contact Name Prefix?</b>\n(Example: <code>Rule Test</code>)")
    elif state == 'T2V_STEP_2':
        user_data[uid]['prefix'] = txt
        user_data[uid]['state'] = 'T2V_STEP_3'
        bot.send_message(uid, "3️⃣ <b>VCF File Starting Number?</b>\n(Example: <code>1</code>)")
    elif state == 'T2V_STEP_3':
        user_data[uid]['vstart'] = int(txt) if txt.isdigit() else 1
        user_data[uid]['state'] = 'T2V_STEP_4'
        bot.send_message(uid, "4️⃣ <b>Contact Starting Number?</b>\n(Example: <code>1</code>)")
    elif state == 'T2V_STEP_4':
        user_data[uid]['cstart'] = int(txt) if txt.isdigit() else 1
        user_data[uid]['state'] = 'T2V_STEP_5'
        bot.send_message(uid, "5️⃣ <b>Contacts per VCF file?</b>\n(Example: <code>50</code>)")
    elif state == 'T2V_STEP_5':
        limit = int(txt) if txt.isdigit() else 50
        d = user_data[uid]
        nums = list(dict.fromkeys(d['nums']))
        v_idx, c_idx = d['vstart'], d['cstart']
        
        caption_on = get_caption_pref(uid) == 'ON'
        auto_plus = is_auto_plus_on()
        
        bot.send_message(uid, f"🚀 <b>Generating {len(nums)} contacts...</b>")
        for i in range(0, len(nums), limit):
            chunk = nums[i:i + limit]
            fname = f"{d['vname']}{v_idx}.vcf"
            vcf_str = ""
            for n in chunk:
                phone = n if n.startswith('+') else f"+{n}" if auto_plus else n
                vcf_str += f"BEGIN:VCARD\nVERSION:3.0\nFN:{d['prefix']} {c_idx}\nTEL;TYPE=CELL:{phone}\nEND:VCARD\n"
                c_idx += 1
            
            bio = BytesIO(vcf_str.encode('utf-8'))
            bio.name = fname
            caption = f"📁 <code>{fname}</code>\n👤 <code>{d['prefix']}</code>\n📊 <code>{len(chunk)} contacts</code>" if caption_on else None
            
            bot.send_document(uid, bio, caption=caption)
            increment_vcf_count()
            v_idx += 1
            
        bot.send_message(uid, "✅ <b>VCF Generation Completed Successfully!</b> 🎉")
        user_data[uid] = {'state': 'IDLE'}

    # ---- FINISH STATES (V2T, Merge, Edit, AdminNavy) ----
    elif state == 'V2T_NAME':
        nums = list(dict.fromkeys(user_data[uid]['nums']))
        bio = BytesIO("\n".join(nums).encode('utf-8'))
        bio.name = txt + ".txt"
        bot.send_document(uid, bio, caption="✅ <b>Extracted Numbers</b>")
        bot.send_message(uid, "✅ <b>Extraction Completed Successfully!</b> 🎉")
        user_data[uid] = {'state': 'IDLE'}
        
    elif state == 'MERGE_NAME':
        d = user_data[uid]

        bio = BytesIO(d['vcf_data'].encode('utf-8'))
        bio.name = txt + ".vcf"

        bot.send_document(uid, bio, caption="✅ <b>Merged VCF Ready</b>")
        bot.send_message(uid, "🎉 <b>Merge Completed Successfully!</b>")

        # cleanup
        user_data[uid] = {'state': 'IDLE'}
        
    elif state == 'EDIT_PREFIX':
        user_data[uid]['prefix'] = txt
        user_data[uid]['state'] = 'EDIT_START'
        bot.send_message(uid, "🔢 <b>Start Number?</b> (e.g. 1)")
    elif state == 'EDIT_START':
        user_data[uid]['state'] = 'EDIT_NAME'
        user_data[uid]['cstart'] = int(txt) if txt.isdigit() else 1
        bot.send_message(uid, "📁 <b>VCF Filename?</b>")
    elif state == 'EDIT_NAME':
        d = user_data[uid]
        c_idx = d['cstart']
        nums = list(dict.fromkeys(d['nums']))
        auto_plus = is_auto_plus_on()
        vcf_str = ""
        for n in nums:
            phone = n if n.startswith('+') else f"+{n}" if auto_plus else n
            vcf_str += f"BEGIN:VCARD\nVERSION:3.0\nFN:{d['prefix']} {c_idx}\nTEL;TYPE=CELL:{phone}\nEND:VCARD\n"
            c_idx += 1
        bio = BytesIO(vcf_str.encode('utf-8'))
        bio.name = txt + ".vcf"
        caption = f"📁 <code>{txt}.vcf</code>\n👤 <code>{d['prefix']}</code>\n📊 <code>{len(nums)} contacts</code>" if get_caption_pref(uid) == 'ON' else None
        bot.send_document(uid, bio, caption=caption)
        increment_vcf_count()
        bot.send_message(uid, "✅ <b>Editing Completed Successfully!</b> 🎉")
        user_data[uid] = {'state': 'IDLE'}

    elif state == 'NAVY_ADM_PREF':
        user_data[uid]['adm_pref'] = txt
        user_data[uid]['state'] = 'NAVY_NAV_PREF'
        bot.send_message(uid, "🖋 <b>Step 4: Navy Name Prefix?</b>")
    elif state == 'NAVY_NAV_PREF':
        user_data[uid]['nav_pref'] = txt
        user_data[uid]['state'] = 'NAVY_ADM_START'
        bot.send_message(uid, "🔢 <b>Step 5: Admin Start Number?</b>")
    elif state == 'NAVY_ADM_START':
        user_data[uid]['adm_start'] = int(txt) if txt.isdigit() else 1
        user_data[uid]['state'] = 'NAVY_NAV_START'
        bot.send_message(uid, "🔢 <b>Step 6: Navy Start Number?</b>")
    elif state == 'NAVY_NAV_START':
        user_data[uid]['nav_start'] = int(txt) if txt.isdigit() else 1
        user_data[uid]['state'] = 'NAVY_FINAL_NAME'
        bot.send_message(uid, "📁 <b>Step 7: VCF Filename?</b>")
    elif state == 'NAVY_FINAL_NAME':
        d = user_data[uid]
        fname = txt + ".vcf"
        vcf_str = ""
        a_idx = d['adm_start']
        auto_plus = is_auto_plus_on()
        for n in d['adm_nums']:
            phone = n if n.startswith('+') else f"+{n}" if auto_plus else n
            vcf_str += f"BEGIN:VCARD\nVERSION:3.0\nFN:{d['adm_pref']} {a_idx}\nTEL;TYPE=CELL:{phone}\nEND:VCARD\n"
            a_idx += 1
        n_idx = d['nav_start']
        for n in d['nav_nums']:
            phone = n if n.startswith('+') else f"+{n}" if auto_plus else n
            vcf_str += f"BEGIN:VCARD\nVERSION:3.0\nFN:{d['nav_pref']} {n_idx}\nTEL;TYPE=CELL:{phone}\nEND:VCARD\n"
            n_idx += 1
            
        bio = BytesIO(vcf_str.encode('utf-8'))
        bio.name = fname
        total = len(d['adm_nums']) + len(d['nav_nums'])
        caption = f"📁 <code>{fname}</code>\n👤 <code>Admin & Navy</code>\n📊 <code>{total} contacts</code>" if get_caption_pref(uid) == 'ON' else None
        bot.send_document(uid, bio, caption=caption)
        increment_vcf_count()
        bot.send_message(uid, "✅ <b>Generation Completed!</b> 🎉")
        user_data[uid] = {'state': 'IDLE'}

    # ---- GET NAME ----
    elif state == 'WAIT_VCF_NAME':
        if message.document:
            try:
                names = re.findall(r'FN:(.*)', file_content.decode('utf-8', errors='ignore'))
                res = f"📁 <b>File:</b> <code>{file_name_uploaded}</code>\n📋 <b>Contacts Found:</b>\n\n" + "\n".join([f"<code>{n}</code>" for n in names[:100]])
                if len(names) > 100: res += "\n<i>...and more</i>"
                bot.send_message(uid, res)
                bot.send_message(uid, "✅ <b>Scan Completed Successfully!</b> 🎉")
            except: bot.send_message(uid, "❌ Error parsing VCF.")
        user_data[uid] = {'state': 'IDLE'}

    # ---- ADMIN CONTROLS ----
    elif state == 'ADM_ADD_SUB':
        try:
            parts = txt.split()
            target_uid, plan = int(parts[0]), parts[1].capitalize()
            days = 30 if plan == 'Monthly' else 365
            end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S') if plan != 'Permanent' else 'Permanent'
            
            c = db.cursor()
            c.execute("UPDATE users SET sub_type=?, sub_start=?, sub_end=? WHERE id=?", 
                      (plan, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), end_date, target_uid))
            db.commit()
            bot.send_message(uid, f"✅ <b>Sub Added!</b>\nUser: <code>{target_uid}</code>\nPlan: <code>{plan}</code>")
            
            bot.send_message(target_uid, f"🎉 <b>Congratulations!</b>\nYour <code>{plan}</code> subscription has been activated by Admin.\nEnjoy the premium features! 🚀")
        except: bot.send_message(uid, "❌ Invalid format. Use: ID Plan (e.g., 12345 Monthly)")
        user_data[uid] = {'state': 'IDLE'}

    elif state == 'ADM_REM_SUB':
        c = db.cursor()
        c.execute("UPDATE users SET sub_type='Free', sub_end='N/A' WHERE id=?", (txt,))
        db.commit()
        bot.send_message(uid, "✅ Subscription Removed.")
        user_data[uid] = {'state': 'IDLE'}

    elif state == 'ADM_ADD_ADMIN':
        c = db.cursor()
        c.execute("UPDATE users SET is_admin=1, sub_type='Admin' WHERE id=?", (txt,))
        db.commit()
        bot.send_message(uid, f"✅ <code>{txt}</code> is now an Admin.")
        user_data[uid] = {'state': 'IDLE'}

    elif state == 'ADM_REM_ADMIN':
        if txt == str(MAIN_ADMIN_ID): return bot.send_message(uid, "❌ Cannot remove Main Admin.")
        c = db.cursor()
        c.execute("UPDATE users SET is_admin=0 WHERE id=?", (txt,))
        db.commit()
        bot.send_message(uid, f"✅ Admin rights removed for <code>{txt}</code>.")
        user_data[uid] = {'state': 'IDLE'}

    elif state == 'ADM_ADD_CH':
        c = db.cursor()
        c.execute("INSERT OR IGNORE INTO channels VALUES (?)", (txt,))
        db.commit()
        bot.send_message(uid, f"✅ Channel <code>{txt}</code> added.")
        user_data[uid] = {'state': 'IDLE'}

    elif state == 'ADM_REM_CH':
        c = db.cursor()
        c.execute("DELETE FROM channels WHERE username=?", (txt,))
        db.commit()
        bot.send_message(uid, "✅ Channel Removed.")
        user_data[uid] = {'state': 'IDLE'}

    elif state == 'ADM_BC':
        c = db.cursor()
        users = c.execute("SELECT id FROM users").fetchall()
        bot.send_message(uid, f"📢 Broadcasting to <code>{len(users)}</code> users...")
        success = 0
        for u in users:
            try: 
                bot.send_message(u[0], f"📢 <b>Announcement from Admin:</b>\n━━━━━━━━━━━━━━━━━━━━\n{txt}")
                success += 1
            except: pass
        bot.send_message(uid, f"✅ <b>Broadcast Complete!</b>\nSent successfully to <code>{success}</code> users.")
        user_data[uid] = {'state': 'IDLE'}

# ================= CALLBACKS =================
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    uid = call.from_user.id
    c = db.cursor()
    
    # Caption User Preferences
    if call.data == "cap_yes":
        c.execute("UPDATE users SET caption_pref='ON' WHERE id=?", (uid,))
        db.commit()
        return bot.edit_message_text("✅ <b>Caption preference set to ON.</b>", uid, call.message.message_id)
    elif call.data == "cap_no":
        c.execute("UPDATE users SET caption_pref='OFF' WHERE id=?", (uid,))
        db.commit()
        return bot.edit_message_text("❌ <b>Caption preference set to OFF.</b>", uid, call.message.message_id)
    
    if call.data == "verify_join":
        if check_force_join(uid): bot.answer_callback_query(call.id, "✅ Verified! Press /start", show_alert=True)
        else: bot.answer_callback_query(call.id, "❌ Join all channels first!", show_alert=True)
        return

    # Admin Only Below
    if not is_admin(uid): return

    if call.data == "adm_stats":
        total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        paid_subs = c.execute("SELECT COUNT(*) FROM users WHERE sub_type IN ('Monthly', 'Yearly', 'Permanent', 'Admin')").fetchone()[0]
        trials = c.execute("SELECT COUNT(*) FROM users WHERE sub_type = 'Trial'").fetchone()[0]
        free = c.execute("SELECT COUNT(*) FROM users WHERE sub_type = 'Free'").fetchone()[0]
        vcfs = c.execute("SELECT value FROM settings WHERE key='total_vcf'").fetchone()[0]
        chs = c.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
        
        stat_msg = (
            "📊 <b>Detailed Bot Statistics</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 <b>Total Users:</b> <code>{total_users}</code>\n"
            f"🌟 <b>Paid Subscribers:</b> <code>{paid_subs}</code>\n"
            f"🆓 <b>Active Trials:</b> <code>{trials}</code>\n"
            f"🚫 <b>Free/Expired Users:</b> <code>{free}</code>\n"
            f"📁 <b>Total VCFs Generated:</b> <code>{vcfs}</code>\n"
            f"📢 <b>Force Join Channels:</b> <code>{chs}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━"
        )
        bot.send_message(uid, stat_msg)
        bot.answer_callback_query(call.id)
        
    elif call.data == "adm_power":
        status = c.execute("SELECT value FROM settings WHERE key='bot_status'").fetchone()[0]
        new_stat = "OFF" if status == "ON" else "ON"
        c.execute("UPDATE settings SET value=? WHERE key='bot_status'", (new_stat,))
        db.commit()
        bot.answer_callback_query(call.id, f"Bot is now {new_stat}", show_alert=True)

    elif call.data == "adm_autoplus":
        status = c.execute("SELECT value FROM settings WHERE key='auto_plus'").fetchone()[0]
        new_stat = "OFF" if status == "ON" else "ON"
        c.execute("UPDATE settings SET value=? WHERE key='auto_plus'", (new_stat,))
        db.commit()
        bot.answer_callback_query(call.id, f"Auto Plus (+) is now {new_stat}", show_alert=True)
        
    elif call.data == "adm_sub_add":
        user_data[uid] = {'state': 'ADM_ADD_SUB'}
        bot.send_message(uid, "Send User ID and Plan (Monthly/Yearly/Permanent)\nExample: <code>123456 Monthly</code>")
    elif call.data == "adm_sub_rem":
        user_data[uid] = {'state': 'ADM_REM_SUB'}
        bot.send_message(uid, "Send User ID to remove subscription:")
    elif call.data == "adm_add_admin":
        user_data[uid] = {'state': 'ADM_ADD_ADMIN'}
        bot.send_message(uid, "Send User ID to make them Admin:")
    elif call.data == "adm_rem_admin":
        user_data[uid] = {'state': 'ADM_REM_ADMIN'}
        bot.send_message(uid, "Send User ID to remove Admin access:")
    elif call.data == "adm_ch_add":
        user_data[uid] = {'state': 'ADM_ADD_CH'}
        bot.send_message(uid, "Send Channel Username (e.g. @Rule_Breakerz):")
    elif call.data == "adm_ch_rem":
        user_data[uid] = {'state': 'ADM_REM_CH'}
        bot.send_message(uid, "Send Channel Username to remove:")
    elif call.data == "adm_bc":
        user_data[uid] = {'state': 'ADM_BC'}
        bot.send_message(uid, "Send message to broadcast:")

print("Rule Breakerz VCF Bot - ULTIMATE Edition Started!")
bot.infinity_polling(skip_pending=True)
