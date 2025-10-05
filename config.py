import os

# Telegram API credentials
API_ID = int(os.getenv("API_ID", ""))
API_HASH = os.getenv("API_HASH", "")

# Bot token from @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# MongoDB connection URI
MONGO_URI = os.getenv("MONGO_URI", "")

# Log group/channel ID where logs are sent
LOGGER_ID = int(os.getenv("LOGGER_ID", "-100"))

# Owner Telegram ID (main admin)
OWNER_ID = int(os.getenv("OWNER_ID", "5106602523"))

# Optional: Support and Updates channel/usernames (for start/help buttons)
SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "https://t.me/Radhasprt")
UPDATES_CHANNEL = os.getenv("UPDATES_CHANNEL", "https://t.me/TheRadhaupdate")

# Default sudo users (will also be stored in MongoDB for persistent use)
SUDO_USERS = [OWNER_ID]

# Bot name and customization
BOT_NAME = os.getenv("BOT_NAME", "carlotta")
BOT_USERNAME = os.getenv("BOT_USERNAME", "carlotta_Robot")

# Time zone (optional, used in logger and uptime tracking)
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

# For extra optional configs (safe to leave empty)
START_IMG = os.getenv("START_IMG", "https://te.legra.ph/file/5a9550c10d934ff11f7b8.jpg")
