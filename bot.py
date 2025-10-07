import asyncio
from datetime import datetime, UTC
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, RPCError
from motor.motor_asyncio import AsyncIOMotorClient
from config import (
    API_ID, API_HASH, BOT_TOKEN, MONGO_URI,
    LOGGER_ID, OWNER_ID, SUPPORT_CHAT, START_IMG, BOT_USERNAME
)

bot = Client("lishiya", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["lishiya"]
users_col, groups_col = db["users"], db["groups"]
sudo_col, logs_col = db["sudo"], db["logs"]
stats_col, broadcasts_col = db["stats"], db["broadcasts"]
edit_alert_cache = {}

# --- Utility Functions ---

async def is_sudo(user_id: int) -> bool:
    """Check if a user is owner or sudo."""
    return user_id == OWNER_ID or await sudo_col.find_one({"user_id": user_id}) is not None

async def add_user_record(user):
    """Track user info in database."""
    await users_col.update_one(
        {"user_id": user.id},
        {"$set": {
            "user_id": user.id,
            "first_name": user.first_name or "",
            "username": user.username or "",
            "last_seen": datetime.now(UTC)
        }},
        upsert=True
    )

async def add_group_record(chat):
    """Track group info in database."""
    await groups_col.update_one(
        {"chat_id": chat.id},
        {"$set": {
            "chat_id": chat.id,
            "title": getattr(chat, "title", "") or "",
            "type": str(chat.type),
            "added_on": datetime.now(UTC)
        }},
        upsert=True
    )

async def log_event(kind: str, payload: dict):
    """Logs to DB and sends formatted log to LOGGER_ID."""
    def safe(val):
        if isinstance(val, enums.ChatType):
            return str(val)
        if isinstance(val, datetime):
            return val.isoformat()
        return val
    payload = {k: safe(v) for k, v in payload.items()}
    log_text = (
        f"📝 <b>Log Event</b>\n"
        f"<b>Type:</b> <code>{kind}</code>\n"
        f"<b>Time:</b> <code>{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
        f"<b>Payload:</b> <code>{payload}</code>"
    )
    await logs_col.insert_one({
        "kind": kind,
        "payload": payload,
        "time": datetime.now(UTC)
    })
    try:
        await bot.send_message(LOGGER_ID, log_text, parse_mode=enums.ParseMode.HTML)
    except Exception:
        pass  # Don't break if unable to log to LOGGER_ID

async def increment_stat(name: str, by: int = 1):
    """Increment bot statistics."""
    await stats_col.update_one({"_id": name}, {"$inc": {"value": by}}, upsert=True)

async def safe_send(peer_id: int, method, *args, **kwargs):
    """Safely send messages, handle FloodWait and errors."""
    try:
        return await method(peer_id, *args, **kwargs)
    except FloodWait as e:
        await asyncio.sleep(e.x)
        return await safe_send(peer_id, method, *args, **kwargs)
    except (RPCError, Exception):
        return None

# --- Keyboards ---

def start_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✨ Support", url=SUPPORT_CHAT),
            InlineKeyboardButton("🌐 Source", url="https://github.com/Nexusbhai/Lishiya")
        ],
        [
            InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{BOT_USERNAME}?startgroup=true"),
            InlineKeyboardButton("👤 Owner", url="https://t.me/TheErenYeager")
        ]
    ])

def help_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Contact Owner", url="https://t.me/TheErenYeager")],
        [InlineKeyboardButton("✨ Support", url=SUPPORT_CHAT)]
    ])

