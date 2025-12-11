#!/bin/bash
echo "========================================"
echo "🤖 SETUP BOT AUTO BACKUP KE GITHUB"
echo "========================================"

# Warna terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Cek git udah installed
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git belum terinstall!${NC}"
    echo "Install dulu:"
    echo "  Ubuntu: sudo apt install git"
    echo "  Termux: pkg install git"
    exit 1
fi

# Cek Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 belum terinstall!${NC}"
    exit 1
fi

# Input data
echo -e "\n${YELLOW}📝 MASUKKAN DATA BOT:${NC}"
read -p "BOT_TOKEN: " BOT_TOKEN
read -p "OWNER_IDS (contoh: 123456789,987654321): " OWNER_IDS
read -p "GitHub Repo URL (contoh: https://github.com/golgel1/kuy.git): " REPO_URL

# Validasi input
if [ -z "$BOT_TOKEN" ] || [ -z "$OWNER_IDS" ] || [ -z "$REPO_URL" ]; then
    echo -e "${RED}❌ Semua field wajib diisi!${NC}"
    exit 1
fi

# Buat .env file
echo -e "\n${GREEN}📁 Membuat .env file...${NC}"
cat > .env << EOF
BOT_TOKEN=$BOT_TOKEN
OWNER_IDS=$OWNER_IDS
EOF
echo "✅ .env file created"

# Buat folder bot_databases
mkdir -p bot_databases

# Setup git
echo -e "\n${GREEN}⚙️ Setup Git...${NC}"
git init

# Configure git
git config --global user.name "Bot Auto Backup"
git config --global user.email "bot@backup.com"

# Add semua file
git add .

# First commit
git commit -m "Initial commit: Bot with auto backup"

# Setup remote
git remote add origin $REPO_URL
git branch -M main

# Test push
echo -e "\n${GREEN}🚀 Push ke GitHub...${NC}"
if git push -u origin main; then
    echo "✅ Push berhasil!"
else
    echo -e "${YELLOW}⚠️ Gagal push, mungkin repo belum kosong${NC}"
    echo "Coba: git push -u origin main --force"
fi

# Install dependencies
echo -e "\n${GREEN}📦 Install dependencies...${NC}"
pip install pyTelegramBotAPI

# Buat script run bot
echo -e "\n${GREEN}📜 Buat run script...${NC}"
cat > run.sh << 'EOF'
#!/bin/bash
# Load environment variables
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

# Cek token
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ BOT_TOKEN tidak ditemukan!"
    echo "Export dulu: export BOT_TOKEN='token_kamu'"
    exit 1
fi

# Pull update dari GitHub
echo "🔄 Pull update dari GitHub..."
git pull origin main

# Jalankan bot
echo "🚀 Menjalankan bot..."
python3 don.py
EOF

chmod +x run.sh

# Buat cron job untuk auto backup
echo -e "\n${GREEN}⏰ Setup auto backup (cron)...${NC}"
cat > backup_cron.sh << 'EOF'
#!/bin/bash
cd /path/to/your/bot/folder  # GANTI INI!
git add bot_databases/*.json
git commit -m "Auto backup $(date '+%Y-%m-%d %H:%M:%S')" 2>/dev/null
git push origin main 2>/dev/null
EOF

chmod +x backup_cron.sh

echo -e "\n${GREEN}========================================"
echo "✅ SETUP SELESAI!"
echo "========================================"
echo ""
echo "📌 CARA JALANKAN BOT:"
echo "1. Export variables:"
echo "   export BOT_TOKEN='$BOT_TOKEN'"
echo "   export OWNER_IDS='$OWNER_IDS'"
echo ""
echo "2. Jalankan bot:"
echo "   ./run.sh"
echo ""
echo "3. Manual backup:"
echo "   python3 don.py  # Lalu kirim /backup ke bot"
echo ""
echo "⚠️  JANGAN LUPA:"
echo "   - Ganti path di backup_cron.sh"
echo "   - Setup cron job: crontab -e"
echo "     Tambah: 0 */6 * * * /path/to/backup_cron.sh"
echo "========================================"
