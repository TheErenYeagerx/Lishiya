# Lishiya Edit Guardian 

![Lishiya Banner](https://files.catbox.moe/u23zkg.jpg)

**Anime-themed Telegram moderation bot** built with **Python 3.10+, Pyrogram, and MongoDB**.

---

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)
![MongoDB](https://img.shields.io/badge/MongoDB-Async-green?style=for-the-badge&logo=mongodb)
![Pyrogram](https://img.shields.io/badge/Pyrogram-Async-blue?style=for-the-badge)
![Telegram](https://img.shields.io/badge/Telegram-Bot-blue?style=for-the-badge&logo=telegram)

---

## 🚀 Features

- 🛡 Auto-delete edited messages in groups  
- 📝 Persistent logging of events  
- 👑 Owner & Sudo management  
- 📢 Broadcast messages to users/groups/all  
- ⚡ Async MongoDB storage for users, groups, and stats   
- ⏳ Clean alerts: auto-delete edited message notifications  

---

## 📜 Commands

### Private Commands
- `/start` – Start bot & show welcome  
- `/help` – Show command guide & buttons  
- `/ping` – Check latency & stats  
- `/addsudo <user_id>` – Add sudo (owner only)  
- `/remsudo <user_id>` – Remove sudo (owner only)  
- `/sudolist` – List sudo users  

### Group Commands
- `/logs` – Show last 20 logs (owner/sudo)  
- `/stats` – Show bot statistics (owner/sudo)  

### Broadcast Commands
- `/broadcast` – Broadcast replied message (owner/sudo)  
- `/broadcast_text <type> <text>` – Broadcast text to users/groups/all  

---

## ⚙️ Setup Instructions

```bash
# Clone repository
git clone https://github.com/TheErenYeager/Lishiya.git
cd Lishiya

# Install dependencies
pip install -r requirements.txt
