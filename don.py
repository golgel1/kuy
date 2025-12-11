# -*- coding: utf-8 -*-
import os
import json
import asyncio
import random
import string
from datetime import datetime
from telebot.async_telebot import AsyncTeleBot
from telebot import types
import subprocess
import traceback

# --- KONFIGURASI DAN SETUP AWAL ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OWNER_IDS_STR = os.environ.get("OWNER_IDS", "").strip()

# VALIDASI
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN GAK ADA ANJING! EXPORT DULU!")
if not OWNER_IDS_STR:
    raise RuntimeError("❌ OWNER_IDS GAK ADA BANGSAT! EXPORT DULU!")

OWNER_IDS = set(map(int, OWNER_IDS_STR.split(",")))

bot = AsyncTeleBot(BOT_TOKEN, parse_mode="HTML")
START_TIME = datetime.utcnow()
BOT_USERNAME = ""

# --- GLOBAL VARIABLES ---
MEDIA_ALBUM_TEMP = {}
MEDIA = {}
MEDIA_ELITE = {}
CONFIG = {}
DELETE_DELAY = 600
USERS = set()
REQUIRED_GROUPS = []

# --- PATH DATABASE ---
DB_FOLDER = "bot_databases"
os.makedirs(DB_FOLDER, exist_ok=True)

def get_db_path(filename):
    bot_id = BOT_TOKEN.split(":")[0] if BOT_TOKEN else "default"
    return os.path.join(DB_FOLDER, f"bot_{bot_id}_{filename}")

DB_MEDIA = get_db_path("media.json")
DB_MEDIA_ELITE = get_db_path("media_elite.json")
DB_GROUPS = get_db_path("groups.json")
DB_CONFIG = get_db_path("config.json")
DB_USERS = get_db_path("users.json")
DB_OWNERS = get_db_path("owners.json")

# --- HELPER FUNCTIONS ---
def gen_code(length=8):
    """Generate random code untuk media"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def is_owner(user_id):
    """Check apakah user adalah owner"""
    return user_id in OWNER_IDS

# --- FUNGSI AUTO BACKUP KE GITHUB ---
def backup_to_github(commit_message="Auto backup"):
    """Backup semua database ke GitHub"""
    try:
        # 1. Tambah semua file database ke git (FIXED: ga pake wildcard)
        for file in os.listdir(DB_FOLDER):
            if file.endswith(".json"):
                filepath = os.path.join(DB_FOLDER, file)
                subprocess.run(["git", "add", filepath], check=False)
        
        # 2. Commit
        result = subprocess.run(["git", "commit", "-m", commit_message], 
                              capture_output=True, text=True, check=False)
        
        # 3. Push ke GitHub
        result = subprocess.run(["git", "push"], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Backup berhasil: {commit_message}")
            return True
        else:
            print(f"⚠️ Backup gagal: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error backup: {e}")
        return False

def restore_from_github():
    """Restore database dari GitHub"""
    try:
        # Pull data terbaru dari GitHub
        result = subprocess.run(["git", "pull"], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Restore dari GitHub berhasil!")
            return True
        else:
            print(f"⚠️ Restore gagal: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error restore: {e}")
        return False

# --- FUNGSI I/O JSON (DITAMBAH AUTO BACKUP) ---
def load_json(path, default):
    """Memuat data dari file JSON."""
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data, auto_backup=True):
    """Menyimpan data ke file JSON + Auto Backup."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Auto backup ke GitHub (jangan wait, biar ga ngeblock)
        if auto_backup:
            asyncio.create_task(async_backup())
            
        return True
    except Exception as e:
        print(f"❌ Error save JSON: {e}")
        return False

