import asyncio
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, RPCError
from motor.motor_asyncio import AsyncIOMotorClient
from config import API_ID, API_HASH, BOT_TOKEN, MONGO_URI, LOGGER_ID, OWNER_ID, SUPPORT_CHAT, START_IMG, BOT_USERNAME

bot = Client("lishiya", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["lishiya"]
users_col = db["users"]
groups_col = db["groups"]
sudo_col = db["sudo"]
logs_col = db["logs"]
stats_col = db["stats"]
broadcasts_col = db["broadcasts"]

edit_alert_cache = {}

async def is_sudo(user_id: int) -> bool:
    return user_id == OWNER_ID or await sudo_col.find_one({"user_id": user_id}) is not None

async def add_user_record(user):
    await users_col.update_one(
        {"user_id": user.id},
        {"$set": {
            "user_id": user.id,
            "first_name": user.first_name or "",
            "username": user.username or "",
            "last_seen": datetime.utcnow()
        }},
        upsert=True
    )

async def add_group_record(chat):
    await groups_col.update_one(
        {"chat_id": chat.id},
        {"$set": {
            "chat_id": chat.id,
            "title": getattr(chat, "title", "") or "",
            "type": chat.type,
            "added_on": datetime.utcnow()
        }},
        upsert=True
    )

async def log_event(kind: str, payload: dict):
    await logs_col.insert_one({"kind": kind, "payload": payload, "time": datetime.utcnow()})

async def increment_stat(name: str, by: int = 1):
    await stats_col.update_one({"_id": name}, {"$inc": {"value": by}}, upsert=True)

async def safe_send(peer_id: int, method, *args, **kwargs):
    try:
        return await method(peer_id, *args, **kwargs)
    except FloodWait as e:
        await asyncio.sleep(e.x)
        return await safe_send(peer_id, method, *args, **kwargs)
    except RPCError:
        return None
    except Exception:
        return None

def start_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Support", url=SUPPORT_CHAT),
         InlineKeyboardButton("Source", url="https://github.com/Shauryanoobhai/EditGuardianBot")],
        [InlineKeyboardButton("Add to Group", url=f"https://t.me/{BOT_USERNAME}?startgroup=true"),
         InlineKeyboardButton("Owner", url=f"https://t.me/TheErenYeager")]
    ])

