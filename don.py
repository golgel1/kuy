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

# --- VARIABEL GLOBAL ---
MEDIA = {}
MEDIA_ELITE = {}
CONFIG = {}
DELETE_DELAY = 600
USERS = set()
REQUIRED_GROUPS = []
MEDIA_ALBUM_TEMP = {}

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

# --- FUNGSI HELPER ---
def gen_code(length=8):
    """Generate random code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def is_owner(user_id):
    """Cek apakah user adalah owner"""
    return user_id in OWNER_IDS

# --- FUNGSI AUTO BACKUP KE GITHUB (DIPERBAIKI) ---
def backup_to_github(commit_message="Auto backup"):
    """Backup semua database ke GitHub - NON BLOCKING"""
    try:
        # Cek dulu apakah git tersedia dan repo sudah di-init
        check_git = subprocess.run(
            ["git", "rev-parse", "--git-dir"], 
            capture_output=True, 
            timeout=5
        )
        
        if check_git.returncode != 0:
            print("⚠️ Git repository belum di-init. Skip backup.")
            return False
        
        # 1. Tambah semua file database
        subprocess.run(
            ["git", "add", f"{DB_FOLDER}/*.json"], 
            capture_output=True,
            timeout=10,
            check=False
        )
        
        # 2. Commit
        subprocess.run(
            ["git", "commit", "-m", commit_message], 
            capture_output=True,
            timeout=10,
            check=False
        )
        
        # 3. Push ke GitHub
        result = subprocess.run(
            ["git", "push"], 
            capture_output=True, 
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print(f"✅ Backup berhasil: {commit_message}")
            return True
        else:
            print(f"⚠️ Backup gagal: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⚠️ Git command timeout")
        return False
    except Exception as e:
        print(f"⚠️ Error backup (diabaikan): {e}")
        return False

def restore_from_github():
    """Restore database dari GitHub"""
    try:
        # Cek git tersedia
        check_git = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            timeout=5
        )
        
        if check_git.returncode != 0:
            print("📝 Git belum di-setup, skip restore")
            return False
        
        # Pull data terbaru
        result = subprocess.run(
            ["git", "pull"], 
            capture_output=True, 
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ Restore dari GitHub berhasil!")
            return True
        else:
            print(f"⚠️ Restore gagal: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"⚠️ Error restore (diabaikan): {e}")
        return False

# --- FUNGSI I/O JSON (DIPERBAIKI) ---
def load_json(path, default):
    """Memuat data dari file JSON."""
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Error load {path}: {e}")
        return default

def save_json(path, data, auto_backup=False):
    """Menyimpan data ke file JSON."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Auto backup OPSIONAL (jangan block proses utama)
        if auto_backup:
            try:
                # Jalankan backup di background thread
                import threading
                threading.Thread(
                    target=backup_to_github,
                    args=(f"Auto backup: {datetime.now().strftime('%Y-%m-%d %H:%M')}",),
                    daemon=True
                ).start()
            except:
                pass
            
        return True
    except Exception as e:
        print(f"❌ Error save JSON: {e}")
        return False

# --- INITIALIZE DATABASE ---
async def initialize_databases():
    """Initialize semua database"""
    global MEDIA, MEDIA_ELITE, CONFIG, DELETE_DELAY, USERS, REQUIRED_GROUPS
    
    print("🔄 Memulai inisialisasi database...")
    
    # 1. OPSIONAL: Restore dari GitHub (ga nge-block kalo gagal)
    try:
        restored = restore_from_github()
        if restored:
            print("📥 Database berhasil di-restore dari GitHub")
    except:
        print("📝 Skip restore, pake data lokal")
    
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

# --- HANDLER START (WAJIB ADA) ---
@bot.message_handler(commands=['start'])
async def start_cmd(m):
    user_id = m.from_user.id
    USERS.add(user_id)
    save_json(DB_USERS, list(USERS))
    
    # Cek apakah ada parameter (kode media)
    args = m.text.split()
    if len(args) > 1:
        code = args[1].upper()
        
        # Cari di database
        media_data = MEDIA.get(code) or MEDIA_ELITE.get(code)
        
        if media_data:
            # Kirim media
            caption = media_data.get("caption", "")
            payload_list = media_data.get("payload", [])
            
            # Kirim setiap media
            for i, payload in enumerate(payload_list):
                try:
                    if payload["type"] == "photo":
                        await bot.send_photo(
                            m.chat.id,
                            payload["file_id"],
                            caption=caption if i == 0 else None
                        )
                    elif payload["type"] == "video":
                        await bot.send_video(
                            m.chat.id,
                            payload["file_id"],
                            caption=caption if i == 0 else None
                        )
                    elif payload["type"] == "document":
                        await bot.send_document(
                            m.chat.id,
                            payload["file_id"],
                            caption=caption if i == 0 else None
                        )
                except Exception as e:
                    print(f"❌ Error send media: {e}")
            
            return
        else:
            await bot.reply_to(m, "❌ Kode tidak ditemukan!")
            return
    
    # Welcome message
    welcome_text = (
        f"👋 <b>Halo {m.from_user.first_name}!</b>\n\n"
        f"Bot ini untuk menyimpan dan share media.\n\n"
    )
    
    if is_owner(user_id):
        welcome_text += "👑 <b>Anda adalah Owner!</b>\n\n"
        welcome_text += "Kirim media untuk disimpan."
    else:
        welcome_text += "Gunakan link dari admin untuk akses media."
    
    await bot.reply_to(m, welcome_text)