async def async_backup():
    """Backup async ke GitHub"""
    try:
        # Tunggu sebentar biar ga spam
        await asyncio.sleep(2)
        backup_to_github("Auto backup: " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    except Exception as e:
        print(f"❌ Error async backup: {e}")

# --- INITIALIZE & RESTORE DARI GITHUB ---
async def initialize_databases():
    """Initialize semua database + restore dari GitHub"""
    global MEDIA, MEDIA_ELITE, CONFIG, DELETE_DELAY, USERS, REQUIRED_GROUPS
    
    print("🔄 Memulai inisialisasi database...")
    
    # 1. Restore dari GitHub dulu
    restored = restore_from_github()
    if restored:
        print("📥 Database berhasil di-restore dari GitHub")
    else:
        print("📝 Membuat database baru...")
    
    # 2. Load semua database
    MEDIA = load_json(DB_MEDIA, {})
    MEDIA_ELITE = load_json(DB_MEDIA_ELITE, {})
    CONFIG = load_json(DB_CONFIG, {})
    DELETE_DELAY = CONFIG.get("delete_delay_seconds", 600)
    USERS = set(load_json(DB_USERS, []))
    
    # Load owners
    saved_owners = load_json(DB_OWNERS, list(OWNER_IDS))
    OWNER_IDS.update(saved_owners)
    save_json(DB_OWNERS, list(OWNER_IDS), auto_backup=False)
    
    REQUIRED_GROUPS = load_json(DB_GROUPS, [])
    
    print(f"📊 Statistik awal:")
    print(f"   Media Biasa: {len(MEDIA)} item")
    print(f"   Media Elite: {len(MEDIA_ELITE)} item")
    print(f"   Total Users: {len(USERS)}")

# --- HANDLER START COMMAND ---
@bot.message_handler(commands=["start"])
async def start_cmd(m):
    user_id = m.from_user.id
    username = m.from_user.username or "Unknown"
    
    # Tambah user ke database
    if user_id not in USERS:
        USERS.add(user_id)
        save_json(DB_USERS, list(USERS))
    
    # Check kalo ada parameter (code media)
    args = m.text.split(maxsplit=1)
    if len(args) > 1:
        code = args[1]
        await send_media_by_code(m, code)
        return
    
    # Welcome message
    kb = types.InlineKeyboardMarkup()
    if is_owner(user_id):
        kb.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin:menu"))
    
    await bot.reply_to(m,
        f"👋 Halo <b>{username}</b>!\n\n"
        f"🤖 Bot ini untuk share media dengan link!\n\n"
        f"👥 Total Users: {len(USERS)}\n"
        f"📊 Total Media: {len(MEDIA) + len(MEDIA_ELITE)}",
        reply_markup=kb
    )

async def send_media_by_code(m, code):
    """Kirim media berdasarkan code"""
    user_id = m.from_user.id
    
    # Cari di database
    media_data = MEDIA.get(code) or MEDIA_ELITE.get(code)
    
    if not media_data:
        await bot.reply_to(m, "❌ Code tidak ditemukan!")
        return
    
    caption = media_data.get("caption", "")
    payload_list = media_data.get("payload", [])
    
    if not payload_list:
        await bot.reply_to(m, "❌ Media kosong!")
        return
    
    try:
        sent_msgs = []
        
        # Kirim media
        if len(payload_list) == 1:
            # Single media
            p = payload_list[0]
            if p["type"] == "photo":
                msg = await bot.send_photo(m.chat.id, p["file_id"], caption=caption)
            elif p["type"] == "video":
                msg = await bot.send_video(m.chat.id, p["file_id"], caption=caption)
            elif p["type"] == "document":
                msg = await bot.send_document(m.chat.id, p["file_id"], caption=caption)
            sent_msgs.append(msg)
        else:
            # Album/Media group
            media_group = []
            for i, p in enumerate(payload_list):
                if p["type"] == "photo":
                    media_group.append(types.InputMediaPhoto(p["file_id"], 
                                     caption=caption if i == 0 else None))
                elif p["type"] == "video":
                    media_group.append(types.InputMediaVideo(p["file_id"], 
                                     caption=caption if i == 0 else None))
                elif p["type"] == "document":
                    media_group.append(types.InputMediaDocument(p["file_id"], 
                                     caption=caption if i == 0 else None))
            
            msgs = await bot.send_media_group(m.chat.id, media_group)
            sent_msgs.extend(msgs)
        
        # Auto delete
        if DELETE_DELAY > 0:
            for msg in sent_msgs:
                asyncio.create_task(auto_delete_message(m.chat.id, msg.message_id))
                
    except Exception as e:
        print(f"❌ Error send media: {e}")
        await bot.reply_to(m, f"❌ Gagal kirim media: {str(e)}")

async def auto_delete_message(chat_id, message_id):
    """Auto delete message setelah delay"""
    try:
        await asyncio.sleep(DELETE_DELAY)
        await bot.delete_message(chat_id, message_id)
    except:
        pass

# --- HANDLER UNTUK SAVE MEDIA (OWNER ONLY) ---
@bot.message_handler(content_types=["photo", "video", "document"])
async def handle_media(m):
    user_id = m.from_user.id
    
    if not is_owner(user_id):
        return
    
    # Check apakah lagi mode album
    if user_id in MEDIA_ALBUM_TEMP:
        await process_album_media(m)
    else:
        # Tanya mau save ke mana
        kb = types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton("📁 Biasa", callback_data=f"save:normal:{m.message_id}"),
            types.InlineKeyboardButton("💎 Elite", callback_data=f"save:elite:{m.message_id}")
        )
        kb.add(types.InlineKeyboardButton("🗑️ Batal", callback_data="save:cancel"))
        
        await bot.reply_to(m, "💾 Mau save ke database mana?", reply_markup=kb)