# --- Handlers ---

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user = message.from_user
    await add_user_record(user)
    await log_event("user_started", {"user_id": user.id, "name": user.first_name, "username": user.username})
    await client.send_photo(
        message.chat.id,
        START_IMG,
        caption=(
            f"👋 Hey {user.mention}!\n\n"
            "Welcome to <b>Edit Guardian Bot</b> 🌟\n"
            "I keep your groups clean by auto-removing all edited messages.\n"
            "• <b>Clean moderation</b>\n"
            "• <b>Persistent logs</b>\n"
            "• <b>Owner & sudo controls</b>\n\n"
            "Type <code>/help</code> to see all features!"
        ),
        reply_markup=start_keyboard(),
        parse_mode=enums.ParseMode.HTML
    )
    try:
        await client.send_message(
            LOGGER_ID,
            f"📥 New user started bot\n• {user.mention}\n• ID: `{user.id}`\n• @{user.username or 'no-username'}\n• {datetime.now(UTC)}",
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass

@bot.on_message(filters.command("help"))
async def help_cmd(client, message):
    text = (
        "<b>Bot Commands & Features</b>\n\n"
        "<code>/ping</code> — Check bot response time and stats\n"
        "<code>/stats</code> — Bot stats (owner/sudo)\n"
        "<code>/broadcast</code> — Broadcast a replied message (owner/sudo)\n"
        "<code>/broadcast_text <type> <text></code> — Broadcast raw text, type: users|groups|all (owner/sudo)\n"
        "<code>/addsudo <user_id></code> — Add sudo (owner only)\n"
        "<code>/remsudo <user_id></code> — Remove sudo (owner only)\n"
        "<code>/sudolist</code> — List sudo users\n"
        "\n<b>Enjoy premium moderation! 🚀</b>"
    )
    await message.reply_text(text, reply_markup=help_keyboard(), parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("ping"))
async def ping_cmd(client, message):
    start = datetime.now(UTC)
    sent = await message.reply_text("🏓 Pinging...")
    elapsed = (datetime.now(UTC) - start).total_seconds() * 1000
    await sent.edit_text(
        f"🏓 <b>Pong!</b>\n"
        f"⏱️ Latency: <code>{int(elapsed)}ms</code>\n\n"
        f"👤 Users tracked: <code>{await users_col.count_documents({})}</code>\n"
        f"👥 Groups tracked: <code>{await groups_col.count_documents({})}</code>",
        parse_mode=enums.ParseMode.HTML
    )

@bot.on_message(filters.command("addsudo") & filters.user(OWNER_ID))
async def addsudo_cmd(client, message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text("Usage: <code>/addsudo &lt;user_id&gt;</code>", parse_mode=enums.ParseMode.HTML)
    try:
        uid = int(parts[1])
        if await sudo_col.find_one({"user_id": uid}):
            return await message.reply_text("Already a sudo user.", parse_mode=enums.ParseMode.HTML)
        await sudo_col.insert_one({
            "user_id": uid,
            "added_by": message.from_user.id,
            "added_on": datetime.now(UTC)
        })
        await log_event("add_sudo", {"by": message.from_user.id, "user_id": uid})
        await message.reply_text(f"✅ Added sudo: <code>{uid}</code>", parse_mode=enums.ParseMode.HTML)
    except ValueError:
        await message.reply_text("User id must be integer.", parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("remsudo") & filters.user(OWNER_ID))
async def remsudo_cmd(client, message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text("Usage: <code>/remsudo &lt;user_id&gt;</code>", parse_mode=enums.ParseMode.HTML)
    try:
        uid = int(parts[1])
        res = await sudo_col.delete_one({"user_id": uid})
        if res.deleted_count:
            await log_event("remove_sudo", {"by": message.from_user.id, "user_id": uid})
            await message.reply_text(f"✅ Removed sudo: <code>{uid}</code>", parse_mode=enums.ParseMode.HTML)
        else:
            await message.reply_text("User not found in sudo list.", parse_mode=enums.ParseMode.HTML)
    except ValueError:
        await message.reply_text("User id must be integer.", parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("sudolist"))
async def sudolist_cmd(client, message):
    cursor = sudo_col.find({})
    lines = []
    async for d in cursor:
        lines.append(f"• <code>{d['user_id']}</code>")
    if not lines:
        return await message.reply_text("No sudo users.", parse_mode=enums.ParseMode.HTML)
    await message.reply_text(
        "<b>Sudo users:</b>\n" + "\n".join(lines),
        parse_mode=enums.ParseMode.HTML
    )

async def broadcast_message(client, targets, msg_type, message_obj=None, text=None):
    total = sent = failed = 0
    sem = asyncio.Semaphore(20)
    async def send_to(peer_id):
        nonlocal sent, failed
        async with sem:
            try:
                if msg_type == "reply":
                    await safe_send(peer_id, client.copy_message, message_obj.chat.id, message_obj.message_id)
                elif msg_type == "text":
                    await safe_send(peer_id, client.send_message, text)
                sent += 1
            except Exception:
                failed += 1
    tasks = [asyncio.create_task(send_to(t)) for t in set(targets)]
    total = len(tasks)
    await asyncio.gather(*tasks)
    return total, sent, failed

@bot.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_reply_cmd(client, message):
    if not await is_sudo(message.from_user.id):
        return await message.reply_text("Unauthorized.", parse_mode=enums.ParseMode.HTML)
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message to broadcast it.", parse_mode=enums.ParseMode.HTML)
    users = [u["user_id"] async for u in users_col.find({}, {"user_id":1})]
    groups = [g["chat_id"] async for g in groups_col.find({}, {"chat_id":1})]
    targets = users + groups
    status = await message.reply_text("Broadcasting...")
    total, sent, failed = await broadcast_message(client, targets, "reply", message_obj=message.reply_to_message)
    await broadcasts_col.insert_one({
        "by": message.from_user.id,
        "type": "reply_broadcast",
        "attempted": total, "sent": sent, "failed": failed,
        "time": datetime.now(UTC)
    })
    await log_event("broadcast", {
        "by": message.from_user.id,
        "attempted": total, "sent": sent, "failed": failed
    })
    await status.edit_text(
        f"✅ Broadcast complete!\nTotal: <code>{total}</code>\nSent: <code>{sent}</code>\nFailed: <code>{failed}</code>",
        parse_mode=enums.ParseMode.HTML
    )

@bot.on_message(filters.command("broadcast_text"))
async def broadcast_text_cmd(client, message):
    if not await is_sudo(message.from_user.id):
        return await message.reply_text("Unauthorized.", parse_mode=enums.ParseMode.HTML)
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        return await message.reply_text("Usage: <code>/broadcast_text &lt;users|groups|all&gt; &lt;text&gt;</code>", parse_mode=enums.ParseMode.HTML)
    target_type = parts[1].lower()
    text = parts[2]
    targets = []
    if target_type in ("users", "all"):
        targets += [u["user_id"] async for u in users_col.find({}, {"user_id":1})]
    if target_type in ("groups", "all"):
        targets += [g["chat_id"] async for g in groups_col.find({}, {"chat_id":1})]
    status = await message.reply_text(f"Broadcasting to <code>{len(targets)}</code> targets...", parse_mode=enums.ParseMode.HTML)
    total, sent, failed = await broadcast_message(client, targets, "text", text=text)
    await broadcasts_col.insert_one({
        "by": message.from_user.id,
        "type": "text_broadcast",
        "target": target_type,
        "attempted": total, "sent": sent, "failed": failed,
        "time": datetime.now(UTC)
    })
    await log_event("broadcast_text", {
        "by": message.from_user.id,
        "target": target_type,
        "attempted": total, "sent": sent, "failed": failed
    })
    await status.edit_text(
        f"✅ Done!\nTotal: <code>{total}</code>\nSent: <code>{sent}</code>\nFailed: <code>{failed}</code>",
        parse_mode=enums.ParseMode.HTML
    )

@bot.on_message(filters.command("stats"))
async def stats_cmd(client, message):
    if not await is_sudo(message.from_user.id):
        return await message.reply_text("Unauthorized.", parse_mode=enums.ParseMode.HTML)
    users_count = await users_col.count_documents({})
    groups_count = await groups_col.count_documents({})
    logs_count = await logs_col.count_documents({})
    broadcasts_count = await broadcasts_col.count_documents({})
    deleted_edits = (await stats_col.find_one({"_id": "deleted_edits"})) or {"value": 0}
    text = (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👤 Users: <code>{users_count}</code>\n"
        f"👥 Groups: <code>{groups_count}</code>\n"
        f"📝 Logs: <code>{logs_count}</code>\n"
        f"📣 Broadcasts: <code>{broadcasts_count}</code>\n"
        f"🗑️ Edited messages deleted: <code>{deleted_edits.get('value', 0)}</code>\n"
    )
    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)

@bot.on_edited_message(filters.group)
async def edited_handler(client, message):
    user = message.from_user
    if not user or await is_sudo(user.id):
        return
    now = datetime.now(UTC)
    last_alert = edit_alert_cache.get(user.id)
    if last_alert and (now - last_alert).total_seconds() < 5:
        return
    edit_alert_cache[user.id] = now
    text_preview = message.text or "<media>"
    await log_event("edited_deleted", {
        "chat_id": message.chat.id,
        "user_id": user.id,
        "preview": text_preview
    })
    await increment_stat("deleted_edits", 1)
    try:
        await message.delete()
        alert = await client.send_message(
            message.chat.id,
            f"⚠️ <b>{user.first_name}</b> edited a message.\nIt was removed for group cleanliness.",
            parse_mode=enums.ParseMode.HTML
        )
        await asyncio.sleep(5)
        await alert.delete()
    except Exception:
        pass

@bot.on_message(filters.group)
async def track_group_messages(client, message):
    await add_group_record(message.chat)

@bot.on_message(filters.private)
async def track_private_messages(client, message):
    await add_user_record(message.from_user)

@bot.on_message(filters.new_chat_members)
async def new_chat_member(client, message):
    for m in message.new_chat_members:
        if m.is_self:
            await add_group_record(message.chat)
            await log_event("bot_added_to_group", {
                "chat_id": message.chat.id,
                "title": message.chat.title
            })
            try:
                await client.send_message(
                    LOGGER_ID,
                    f"➕ Added to group: <b>{message.chat.title}</b> (<code>{message.chat.id}</code>)",
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception:
                pass

bot.run()