# -*- coding: utf-8 -*-
import os
import json
import asyncio
import random
import string
from datetime import datetime
from telebot.async_telebot import AsyncTeleBot
from telebot import types

# --- KONFIGURASI DAN SETUP AWAL ---
# PASTIKAN BOT_TOKEN dan OWNER_ID di set menggunakan Environment Variable.
# JANGAN masukkan token atau ID owner secara hardcode di sini.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip() # Hapus token default di sini
OWNER_ID_STR = os.environ.get("OWNER_ID", "")
try:
    OWNER_ID = int(OWNER_ID_STR)
except ValueError:
    print("FATAL: OWNER_ID tidak diset atau bukan angka.")
    OWNER_ID = 0 # Fallback
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN belum diset di Environment Variable.")


bot = AsyncTeleBot(BOT_TOKEN, parse_mode="HTML")
START_TIME = datetime.utcnow()
BOT_USERNAME = ""
DB_MEDIA = "media.json"
DB_GROUPS = "groups.json"
DB_CONFIG = "config.json"
DB_USERS = "users.json"
USER_STATE = {}

def load_json(path, default):
    """Memuat data dari file JSON."""
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    """Menyimpan data ke file JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

MEDIA = load_json(DB_MEDIA, {})

# --- MUAT KONFIGURASI DAN USER ID ---
CONFIG = load_json(DB_CONFIG, {})
# Waktu hapus default 600 detik (10 menit)
DELETE_DELAY = CONFIG.get("delete_delay_seconds", 600)
USERS = set(load_json(DB_USERS, []))
# --- AKHIR MUAT KONFIGURASI DAN USER ID ---

# --- DAFTAR GRUP WAJIB (REQUIRED_GROUPS) ---
# Daftar default dengan 3 Channel yang sudah kita sepakati:
DEFAULT_REQUIRED_GROUPS = [
    {"id": -1002951551854, "link": "https://t.me/+OJ410VgnrmRhN2Nh",
"fixed": True},
    {"id": -1003112653502, "link": "https://t.me/+uN9YI_j4QJpjYWJl",
"fixed": True},
    {"id": -1003158495012, "link": "https://t.me/+Ue9dsIfR88hhYTBl",
"fixed": True},
]
if os.path.exists(DB_GROUPS) and os.path.getsize(DB_GROUPS) > 0:
    REQUIRED_GROUPS = load_json(DB_GROUPS, DEFAULT_REQUIRED_GROUPS)
else:
    REQUIRED_GROUPS = DEFAULT_REQUIRED_GROUPS
    save_json(DB_GROUPS, REQUIRED_GROUPS)
# --- AKHIR DAFTAR GRUP WAJIB ---

# --- FUNGSI UTILITY ---
def gen_code(length=6):
    """Menghasilkan kode unik untuk media."""
    chars = string.ascii_uppercase + string.digits
    while True:
        c = "".join(random.choice(chars) for _ in range(length))
        if c not in MEDIA:
            return c

def is_owner(uid):
    """Mengecek apakah user adalah owner bot."""
    try:
        # Perhatikan: OWNER_ID sudah diset saat inisialisasi
        return int(uid) == OWNER_ID 
    except:
        return False
        
# FUNGSI CEK KEANGGOTAAN DENGAN PERBAIKAN STABILITAS
async def not_joined(user_id):
    """Mengecek apakah user sudah join semua grup/channel wajib."""
    missing = []
    current_groups = load_json(DB_GROUPS, REQUIRED_GROUPS)
    for g in current_groups:
        try:
            m = await bot.get_chat_member(g["id"], user_id)
            # Jika status adalah 'left' atau 'kicked', berarti BELUM JOIN.
            if m.status in ("left", "kicked"):
                missing.append(g)
        except Exception as e:
            # Kita asumsikan user BELUM JOIN untuk keamanan (Force Subscribe).
            print(f"Error checking membership for {user_id} in {g['id']}: {e}")
            missing.append(g)
    return missing

def join_keyboard(code=""):
    """Membuat keyboard inline untuk cek join."""
    kb = types.InlineKeyboardMarkup()
    current_groups = load_json(DB_GROUPS, REQUIRED_GROUPS)
    for g in current_groups:
        kb.add(types.InlineKeyboardButton("TAB UNTUK JOIN ", url=g["link"]))
    kb.add(types.InlineKeyboardButton("✅ Cek Ulang", callback_data=f"check_join:{code}"))
    return kb

# --- FUNGSI AUTO DELETE DAN SEND MEDIA ---
async def delete_message_after_delay(chat_id, message_id, delay):
    """Menghapus pesan setelah jeda waktu tertentu."""
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass

async def send_single_media(chat_id, item, cap):
    """Mengirim media dengan BLUR/SPOILER dan menjadwalkan penghapusan."""
    tipe = item.get("type")
    file_id = item.get("file_id")
    text_content = item.get("text")
    sent_message = None
    try:
        if tipe == "video":
            sent_message = await bot.send_video(chat_id, file_id, caption=cap, has_spoiler=True)
        elif tipe == "photo":
            sent_message = await bot.send_photo(chat_id, file_id, caption=cap, has_spoiler=True)
        elif tipe == "document":
            sent_message = await bot.send_document(chat_id, file_id,
caption=cap)
        elif tipe == "text":
            sent_message = await bot.send_message(chat_id, text_content or cap)
    except Exception as e:
        print(f"Error sending media: {e}")
        return None
    if sent_message:
        global DELETE_DELAY
        asyncio.create_task(delete_message_after_delay(chat_id, sent_message.message_id, DELETE_DELAY))
        return sent_message.message_id
    return None

async def send_media(chat_id, code):
    """Mengirim semua media terkait kode dan pesan promosi."""
    data = MEDIA.get(code.upper())
    if not data:
        await bot.send_message(chat_id, f"❌  Kode <b>{code}</b> KADALUARSA JOIN @MEDLOKAL UNTUK UPDATENYA!")
        return
    payload_list = data.get("payload", [])
    cap = data.get("caption", "")
    
    # --- 1. KIRIM INGATAN AUTO-DELETE (TOXIC) ---
    global DELETE_DELAY
    minutes = DELETE_DELAY // 60
    reminder_msg = await bot.send_message(chat_id, f"🔥 **INI GRATIS!** Konten dan pesan ini **HILANG PERMANEN dalam {minutes} menit! *SV SEKARANG* atau Menyesal!")
    asyncio.create_task(delete_message_after_delay(chat_id, reminder_msg.message_id, DELETE_DELAY))
    
    # --- 2. LOOP KIRIM SEMUA MEDIA (DENGAN BLUR DAN JADWAL HAPUS) ---
    for i, item in enumerate(payload_list):
        current_caption = cap if i == 0 else None
        await send_single_media(chat_id, item, current_caption)
        
    # --- 3. KIRIM KEYBOARD PROMOSI (TOXIC & PERMANEN) ---
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🚨 ORDER TAB DI SINI! 🚨", url="https://t.me/bagkhnkajakwo_bot?start="))
    kb.row(
        types.InlineKeyboardButton("🔞 KOLEKSI", url="https://t.me/+Ue9dsIfR88hhYTBl"),
        types.InlineKeyboardButton("⭐  PREMIUM", url="https://t.me/+wk0XBM03ayAxZTI1"),
        types.InlineKeyboardButton("📦 BACKUP", url="https://t.me/+zuW0-uBdBX5mOThl")
    )
    kb.row(
        types.InlineKeyboardButton("📱FWB", url="https://t.me/+gdh-ZymHt5c4MWUx"),
        types.InlineKeyboardButton("🌃 ", url="https://t.me/+zlYtolDxBEhhYjk1"),
        types.InlineKeyboardButton("✅  BUKTI TF", url="https://t.me/+vDbGKqYciDkyYTY1")
    )
    txt = "💰 STOP JADI GRATISAN UPDATE NOW\n\n✅  KODE B0WCIL/KODE BAKSO\n✅  VIP BASIC,PREMIUM,EXCLUSIV\n✅  NOKOS TELE & TELE MOD\n\nPEMBELIAN PAKET JAUH LEBIH UNTUNG, ORDER SEKARANG!**\n bot ini d buat olh @myowd"
    await bot.send_message(chat_id, txt, reply_markup=kb)

# --- HANDLER UTAMA ---
@bot.message_handler(commands=["start"])
async def start_cmd(m):
    # SIMPAN ID PENGGUNA UNTUK BROADCAST
    global USERS
    if m.from_user.id not in USERS:
        USERS.add(m.from_user.id)
        save_json(DB_USERS, list(USERS))
        
    code = m.text.split()[1] if len(m.text.split()) > 1 else ""
    missing = await not_joined(m.from_user.id)
    
    if missing:
        # Teks wajib join yang lebih toxic
        await bot.send_message(m.chat.id, "😤 **DASAR GRATISAN!** KONTEN INI MAHAL! **WAJIB JOIN SEMUA DULU!**", reply_markup=join_keyboard(code))
        return
        
    if code:
        await send_media(m.chat.id, code)
    else:
        await bot.send_message(m.chat.id, "Kirim /start KODE")

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_join:"))
async def cb_check(c):
    code = c.data.split(":")[1] if ":" in c.data else ""
    missing = await not_joined(c.from_user.id)
    if missing:
        await bot.answer_callback_query(c.id, "ANAK ANJ! JOIN SEMUA DULU DASAR GERATISAN ", show_alert=True)
        return
    
    await bot.answer_callback_query(c.id)
    try:
        await bot.delete_message(c.message.chat.id, c.message.message_id)
    except:
        pass
        
    if code:
        await send_media(c.message.chat.id, code)

# --- MODE PENYIMPANAN INTERAKTIF (OWNER ONLY) ---
@bot.message_handler(func=lambda m: m.text and m.text.lower() in ["p", "save"])
async def prompt_save_cmd(m):
    if not is_owner(m.from_user.id):
        return
        
    USER_STATE[m.from_user.id] = {"status": "WAITING_FOR_MEDIA", "media": []}
    await bot.reply_to(m, "Silakan kirimkan foto, video, atau teks (album didukung) yang ingin disimpan. Kirim **done** jika sudah selesai.")

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "done")
async def done_save_cmd(m):
    user_id = m.from_user.id
    if not is_owner(user_id) or user_id not in USER_STATE:
        return
        
    state = USER_STATE.get(user_id)
    payload_list = state.get("media", [])
    
    if not payload_list:
        del USER_STATE[user_id]
        await bot.reply_to(m, "❌  Tidak ada media yang diterima. Mode penyimpanan dibatalkan.")
        return
        
    caption = payload_list[-1].get("caption", "")
    for item in payload_list:
        if "caption" in item:
            item["caption"] = None
            
    code = gen_code()
    MEDIA[code] = {"caption": caption, "payload": payload_list}
    save_json(DB_MEDIA, MEDIA)
    
    global BOT_USERNAME # Pastikan BOT_USERNAME sudah diinisialisasi
    link = f"https://t.me/{BOT_USERNAME}?start={code}"
    
    await bot.reply_to(m, f"✅  Berhasil disimpan! Kode: <b>{code}</b>\n\n{link}")
    del USER_STATE[user_id]

@bot.message_handler(
    content_types=["photo", "video", "text", "document"],
    func=lambda m: m.from_user.id in USER_STATE and USER_STATE[m.from_user.id]["status"] == "WAITING_FOR_MEDIA"
)
async def handle_media_save(m):
    user_id = m.from_user.id
    state = USER_STATE[user_id]
    payload = {}
    caption = m.caption or ""
    
    if m.photo:
        payload.update(type="photo", file_id=m.photo[-1].file_id)
    elif m.video:
        payload.update(type="video", file_id=m.video.file_id)
    elif m.document:
        payload.update(type="document", file_id=m.document.file_id)
    elif m.text:
        payload.update(type="text", text=m.text)
    else:
        return
        
    if caption:
        payload["caption"] = caption
        
    state["media"].append(payload)
    USER_STATE[user_id] = state

# --- ADMIN COMMANDS (SILENT CHECK) ---
@bot.message_handler(commands=["set_delay"])
async def set_delay_cmd(m):
    if not is_owner(m.from_user.id):
        return
        
    global DELETE_DELAY, CONFIG
    a = m.text.split()
    if len(a) < 2:
        minutes = DELETE_DELAY // 60
        await bot.reply_to(m, f"Format: /set_delay [menit]. Contoh: /set_delay 5\n\nDelay saat ini: <b>{minutes} menit</b> ({DELETE_DELAY} detik).")
        return
        
    try:
        minutes = int(a[1])
        if minutes <= 0:
            raise ValueError
        new_delay = minutes * 60
        DELETE_DELAY = new_delay
        CONFIG["delete_delay_seconds"] = new_delay
        save_json(DB_CONFIG, CONFIG)
        await bot.reply_to(m, f"✅  Waktu hapus otomatis berhasil diubah menjadi <b>{minutes} menit</b> ({new_delay} detik).")
    except ValueError:
        await bot.reply_to(m, "❌  Masukkan jumlah menit dalam angka positif.")

@bot.message_handler(commands=["broadcast"])
async def broadcast_cmd(m):
    if not is_owner(m.from_user.id):
        return
        
    text = m.text.split(maxsplit=1)
    if len(text) < 2:
        await bot.reply_to(m, "Format: /broadcast [Pesan Anda]")
        return
        
    message_to_send = text[1]
    sent_count = 0
    failed_count = 0
    broadcast_msg = await bot.reply_to(m, f"🚀 Mulai broadcast ke {len(USERS)} pengguna...")
    
    for user_id in list(USERS):
        try:
            await bot.send_message(user_id, message_to_send)
            sent_count += 1
        except Exception:
            failed_count += 1
            pass
            
    await bot.edit_message_text(
        f"✅  Broadcast selesai!\n\nSent: <b>{sent_count}</b>\nGagal (blokir/error): <b>{failed_count}</b>",
        m.chat.id,
        broadcast_msg.message_id
    )

@bot.message_handler(commands=["listgroups"])
async def listg(m):
    if not is_owner(m.from_user.id):
        return
        
    current_groups = load_json(DB_GROUPS, REQUIRED_GROUPS)
    if not current_groups:
        t = "📋 Tidak ada Grup/Channel wajib yang terdaftar."
    else:
        t = "📋 Daftar Grup/Channel Wajib:\n\n" + "\n".join([f"ID: {x['id']}\nLink: {x['link']}" for x in current_groups])
        
    await bot.reply_to(m, t)

@bot.message_handler(commands=["addgroup"])
async def addg(m):
    if not is_owner(m.from_user.id):
        return
        
    a = m.text.split()
    if len(a) < 3:
        await bot.reply_to(m, "Format: /addgroup [ID_Grup/Channel] [Link_Invite]\n\nContoh: /addgroup -100xxx https://t.me/xxx\n\n**Perintah ini bisa digunakan untuk Grup maupun Channel.**")
        return
        
    try:
        gid = int(a[1])
        link = a[2]
    except ValueError:
        await bot.reply_to(m, "❌  Format ID Grup/Channel salah! ID harus angka (contoh: -100xxx).")
        return
        
    required_groups = load_json(DB_GROUPS, REQUIRED_GROUPS)
    if any(g['id'] == gid for g in required_groups):
        await bot.reply_to(m, f"❌  Grup/Channel dengan ID <b>{gid}</b> sudah terdaftar.")
        return
        
    # Set fixed=True agar grup default tidak mudah dihapus
    required_groups.append({"id": gid, "link": link, "fixed": True}) 
    save_json(DB_GROUPS, required_groups)
    await bot.reply_to(m, f"✅  Grup/Channel ID <b>{gid}</b> berhasil ditambahkan!\nTotal Grup/Channel wajib: <b>{len(required_groups)}</b>.")

@bot.message_handler(commands=["delgroup"])
async def delg(m):
    if not is_owner(m.from_user.id):
        return
        
    a = m.text.split()
    if len(a) < 2:
        await bot.reply_to(m, "Format: /delgroup [ID_Grup/Channel]\n\nContoh: /delgroup -100xxx")
        return
        
    try:
        gid = int(a[1])
    except ValueError:
        await bot.reply_to(m, "❌  Format ID Grup/Channel salah! ID harus angka.")
        return
        
    required_groups = load_json(DB_GROUPS, REQUIRED_GROUPS)
    initial_count = len(required_groups)
    new_groups = [g for g in required_groups if g["id"] != gid]
    
    if len(new_groups) == initial_count:
        await bot.reply_to(m, f"⚠️ Grup/Channel ID <b>{gid}</b> tidak ditemukan dalam daftar.")
        return
        
    save_json(DB_GROUPS, new_groups)
    await bot.reply_to(m, f"✅  Grup/Channel ID <b>{gid}</b> telah dihapus. Sisa <b>{len(new_groups)}</b> grup.")

# --- RUNNER ---
async def init_me():
    global BOT_USERNAME
    try:
        me = await bot.get_me()
        BOT_USERNAME = me.username or ""
        print(f"[OK] @{BOT_USERNAME}")
        print(f"[INFO] Owner ID: {OWNER_ID}")
        minutes = DELETE_DELAY // 60
        print(f"[INFO] Delete Delay: {minutes} menit ({DELETE_DELAY} detik)")
        total_users = len(load_json(DB_USERS, []))
        total_media = len(load_json(DB_MEDIA, {}))
        total_groups = len(load_json(DB_GROUPS, []))
        print(f"[INFO] Total Users: {total_users}")
        print(f"[INFO] Total Media: {total_media}")
        print(f"[INFO] Total Grup/Channel Wajib: {total_groups}")
    except Exception as e:
        print(f"[ERROR] {e}")

async def runner():
    await init_me()
    while True:
        try:
            await bot.infinity_polling(timeout=60, skip_pending=True)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            await asyncio.sleep(5)

if __name__ ==  "__main__":
    asyncio.run(runner())
