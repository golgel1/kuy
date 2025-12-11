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

# --- FUNGSI AUTO BACKUP KE GITHUB ---
def backup_to_github(commit_message="Auto backup"):
    """Backup semua database ke GitHub"""
    try:
        # 1. Tambah semua file database ke git
        subprocess.run(["git", "add", DB_FOLDER + "/*.json"], check=False)
        
        # 2. Commit
        subprocess.run(["git", "commit", "-m", commit_message], check=False)
        
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
        
        # Auto backup ke GitHub
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
    except:
        pass

# --- INITIALIZE & RESTORE DARI GITHUB ---
async def initialize_databases():
    """Initialize semua database + restore dari GitHub"""
    print("🔄 Memulai inisialisasi database...")
    
    # 1. Restore dari GitHub dulu
    restored = restore_from_github()
    if restored:
        print("📥 Database berhasil di-restore dari GitHub")
    else:
        print("📝 Membuat database baru...")
    
    # 2. Load semua database
    global MEDIA, MEDIA_ELITE, CONFIG, DELETE_DELAY, USERS, REQUIRED_GROUPS
    
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
    
    # 3. Initial backup kalo ada data
    if MEDIA or MEDIA_ELITE:
        asyncio.create_task(async_backup())

# --- MODIFIKASI FUNGSI SAVE MEDIA (TAMBAH BACKUP) ---
async def process_media_save(m, target_db, save_path, db_name):
    """Fungsi pembantu untuk memproses penyimpanan media tunggal/album."""
    user_id = m.from_user.id
    caption = m.caption or ""
    
    # 1. Handle Album (Media Group)
    if m.media_group_id:
        if user_id not in MEDIA_ALBUM_TEMP:
            MEDIA_ALBUM_TEMP[user_id] = {"caption": caption, "payload": [], "media_group_id": m.media_group_id, "target": db_name}
            await bot.reply_to(m, f"🖼️ **Mode Album {db_name} Aktif!** Kirim semua media, lalu kirim **done**.")
        
        payload = {}
        if m.photo: payload.update(type="photo", file_id=m.photo[-1].file_id)
        elif m.video: payload.update(type="video", file_id=m.video.file_id)
        elif m.document: payload.update(type="document", file_id=m.document.file_id)
            
        if payload:
            MEDIA_ALBUM_TEMP[user_id]["payload"].append(payload)
            
    else:
        # 2. Handle Single Media (Simpan instan + Backup)
        payload = {}
        if m.photo: payload.update(type="photo", file_id=m.photo[-1].file_id)
        elif m.video: payload.update(type="video", file_id=m.video.file_id)
        elif m.document: payload.update(type="document", file_id=m.document.file_id)
        else: return
            
        code = gen_code()
        target_db[code] = {"caption": caption, "payload": [payload]}
        
        # Save ke local + auto backup ke GitHub
        if save_json(save_path, target_db):
            # Backup ke GitHub
            backup_success = backup_to_github(f"Add {db_name} media: {code}")
            
            link = f"https://t.me/{BOT_USERNAME}?start={code}"
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("📋 Copy Link", url=link))
            
            backup_msg = "✅ **Auto backup ke GitHub berhasil!**" if backup_success else "⚠️ **Gagal backup ke GitHub, tapi data local tersimpan.**"
            
            await bot.reply_to(m, 
                f"✅  <b>Media {db_name} berhasil disimpan!</b>\n\n"
                f"Kode: <code>{code}</code>\n"
                f"Link: {link}\n\n"
                f"{backup_msg}",
                reply_markup=kb
            )
        else:
            await bot.reply_to(m, "❌ Gagal menyimpan media!")

# --- MODIFIKASI DONE SAVE (TAMBAH BACKUP) ---
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "done" and m.from_user.id in MEDIA_ALBUM_TEMP)
async def done_save_cmd(m):
    user_id = m.from_user.id
    if not is_owner(user_id): return
    
    state = MEDIA_ALBUM_TEMP.get(user_id)
    payload_list = state.get("payload", [])
    caption = state.get("caption", "")
    db_name = state.get("target")
    
    if db_name == "ELITE":
        target_db = MEDIA_ELITE
        save_path = DB_MEDIA_ELITE
    else:
        target_db = MEDIA
        save_path = DB_MEDIA

    if len(payload_list) <= 1:
        await bot.reply_to(m, "❌ Album dibatalkan. MEDIA CUMA SATU!")
        del MEDIA_ALBUM_TEMP[user_id]
        return
        
    # Hapus caption dari media individual
    for item in payload_list:
        if "caption" in item:
            item["caption"] = None 
            
    code = gen_code()
    target_db[code] = {"caption": caption, "payload": payload_list}
    
    # Save + Backup
    if save_json(save_path, target_db):
        backup_success = backup_to_github(f"Add {db_name} album: {code} ({len(payload_list)} media)")
        
        link = f"https://t.me/{BOT_USERNAME}?start={code}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📋 Copy Link", url=link))
        
        backup_msg = "✅ **Auto backup ke GitHub berhasil!**" if backup_success else "⚠️ **Gagal backup ke GitHub, tapi data local tersimpan.**"
        
        await bot.reply_to(m,
            f"✅  <b>Album {db_name} berhasil disimpan!</b>\n\n"
            f"Kode: <code>{code}</code>\n"
            f"Jumlah Media: {len(payload_list)}\n"
            f"Link: {link}\n\n"
            f"{backup_msg}",
            reply_markup=kb
        )
    else:
        await bot.reply_to(m, "❌ Gagal menyimpan album!")
        
    del MEDIA_ALBUM_TEMP[user_id]