def help_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Contact Owner", url=f"https://t.me/TheErenYeager")],
        [InlineKeyboardButton("Support", url=SUPPORT_CHAT)]
    ])

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user = message.from_user
    await add_user_record(user)
    await log_event("user_started", {"user_id": user.id, "name": user.first_name, "username": user.username})
    await client.send_photo(
        message.chat.id,
        START_IMG,
        caption=f"Hello {user.mention}, I'm your Edit Guardian Bot.\n\n"
                "I remove edited messages in groups and keep clean logs.\n\n"
                "• Clean moderation\n• Persistent logs\n• Owner & sudo controls\n\nUse /help for commands.",
        reply_markup=start_keyboard()
    )
    try:
        await client.send_message(
            LOGGER_ID,
            f"📥 New user started bot\n• {user.mention}\n• ID: `{user.id}`\n• @{user.username or 'no-username'}\n• {datetime.utcnow()}",
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass

@bot.on_message(filters.command("help"))
async def help_cmd(client, message):
    text = (
        "Commands\n\n"
        "/ping — check latency and quick stats\n"
        "/stats — bot stats (owner/sudo)\n"
        "/logs — recent logs (owner/sudo)\n"
        "/broadcast reply — broadcast a replied message (owner/sudo)\n"
        "/broadcast_text <type> <text> — broadcast raw text, type: users|groups|all (owner/sudo)\n"
        "/addsudo <user_id> — add sudo (owner only)\n"
        "/remsudo <user_id> — remove sudo (owner only)\n"
        "/sudolist — list sudo users\n"
    )
    await message.reply_text(text, reply_markup=help_keyboard())

@bot.on_message(filters.command("ping"))
async def ping_cmd(client, message):
    start = datetime.utcnow()
    sent = await message.reply_text("Pinging...")
    elapsed = (datetime.utcnow() - start).total_seconds() * 1000
    await sent.edit_text(
        f"🏓 Pong\nLatency: `{int(elapsed)}ms`\n\n"
        f"Users tracked: `{await users_col.count_documents({})}`\n"
        f"Groups tracked: `{await groups_col.count_documents({})}`",
        parse_mode=enums.ParseMode.MARKDOWN
    )

@bot.on_message(filters.command("addsudo") & filters.user(OWNER_ID))
async def addsudo_cmd(client, message):
    parts = message.text.split()
    if len(parts) < 2: return await message.reply_text("Usage: /addsudo <user_id>")
    try:
        uid = int(parts[1])
        if await sudo_col.find_one({"user_id": uid}):
            return await message.reply_text("Already a sudo user.")
        await sudo_col.insert_one({"user_id": uid, "added_by": message.from_user.id, "added_on": datetime.utcnow()})
        await log_event("add_sudo", {"by": message.from_user.id, "user_id": uid})
        await message.reply_text(f"Added sudo: `{uid}`", parse_mode=enums.ParseMode.MARKDOWN)
    except ValueError:
        await message.reply_text("User id must be integer.")

@bot.on_message(filters.command("remsudo") & filters.user(OWNER_ID))
async def remsudo_cmd(client, message):
    parts = message.text.split()
    if len(parts) < 2: return await message.reply_text("Usage: /remsudo <user_id>")
    try:
        uid = int(parts[1])
        res = await sudo_col.delete_one({"user_id": uid})
        if res.deleted_count:
            await log_event("remove_sudo", {"by": message.from_user.id, "user_id": uid})
            await message.reply_text(f"Removed sudo: `{uid}`", parse_mode=enums.ParseMode.MARKDOWN)
        else:
            await message.reply_text("User not found in sudo list.")
    except ValueError:
        await message.reply_text("User id must be integer.")

@bot.on_message(filters.command("sudolist"))
async def sudolist_cmd(client, message):
    cursor = sudo_col.find({})
    lines = []
    async for d in cursor:
        lines.append(f"• `{d['user_id']}`")
    if not lines:
        return await message.reply_text("No sudo users.")
    await message.reply_text("Sudo users:\n" + "\n".join(lines), parse_mode=enums.ParseMode.MARKDOWN)

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
            except:
                failed += 1

    tasks = [asyncio.create_task(send_to(t)) for t in set(targets)]
    total = len(tasks)
    await asyncio.gather(*tasks)
    return total, sent, failed

@bot.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_reply_cmd(client, message):
    if not await is_sudo(message.from_user.id): return await message.reply_text("Unauthorized.")
    if not message.reply_to_message: return await message.reply_text("Reply to a message to broadcast it.")
    users = [u["user_id"] async for u in users_col.find({}, {"user_id":1})]
    groups = [g["chat_id"] async for g in groups_col.find({}, {"chat_id":1})]
    targets = users + groups
    status = await message.reply_text("Broadcasting...")
    total, sent, failed = await broadcast_message(client, targets, "reply", message_obj=message.reply_to_message)
    await broadcasts_col.insert_one({"by": message.from_user.id, "type": "reply_broadcast", "attempted": total, "sent": sent, "failed": failed, "time": datetime.utcnow()})
    await log_event("broadcast", {"by": message.from_user.id, "attempted": total, "sent": sent, "failed": failed})
    await status.edit_text(f"Broadcast done. Attempted: {total}, Sent: {sent}, Failed: {failed}")

@bot.on_message(filters.command("broadcast_text"))
async def broadcast_text_cmd(client, message):
    if not await is_sudo(message.from_user.id): return await message.reply_text("Unauthorized.")
    parts = message.text.split(None, 2)
    if len(parts) < 3: return await message.reply_text("Usage: /broadcast_text <users|groups|all> <text>")
    target_type = parts[1].lower()
    text = parts[2]
    targets = []
    if target_type in ("users","all"): targets += [u["user_id"] async for u in users_col.find({}, {"user_id":1})]
    if target_type in ("groups","all"): targets += [g["chat_id"] async for g in groups_col.find({}, {"chat_id":1})]
    status = await message.reply_text(f"Broadcasting to {len(targets)} targets...")
    total, sent, failed = await broadcast_message(client, targets, "text", text=text)
    await broadcasts_col.insert_one({"by": message.from_user.id, "type": "text_broadcast", "target": target_type, "attempted": total, "sent": sent, "failed": failed, "time": datetime.utcnow()})
    await log_event("broadcast_text", {"by": message.from_user.id, "target": target_type, "attempted": total, "sent": sent, "failed": failed})
    await status.edit_text(f"Done. Attempted: {total}, Sent: {sent}, Failed: {failed}")

@bot.on_message(filters.command("stats"))
async def stats_cmd(client, message):
    if not await is_sudo(message.from_user.id): return await message.reply_text("Unauthorized.")
    users_count = await users_col.count_documents({})
    groups_count = await groups_col.count_documents({})
    logs_count = await logs_col.count_documents({})
    broadcasts_count = await broadcasts_col.count_documents({})
    deleted_edits = (await stats_col.find_one({"_id": "deleted_edits"})) or {"value": 0}
    text = (
        f"📊 Bot Statistics\n\n"
        f"Users: `{users_count}`\n"
        f"Groups: `{groups_count}`\n"
        f"Logs: `{logs_count}`\n"
        f"Broadcasts: `{broadcasts_count}`\n"
        f"Edited messages deleted: `{deleted_edits.get('value', 0)}`\n"
    )
    await message.reply_text(text, parse_mode=enums.ParseMode.MARKDOWN)

@bot.on_message(filters.command("logs"))
async def logs_cmd(client, message):
    if not await is_sudo(message.from_user.id): return await message.reply_text("Unauthorized.")
    cursor = logs_col.find().sort("time", -1).limit(20)
    lines = []
    async for d in cursor:
        t = d.get("time").strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{t} | {d.get('kind')} | {d.get('payload')}")
    if not lines: return await message.reply_text("No logs.")
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > 4000:
            await message.reply_text(f"```\n{chunk}\n```", parse_mode=enums.ParseMode.MARKDOWN)
            chunk = line + "\n"
        else:
            chunk += line + "\n"
    if chunk: await message.reply_text(f"```\n{chunk}\n```", parse_mode=enums.ParseMode.MARKDOWN)

@bot.on_edited_message(filters.group)
async def edited_handler(client, message):
    user = message.from_user
    if not user or await is_sudo(user.id): return
    now = datetime.utcnow()
    last_alert = edit_alert_cache.get(user.id)
    if last_alert and (now - last_alert).total_seconds() < 5: return
    edit_alert_cache[user.id] = now
    text_preview = message.text or "<media>"
    await log_event("edited_deleted", {"chat_id": message.chat.id, "user_id": user.id, "preview": text_preview})
    await increment_stat("deleted_edits", 1)
    try:
        await message.delete()
        alert = await client.send_message(message.chat.id, f"{user.first_name} edited a message and it was removed.")
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
            await log_event("bot_added_to_group", {"chat_id": message.chat.id, "title": message.chat.title})
            try:
                await client.send_message(LOGGER_ID, f"➕ Added to group: {message.chat.title} ({message.chat.id})")
            except Exception:
                pass

bot.run()