async def process_album_media(m):
    """Proses media yang masuk saat mode album aktif"""
    user_id = m.from_user.id
    state = MEDIA_ALBUM_TEMP[user_id]
    
    payload = {}
    if m.photo: 
        payload = {"type": "photo", "file_id": m.photo[-1].file_id}
    elif m.video: 
        payload = {"type": "video", "file_id": m.video.file_id}
    elif m.document: 
        payload = {"type": "document", "file_id": m.document.file_id}
    
    if payload:
        state["payload"].append(payload)
        await bot.reply_to(m, f"➕ Media ditambahkan ({len(state['payload'])}). Kirim 'done' kalau udah selesai.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("save:"))
async def save_media_callback(c):
    if not is_owner(c.from_user.id):
        return
    
    parts = c.data.split(":")
    action = parts[1]
    
    if action == "cancel":
        await bot.delete_message(c.message.chat.id, c.message.message_id)
        return
    
    msg_id = int(parts[2])
    db_type = action  # "normal" atau "elite"
    
    try:
        # Get original message
        orig_msg = await bot.forward_message(c.from_user.id, c.message.chat.id, msg_id)
        
        # Save media
        target_db = MEDIA_ELITE if db_type == "elite" else MEDIA
        save_path = DB_MEDIA_ELITE if db_type == "elite" else DB_MEDIA
        db_name = "ELITE" if db_type == "elite" else "BIASA"
        
        caption = orig_msg.caption or ""
        payload = {}
        
        if orig_msg.photo:
            payload = {"type": "photo", "file_id": orig_msg.photo[-1].file_id}
        elif orig_msg.video:
            payload = {"type": "video", "file_id": orig_msg.video.file_id}
        elif orig_msg.document:
            payload = {"type": "document", "file_id": orig_msg.document.file_id}
        
        if not payload:
            await bot.answer_callback_query(c.id, "❌ Format media tidak didukung!")
            return
        
        code = gen_code()
        target_db[code] = {"caption": caption, "payload": [payload]}
        
        if save_json(save_path, target_db):
            link = f"https://t.me/{BOT_USERNAME}?start={code}"
            
            await bot.edit_message_text(
                f"✅ <b>Media {db_name} berhasil disimpan!</b>\n\n"
                f"Kode: <code>{code}</code>\n"
                f"Link: {link}",
                c.message.chat.id,
                c.message.message_id
            )
        else:
            await bot.answer_callback_query(c.id, "❌ Gagal save!")
        
        # Delete forwarded message
        await bot.delete_message(c.from_user.id, orig_msg.message_id)
        
    except Exception as e:
        print(f"❌ Error save: {e}")
        await bot.answer_callback_query(c.id, f"❌ Error: {str(e)}")

# --- HANDLER DONE (UNTUK ALBUM) ---
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "done")
async def done_album_cmd(m):
    user_id = m.from_user.id
    
    if not is_owner(user_id):
        return
    
    if user_id not in MEDIA_ALBUM_TEMP:
        await bot.reply_to(m, "❌ Ga ada album aktif!")
        return
    
    state = MEDIA_ALBUM_TEMP[user_id]
    payload_list = state["payload"]
    caption = state.get("caption", "")
    
    if len(payload_list) < 2:
        await bot.reply_to(m, "❌ Album minimal 2 media!")
        del MEDIA_ALBUM_TEMP[user_id]
        return
    
    # Tanya mau save ke mana
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("📁 Biasa", callback_data="album:normal"),
        types.InlineKeyboardButton("💎 Elite", callback_data="album:elite")
    )
    
    await bot.reply_to(m, f"💾 Album dengan {len(payload_list)} media. Mau save ke mana?", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("album:"))