# --- FUNGSI MANUAL BACKUP (UNTUK OWNER) ---
@bot.message_handler(commands=["backup"])
async def manual_backup_cmd(m):
    if not is_owner(m.from_user.id):
        return
    
    msg = await bot.reply_to(m, "🔄 **Sedang backup ke GitHub...**")
    
    success = backup_to_github(f"Manual backup by {m.from_user.id}")
    
    if success:
        await bot.edit_message_text(
            "✅ **Backup berhasil!**\n\n"
            "Semua data sudah di-push ke GitHub.\n"
            "Kalo VPS ilang, data tetap aman!",
            m.chat.id,
            msg.message_id
        )
    else:
        await bot.edit_message_text(
            "❌ **Backup gagal!**\n\n"
            "Cek koneksi atau konfigurasi git.",
            m.chat.id,
            msg.message_id
        )

# --- ADMIN MENU TAMBAH FITUR BACKUP ---
@bot.callback_query_handler(func=lambda c: c.data == "admin:backup")
async def admin_backup_menu(c):
    if not is_owner(c.from_user.id): return
    
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔄 Backup Sekarang", callback_data="do_backup"),
        types.InlineKeyboardButton("📊 Cek Status", callback_data="check_backup")
    )
    kb.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="admin:back"))
    
    await bot.edit_message_text(
        "💾 **Menu Backup GitHub**\n\n"
        "Fitur ini akan menyimpan semua database ke GitHub.\n"
        "Data aman kalo VPS rusak/hilang!",
        c.message.chat.id,
        c.message.message_id,
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data == "do_backup")
async def do_backup_callback(c):
    if not is_owner(c.from_user.id): return
    
    await bot.answer_callback_query(c.id, "🔄 Backup dimulai...")
    
    success = backup_to_github(f"Backup via admin menu by {c.from_user.id}")
    
    if success:
        await bot.edit_message_text(
            "✅ **Backup berhasil!**\n\n"
            "Semua data sudah di-push ke GitHub.",
            c.message.chat.id,
            c.message.message_id
        )
    else:
        await bot.edit_message_text(
            "❌ **Backup gagal!**",
            c.message.chat.id,
            c.message.message_id
        )

# --- MODIFIKASI FUNGSI LAIN YANG SAVE DATA ---
# (Semua fungsi yang pake save_json() otomatis backup)

# ... [SISANYA KODE SAMA PERSIS DENGAN YANG SEBELUMNYA] ...
# (Fungsi-fungsi lain tetap sama, cuma panggil save_json())

# --- RUNNER YANG DIMODIFIKASI ---
async def init_me():
    global BOT_USERNAME
    try:
        # 1. Initialize databases + restore dari GitHub
        await initialize_databases()
        
        # 2. Get bot info
        me = await bot.get_me()
        BOT_USERNAME = me.username or ""
        
        print(f"\n{'='*50}")
        print(f"🤖 BOT: @{BOT_USERNAME}")
        print(f"📊 Media Biasa: {len(MEDIA)} item")
        print(f"💎 Media Elite: {len(MEDIA_ELITE)} item")
        print(f"👥 Total Users: {len(USERS)}")
        print(f"👑 Owners: {len(OWNER_IDS)}")
        print(f"⏱️ Auto Delete: {DELETE_DELAY//60} menit")
        print(f"{'='*50}")
        print("✅ BOT SIAP JALAN + AUTO BACKUP KE GITHUB!")
        
    except Exception as e:
        print(f"❌ Error init: {e}")
        traceback.print_exc()

async def runner():
    await init_me()
    while True:
        try:
            await bot.infinity_polling(timeout=60, skip_pending=True)
        except KeyboardInterrupt:
            print("\n🛑 Bot dihentikan")
            break
        except Exception as e:
            print(f"❌ Polling error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(runner())