# --- HANDLER MEDIA UNTUK OWNER ---
@bot.message_handler(content_types=['photo', 'video', 'document'])
async def handle_media(m):
    user_id = m.from_user.id
    
    if not is_owner(user_id):
        return
    
    # Mode simpan media biasa
    await process_media_save(m, MEDIA, DB_MEDIA, "BIASA")

async def process_media_save(m, target_db, save_path, db_name):
    """Fungsi pembantu untuk memproses penyimpanan media tunggal/album."""
    user_id = m.from_user.id
    caption = m.caption or ""
    
    # 1. Handle Album (Media Group)
    if m.media_group_id:
        if user_id not in MEDIA_ALBUM_TEMP:
            MEDIA_ALBUM_TEMP[user_id] = {
                "caption": caption,
                "payload": [],
                "media_group_id": m.media_group_id,
                "target": db_name
            }
            await bot.reply_to(m, f"🖼️ **Mode Album {db_name} Aktif!** Kirim semua media, lalu kirim **done**.")
        
        payload = {}
        if m.photo:
            payload.update(type="photo", file_id=m.photo[-1].file_id)
        elif m.video:
            payload.update(type="video", file_id=m.video.file_id)
        elif m.document:
            payload.update(type="document", file_id=m.document.file_id)
            
        if payload:
            MEDIA_ALBUM_TEMP[user_id]["payload"].append(payload)
            
    else:
        # 2. Handle Single Media (Simpan instan)
        payload = {}
        if m.photo:
            payload.update(type="photo", file_id=m.photo[-1].file_id)
        elif m.video:
            payload.update(type="video", file_id=m.video.file_id)
        elif m.document:
            payload.update(type="document", file_id=m.document.file_id)
        else:
            return
            
        code = gen_code()
        target_db[code] = {"caption": caption, "payload": [payload]}
        
        # Save ke local + auto backup
        if save_json(save_path, target_db, auto_backup=True):
            link = f"https://t.me/{BOT_USERNAME}?start={code}"
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("📋 Copy Link", url=link))
            
            await bot.reply_to(m, 
                f"✅ <b>Media {db_name} berhasil disimpan!</b>\n\n"
                f"Kode: <code>{code}</code>\n"
                f"Link: {link}",
                reply_markup=kb
            )
        else:
            await bot.reply_to(m, "❌ Gagal menyimpan media!")

# --- HANDLER DONE UNTUK ALBUM ---
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "done")
async def done_save_cmd(m):
    user_id = m.from_user.id
    
    if not is_owner(user_id):
        return
    
    if user_id not in MEDIA_ALBUM_TEMP:
        return
    
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
            
    code = gen_code()
    target_db[code] = {"caption": caption, "payload": payload_list}
    
    # Save + Backup
    if save_json(save_path, target_db, auto_backup=True):
        link = f"https://t.me/{BOT_USERNAME}?start={code}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📋 Copy Link", url=link))
        
        await bot.reply_to(m,
            f"✅ <b>Album {db_name} berhasil disimpan!</b>\n\n"
            f"Kode: <code>{code}</code>\n"
            f"Jumlah Media: {len(payload_list)}\n"
            f"Link: {link}",
            reply_markup=kb
        )
    else:
        await bot.reply_to(m, "❌ Gagal menyimpan album!")
        
    del MEDIA_ALBUM_TEMP[user_id]

# --- COMMAND MANUAL BACKUP ---
@bot.message_handler(commands=["backup"])
async def manual_backup_cmd(m):
    if not is_owner(m.from_user.id):
        return
    
    msg = await bot.reply_to(m, "🔄 **Sedang backup ke GitHub...**")
    
    success = backup_to_github(f"Manual backup by {m.from_user.id}")
    
    if success:
        await bot.edit_message_text(
            "✅ **Backup berhasil!**\n\n"
            "Semua data sudah di-push ke GitHub.",
            m.chat.id,
            msg.message_id
        )
    else:
        await bot.edit_message_text(
            "❌ **Backup gagal!**\n\n"
            "Pastikan git sudah di-setup dengan benar.",
            m.chat.id,
            msg.message_id
        )

# --- COMMAND STATS ---
@bot.message_handler(commands=['stats'])
async def stats_cmd(m):
    if not is_owner(m.from_user.id):
        return
    
    uptime = datetime.utcnow() - START_TIME
    
    stats_text = (
        f"📊 <b>STATISTIK BOT</b>\n\n"
        f"📁 Media Biasa: {len(MEDIA)}\n"
        f"💎 Media Elite: {len(MEDIA_ELITE)}\n"
        f"👥 Total Users: {len(USERS)}\n"
        f"⏱️ Uptime: {str(uptime).split('.')[0]}\n"
    )
    
    await bot.reply_to(m, stats_text)

# --- RUNNER ---
async def init_me():
    global BOT_USERNAME
    try:
        # 1. Initialize databases
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
        print("✅ BOT SIAP JALAN!")
        
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
            traceback.print_exc()
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(runner())