async def save_album_callback(c):
    if not is_owner(c.from_user.id):
        return
    
    user_id = c.from_user.id
    db_type = c.data.split(":")[1]
    
    if user_id not in MEDIA_ALBUM_TEMP:
        await bot.answer_callback_query(c.id, "❌ Session expired!")
        return
    
    state = MEDIA_ALBUM_TEMP[user_id]
    
    target_db = MEDIA_ELITE if db_type == "elite" else MEDIA
    save_path = DB_MEDIA_ELITE if db_type == "elite" else DB_MEDIA
    db_name = "ELITE" if db_type == "elite" else "BIASA"
    
    code = gen_code()
    target_db[code] = {
        "caption": state.get("caption", ""),
        "payload": state["payload"]
    }
    
    if save_json(save_path, target_db):
        link = f"https://t.me/{BOT_USERNAME}?start={code}"
        
        await bot.edit_message_text(
            f"✅ <b>Album {db_name} berhasil disimpan!</b>\n\n"
            f"Kode: <code>{code}</code>\n"
            f"Media: {len(state['payload'])} items\n"
            f"Link: {link}",
            c.message.chat.id,
            c.message.message_id
        )
    else:
        await bot.answer_callback_query(c.id, "❌ Gagal save!")
    
    del MEDIA_ALBUM_TEMP[user_id]

# --- COMMAND START ALBUM ---
@bot.message_handler(commands=["album"])
async def start_album_cmd(m):
    if not is_owner(m.from_user.id):
        return
    
    user_id = m.from_user.id
    MEDIA_ALBUM_TEMP[user_id] = {"caption": "", "payload": []}
    
    await bot.reply_to(m, 
        "🖼️ <b>Mode Album Aktif!</b>\n\n"
        "Kirim semua media (foto/video/document), lalu ketik <b>done</b>."
    )

# --- MANUAL BACKUP COMMAND ---
@bot.message_handler(commands=["backup"])
async def manual_backup_cmd(m):
    if not is_owner(m.from_user.id):
        return
    
    msg = await bot.reply_to(m, "🔄 Backup ke GitHub...")
    
    success = backup_to_github(f"Manual backup by {m.from_user.id}")
    
    if success:
        await bot.edit_message_text(
            "✅ Backup berhasil ke GitHub!",
            m.chat.id,
            msg.message_id
        )
    else:
        await bot.edit_message_text(
            "❌ Backup gagal! Cek koneksi/config git.",
            m.chat.id,
            msg.message_id
        )

# --- STATS COMMAND ---
@bot.message_handler(commands=["stats"])
async def stats_cmd(m):
    if not is_owner(m.from_user.id):
        return
    
    uptime = datetime.utcnow() - START_TIME
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    
    await bot.reply_to(m,
        f"📊 <b>Statistik Bot</b>\n\n"
        f"👥 Total Users: {len(USERS)}\n"
        f"📁 Media Biasa: {len(MEDIA)}\n"
        f"💎 Media Elite: {len(MEDIA_ELITE)}\n"
        f"⏱️ Uptime: {uptime.days}d {hours}h {minutes}m\n"
        f"🗑️ Auto Delete: {DELETE_DELAY//60} menit"
    )

# --- ADMIN MENU ---
@bot.callback_query_handler(func=lambda c: c.data == "admin:menu")
async def admin_menu(c):
    if not is_owner(c.from_user.id):
        return
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📊 Stats", callback_data="admin:stats"))
    kb.add(types.InlineKeyboardButton("💾 Backup", callback_data="admin:backup"))
    kb.add(types.InlineKeyboardButton("🗑️ Delete Media", callback_data="admin:delete"))
    
    await bot.edit_message_text(
        "⚙️ <b>Admin Panel</b>\n\nPilih menu:",
        c.message.chat.id,
        c.message.message_id,
        reply_markup=kb
    )

# --- RUNNER ---
async def init_me():
    global BOT_USERNAME
    try:
        await initialize_databases()
        
        me = await bot.get_me()
        BOT_USERNAME = me.username or ""
        
        print(f"\n{'='*50}")
        print(f"🤖 BOT: @{BOT_USERNAME}")
        print(f"📊 Media Biasa: {len(MEDIA)}")
        print(f"💎 Media Elite: {len(MEDIA_ELITE)}")
        print(f"👥 Total Users: {len(USERS)}")
        print(f"👑 Owners: {len(OWNER_IDS)}")
        print(f"{'='*50}")
        print("✅ BOT SIAP!")
        
    except Exception as e:
        print(f"❌ Init error: {e}")
        traceback.print_exc()

async def runner():
    await init_me()
    while True:
        try:
            await bot.infinity_polling(timeout=60, skip_pending=True)
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped")
            break
        except Exception as e:
            print(f"❌ Polling error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(runner())
