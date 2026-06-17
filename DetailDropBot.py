#!/usr/bin/env python3
"""
DetailDrop Telegram Bot
Multi-source intelligence search bot - Uniform Format v3.0
"""

import requests
import socket

# Force IPv4 to prevent IPv6 connection timeouts (common in environments with broken IPv6 routes)
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    args_list = list(args)
    if len(args_list) >= 3:
        args_list[2] = socket.AF_INET
    else:
        kwargs['family'] = socket.AF_INET
    return old_getaddrinfo(*args_list, **kwargs)
socket.getaddrinfo = new_getaddrinfo

import json
import logging
import re
import asyncio
import html
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
import dns.resolver
resolver = dns.resolver.Resolver(configure=False)
resolver.nameservers = ['2001:4860:4860::8888', '2001:4860:4860::8844', '8.8.8.8', '8.8.4.4']
dns.resolver.default_resolver = resolver
import pymongo
import psutil

# Startup time and API Status cache
STARTUP_TIME = datetime.utcnow()
API_STATUSES = {
    "mobile": "🟢",
    "pan": "🟢",
    "vehicle1": "🟢",
    "vehicle2": "🟢",
    "leak": "🟢",
    "github": "🟢"
}

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8683454343:AAEX46N64eLaD4ZFJDCVRTjeS6xeRSE31FU")

# API URLs
MOBILE_API = "https://numberto-info-noobster.com-dashbord63hh7qe4.workers.dev/?number={}"
VEHICLE_API_1 = "https://vehicleto-adavanceinfo-noobster.com-dashbord63hh7qe4.workers.dev/?rc={}"
VEHICLE_API_2 = "https://vehicle-api-pkbw.onrender.com/api/rc?vehicle_no={}"
PAN_API = "https://pan-info-api-1098.onrender.com/pan={}"
LEAK_API = "https://lynn-tracker-ref-contained.trycloudflare.com/leak={}"
GITHUB_API = "https://api.github.com/users/{}"

# Conversation states
WAITING_MOBILE = 2
WAITING_VEHICLE = 3
WAITING_PAN = 4
WAITING_GITHUB = 5
WAITING_LEAK = 6

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== MONGODB & ACCESS CONFIG ====================
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://TGHostingManagerBot:Z15kgFLgaOLUA84a@tghostingmanagerbot.pz1om5f.mongodb.net/")
ADMIN_IDS = [8464435078]
ADMIN_USERNAME = "NeoVirtuosa"

# ==================== FORCE JOIN CONFIG ====================
FORCE_JOIN_GROUP_ID = -1003987947941
FORCE_JOIN_GROUP_LINK = "https://t.me/DetailDropGroup"
FORCE_JOIN_CHANNEL_ID = -1003718462382
FORCE_JOIN_CHANNEL_LINK = "https://t.me/DetailDrop"

FORCE_JOIN_TEXT = """📢 <b>Connect to our Community</b>
━━━━━━━━━━━━━━━━━━━━
Join our channels below to unlock search database access, get server status reports, and receive the latest cyber-intelligence updates."""

def get_force_join_keyboard():
    keyboard = [
        [InlineKeyboardButton("💬 Join Group", url=FORCE_JOIN_GROUP_LINK),
         InlineKeyboardButton("📢 Join Channel", url=FORCE_JOIN_CHANNEL_LINK)],
        [InlineKeyboardButton("🔄 Verify Membership", callback_data="verify_force_join")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def check_force_join_status(user_id: int, bot) -> tuple[bool, str]:
    """Verify membership details and return (is_joined, missing_chat_type)"""
    if user_id in ADMIN_IDS:
        return True, ""
        
    group_joined = True
    try:
        member = await bot.get_chat_member(chat_id=FORCE_JOIN_GROUP_ID, user_id=user_id)
        if member.status not in ['member', 'restricted', 'administrator', 'creator']:
            group_joined = False
    except Exception as e:
        logger.error(f"Error checking group membership for {user_id}: {e}")
        group_joined = False
        
    channel_joined = True
    try:
        member = await bot.get_chat_member(chat_id=FORCE_JOIN_CHANNEL_ID, user_id=user_id)
        if member.status not in ['member', 'restricted', 'administrator', 'creator']:
            channel_joined = False
    except Exception as e:
        logger.error(f"Error checking channel membership for {user_id}: {e}")
        channel_joined = False
        
    if group_joined and channel_joined:
        return True, ""
    elif not group_joined and not channel_joined:
        return False, "both"
    elif not group_joined:
        return False, "group"
    else:
        return False, "channel"

async def check_force_join(user_id: int, bot) -> bool:
    """Verify if user has joined both networks (bool return for compatibility)"""
    joined, _ = await check_force_join_status(user_id, bot)
    return joined

def private_chat_only(func):
    """Decorator to restrict handler execution strictly to private chats (DMs), except for bot admins"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user and user.id in ADMIN_IDS:
            return await func(update, context)
            
        if update.effective_chat and update.effective_chat.type != 'private':
            return
        return await func(update, context)
    return wrapper

try:
    mongo_client = pymongo.MongoClient(MONGO_URI)
    db = mongo_client["DetailDropBotDB"]
    db.users.create_index("user_id", unique=True)
    db.promocodes.create_index("code", unique=True)
    
    # Initialize settings if not exists
    settings_doc = db.settings.find_one({"_id": "global_settings"})
    if not settings_doc:
        db.settings.insert_one({
            "_id": "global_settings",
            "maintenance_mode": False,
            "total_queries": 0
        })
    logger.info("MongoDB connected successfully!")
except Exception as e:
    logger.critical(f"Failed to connect to MongoDB: {e}")
    raise e

def register_user(user, ref_id=None):
    """Register a new user in MongoDB database"""
    user_id = user.id
    user_data = db.users.find_one({"user_id": user_id})
    if not user_data:
        joined_at = datetime.utcnow()
        pass_expiry = joined_at + timedelta(days=1) # 1-day free pass
        user_data = {
            "user_id": user_id,
            "first_name": user.first_name,
            "username": user.username,
            "joined_at": joined_at,
            "pass_expiry": pass_expiry,
            "credits": 10,
            "referred_by": ref_id,
            "total_referred": 0,
            "banned": False,
            "last_checkin": None,
            "queries_count": 0,
            "last_active": joined_at
        }
        db.users.insert_one(user_data)
        logger.info(f"Registered new user: {user_id} (Referrer: {ref_id})")
    return user_data

def get_pass_time_left(user_data):
    """Get remaining seconds for user's time-based pass"""
    if not user_data:
        return 0
    pass_expiry = user_data.get('pass_expiry')
    if not pass_expiry:
        # Fallback to calculating from joined_at for legacy users
        joined_at = user_data.get('joined_at')
        if not joined_at:
            return 0
        if joined_at.tzinfo is not None:
            joined_at = joined_at.astimezone(timezone.utc).replace(tzinfo=None)
        elapsed = datetime.utcnow() - joined_at
        time_left = 3600 - elapsed.total_seconds()
        return max(0, int(time_left))
        
    if pass_expiry.tzinfo is not None:
        pass_expiry = pass_expiry.astimezone(timezone.utc).replace(tzinfo=None)
    time_left = pass_expiry - datetime.utcnow()
    return max(0, int(time_left.total_seconds()))

def has_user_access_only(user_id):
    """Check if user has active pass or >= 1 credit without deducting it"""
    if user_id in ADMIN_IDS:
        return True
    user_data = db.users.find_one({"user_id": user_id})
    if not user_data:
        return True # Will register on query
    if user_data.get('banned', False):
        return False
    time_left = get_pass_time_left(user_data)
    if time_left > 0:
        return True
    return user_data.get('credits', 0) >= 1

def record_query_activity(query_type=None):
    """Update global settings with total, daily, and type-based query stats"""
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    settings_doc = db.settings.find_one({"_id": "global_settings"})
    last_query_date = settings_doc.get("last_query_date") if settings_doc else None
    
    inc_dict = {"total_queries": 1}
    set_dict = {"last_active": datetime.utcnow()}
    
    if last_query_date == today_str:
        inc_dict["queries_today"] = 1
    else:
        set_dict["queries_today"] = 1
        set_dict["last_query_date"] = today_str
        
    if query_type:
        inc_dict[f"queries_by_type.{query_type}"] = 1
        
    db.settings.update_one(
        {"_id": "global_settings"},
        {"$inc": inc_dict, "$set": set_dict},
        upsert=True
    )

async def check_user_access(user, context: ContextTypes.DEFAULT_TYPE, deduct_credit: bool = True, query_type: str = None) -> tuple[bool, bool, str, InlineKeyboardMarkup]:
    """Check if the user has an active free pass or has credit, checking ban and maintenance status first. Returns (allowed, masked, error_msg, reply_markup)"""
    user_id = user.id
    user_data = db.users.find_one({"user_id": user_id})

    # Admin has absolute access & bypasses all checks immediately
    if user_id in ADMIN_IDS:
        if deduct_credit:
            record_query_activity(query_type)
            if user_data:
                db.users.update_one({"user_id": user_id}, {"$inc": {"queries_count": 1}, "$set": {"last_active": datetime.utcnow()}})
        return True, False, "", None
        
    # 1. Ban Check
    if user_data and user_data.get('banned', False):
        return False, False, "❌ <b>Your account has been banned by the Administrator.</b>", None
        
    # 2. Maintenance Mode Check
    settings_doc = db.settings.find_one({"_id": "global_settings"})
    is_maintenance = settings_doc.get('maintenance_mode', False) if settings_doc else False
    if is_maintenance:
        return False, False, "🔧 <b>Maintenance Mode Active:</b> The bot is temporarily undergoing scheduled updates. Please try again later.", None
        
    # 3. Force Join Check
    joined = await check_force_join(user_id, context.bot)
    if not joined:
        return False, False, FORCE_JOIN_TEXT, get_force_join_keyboard()
        
    if not user_data:
        user_data = register_user(user)
    else:
        db.users.update_one({"user_id": user_id}, {"$set": {"last_active": datetime.utcnow()}})
        
    if not deduct_credit:
        time_left = get_pass_time_left(user_data)
        if time_left > 0:
            return True, False, "", None
        credits = user_data.get('credits', 0)
        if credits >= 1:
            return True, False, "", None
        return True, True, "", None

    # Increment queries count for successful attempt
    record_query_activity(query_type)
    db.users.update_one({"user_id": user_id}, {"$inc": {"queries_count": 1}})
        
    time_left = get_pass_time_left(user_data)
    if time_left > 0:
        return True, False, "", None
        
    credits = user_data.get('credits', 0)
    if credits >= 1:
        # Deduct 1 credit
        db.users.update_one({"user_id": user_id}, {"$inc": {"credits": -1}})
        logger.info(f"Deducted 1 credit from user {user_id}. Remaining: {credits - 1}")
        return True, False, "", None
        
    # No credits -> allow access but mark results as MASKED
    return True, True, "", None

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_data = db.users.find_one({"user_id": user_id})
    if not user_data:
        user_data = register_user(user)
    
    referrals = user_data.get('total_referred', 0)
    
    if user_id in ADMIN_IDS:
        profile_text = f"""👤 <b>ADMIN PROFILE</b>
━━━━━━━━━━━━━━━━━━━━
🆔 <b>Admin ID:</b> <code>{user_id}</code>
👑 <b>Role:</b> <code>System Administrator</code>
💰 <b>Credit Balance:</b> <code>♾️</code>
⏳ <b>Bypass Status:</b> <code>Active</code>
━━━━━━━━━━━━━━━━━━━━
💡 <i>You have system bypass and infinite credits enabled. Use the Admin Panel button below to manage users and view statistics.</i>"""
        keyboard = [
            [InlineKeyboardButton("📊 Admin Panel", callback_data="admin_panel")],
            [InlineKeyboardButton("🔙 Back to Home", callback_data="start")]
        ]
    else:
        credits = user_data.get('credits', 0)
        time_left = get_pass_time_left(user_data)
        if time_left > 0:
            if time_left >= 86400:
                status_str = f"Active ✅ ({time_left // 86400}d {(time_left % 86400) // 3600}h left)"
            else:
                status_str = f"Active ✅ ({time_left // 3600}h {(time_left % 3600) // 60}m left)"
        else:
            status_str = "Expired / Inactive ❌"
            
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        profile_text = f"""👤 <b>USER PROFILE</b>
━━━━━━━━━━━━━━━━━━━━
👤 <b>Name:</b> {escape_html(user.first_name)}
🔑 <b>Username:</b> @{escape_html(user.username) if user.username else 'N/A'}
🆔 <b>User ID:</b> <code>{user_id}</code>

💰 <b>ACCOUNT STATUS</b>
━━━━━━━━━━━━━━━━━━━━
💵 <b>Credit Balance:</b> <code>{credits} credits</code>
⏳ <b>Time Pass Status:</b> {status_str}
 
👥 <b>REFERRAL SYSTEM</b>
━━━━━━━━━━━━━━━━━━━━
📊 <b>Invite Stats:</b>
• Friends Referred: <code>{referrals} users</code>
• Credits Earned: <code>+{referrals * 2} credits</code>
 
🔗 <b>Your Referral Link:</b>
<code>{ref_link}</code>
━━━━━━━━━━━━━━━━━━━━
💡 <i>Share your invite link above. You will instantly earn <b>+2 credits</b> for every friend who joins!</i>"""
        keyboard = [
            [InlineKeyboardButton("💳 Buy Credits", callback_data="buy_credits")],
            [InlineKeyboardButton("🔙 Back to Home", callback_data="start")]
        ]
    
    query = update.callback_query
    if query:
        await query.edit_message_text(profile_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        await update.effective_message.reply_text(profile_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def show_buy_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        buy_text = f"""👑 <b>ADMIN BYPASS ACTIVE</b>
━━━━━━━━━━━━━━━━━━━━
⚠️ You are an administrator and have <b>infinite credits</b>.

🛠️ <b>Credit Management:</b>
• Add credits: <code>/addcredit &lt;user_id&gt; &lt;amount&gt;</code>
• Remove credits: <code>/removecredit &lt;user_id&gt; &lt;amount&gt;</code>

⚡ <b>Time Pass Management:</b>
• Add Pass (Hours): <code>/addpass &lt;user_id&gt; &lt;hours&gt;</code>
• Add Pass (Days): <code>/addpassdays &lt;user_id&gt; &lt;days&gt;</code>
━━━━━━━━━━━━━━━━━━━━"""
        keyboard = [
            [InlineKeyboardButton("📊 Admin Panel", callback_data="admin_panel")],
            [InlineKeyboardButton("🔙 Back to Home", callback_data="start")]
        ]
    else:
        text_template = f"Hi! I want to buy a Time Pass for DetailDropBot. My User ID is {user_id}"
        import urllib.parse
        encoded_text = urllib.parse.quote(text_template)
        admin_link = f"https://t.me/{ADMIN_USERNAME}?text={encoded_text}"
        
        buy_text = f"""💳 <b>BUY TIME PASSES</b>
━━━━━━━━━━━━━━━━━━━━
Get a Time Pass to continue searching bank, vehicle, mobile, pan, leak, and github details with **unlimited queries**!

🏷️ <b>Pricing Packages:</b>
• ⚡ <b>Flash Pass (1 Hour):</b> ₹15
• 📅 <b>Day Pass (24 Hours):</b> ₹29
• 🛡️ <b>Weekly Pass (7 Days):</b> ₹79
• 👑 <b>VIP Month Pass (30 Days):</b> ₹199

🛒 <b>How to Buy:</b>
Click the button below to message the admin (<b>@{ADMIN_USERNAME}</b>) directly. You will be redirected with your User ID pre-filled.
━━━━━━━━━━━━━━━━━━━━"""
        keyboard = [
            [InlineKeyboardButton("💬 Message Admin to Buy", url=admin_link)],
            [InlineKeyboardButton("👤 View Profile", callback_data="profile")],
            [InlineKeyboardButton("🔙 Back to Home", callback_data="start")]
        ]
        
    query = update.callback_query
    if query:
        await query.edit_message_text(buy_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        await update.effective_message.reply_text(buy_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        query = update.callback_query
        if query:
            await query.answer()
            await send_temp_message(context, user_id, "❌ <b>Unauthorized:</b> This command is only for admins.")
        else:
            await update.effective_message.reply_text("❌ <b>Unauthorized:</b> This command is only for admins.", parse_mode='HTML')
        return
        
    now = datetime.utcnow()
    
    # 1. User counters
    total_users = db.users.count_documents({})
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    new_users_today = db.users.count_documents({"joined_at": {"$gte": today_start}})
    
    premium_users = db.users.count_documents({"pass_expiry": {"$gt": now}})
    banned_users = db.users.count_documents({"banned": True})
    
    # 2. Credits in circulation
    credits_pipeline = [{"$group": {"_id": None, "total": {"$sum": "$credits"}}}]
    credits_result = list(db.users.aggregate(credits_pipeline))
    total_credits = credits_result[0]["total"] if credits_result else 0
    
    # 3. Community growth
    referrals_pipeline = [{"$group": {"_id": None, "total": {"$sum": "$total_referred"}}}]
    referrals_result = list(db.users.aggregate(referrals_pipeline))
    total_referrals = referrals_result[0]["total"] if referrals_result else 0
    
    top_referrer_doc = db.users.find_one({"total_referred": {"$gt": 0}}, sort=[("total_referred", -1)])
    if top_referrer_doc:
        top_ref_name = f"@{top_referrer_doc.get('username')}" if top_referrer_doc.get('username') else top_referrer_doc.get('first_name')
        top_referrer = f"{top_ref_name} ({top_referrer_doc.get('total_referred')} joins)"
    else:
        top_referrer = "N/A"
        
    last_active_doc = db.users.find_one({"last_active": {"$ne": None}}, sort=[("last_active", -1)])
    if last_active_doc:
        last_active_time = last_active_doc.get('last_active')
        if last_active_time.tzinfo is not None:
            last_active_time = last_active_time.replace(tzinfo=None)
        elapsed_sec = (now - last_active_time).total_seconds()
        if elapsed_sec < 60:
            elapsed_str = f"{int(elapsed_sec)}s ago"
        elif elapsed_sec < 3600:
            elapsed_str = f"{int(elapsed_sec // 60)}m ago"
        else:
            elapsed_str = f"{int(elapsed_sec // 3600)}h ago"
        last_active_name = f"@{last_active_doc.get('username')}" if last_active_doc.get('username') else last_active_doc.get('first_name')
        last_activity = f"{last_active_name} ({elapsed_str})"
    else:
        last_activity = "N/A"
        
    # 4. Search popularity & Global settings
    settings_doc = db.settings.find_one({"_id": "global_settings"})
    if not settings_doc:
        settings_doc = {
            "maintenance_mode": False,
            "total_queries": 0,
            "queries_today": 0,
            "queries_by_type": {}
        }
    is_maintenance = settings_doc.get('maintenance_mode', False)
    total_queries = settings_doc.get('total_queries', 0)
    queries_today = settings_doc.get('queries_today', 0)
    
    last_query_date = settings_doc.get("last_query_date")
    today_str = now.strftime("%Y-%m-%d")
    if last_query_date != today_str:
        queries_today = 0
        
    queries_by_type = settings_doc.get('queries_by_type', {})
    mobile_count = queries_by_type.get('mobile', 0)
    vehicle_count = queries_by_type.get('vehicle1', 0) + queries_by_type.get('vehicle2', 0)
    pan_count = queries_by_type.get('pan', 0)
    leak_count = queries_by_type.get('leak', 0)
    github_count = queries_by_type.get('github', 0)
    
    pop_list = [
        ("📱 Mobile", mobile_count),
        ("🚗 Vehicle", vehicle_count),
        ("📄 PAN", pan_count),
        ("🕵️ Leak", leak_count),
        ("💻 GitHub", github_count)
    ]
    pop_list.sort(key=lambda x: x[1], reverse=True)
    popularity_str = " > ".join([f"{name} ({count})" for name, count in pop_list])
    
    # 5. Active passes breakdown
    pass_users = db.users.find({"pass_expiry": {"$gt": now}})
    pass_1h = 0
    pass_24h = 0
    pass_7d = 0
    pass_30d = 0
    for u in pass_users:
        expiry = u.get('pass_expiry')
        if expiry:
            if expiry.tzinfo is not None:
                expiry = expiry.replace(tzinfo=None)
            rem_h = (expiry - now).total_seconds() / 3600.0
            if rem_h <= 1.0:
                pass_1h += 1
            elif rem_h <= 24.0:
                pass_24h += 1
            elif rem_h <= 168.0:
                pass_7d += 1
            else:
                pass_30d += 1
                
    # 6. Pending support tickets
    pending_tickets = db.tickets.count_documents({"status": "pending"})
    
    # 7. Server CPU & RAM
    try:
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent
    except Exception:
        cpu_usage = 0
        ram_usage = 0
        
    # 8. Bot Uptime
    uptime = now - STARTUP_TIME
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    uptime_parts = []
    if days > 0:
        uptime_parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        uptime_parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0 or not uptime_parts:
        uptime_parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    uptime_str = ", ".join(uptime_parts)
    
    maintenance_status = "🟢 <b>INACTIVE</b>" if not is_maintenance else "🔴 <b>ACTIVE (Admins Only)</b>"
    
    admin_text = f"""📊 <b>SYSTEM STATISTICS</b>
━━━━━━━━━━━━━━━━━━━━
👥 <b>Total Users:</b> <code>{total_users}</code> (+{new_users_today} today)
👑 <b>Premium Users:</b> <code>{premium_users}</code> | 🚫 <b>Banned:</b> <code>{banned_users}</code>
🔍 <b>Total Queries Run:</b> <code>{total_queries}</code> ({queries_today} today)
💳 <b>Credits in Circulation:</b> <code>{total_credits}</code>

📈 <b>COMMUNITY GROWTH:</b>
• 👥 <b>Total Referrals:</b> <code>{total_referrals} joins</code>
• 🏆 <b>Top Referrer:</b> <code>{top_referrer}</code>
• 🕒 <b>Last Activity:</b> <code>{last_activity}</code>

🔥 <b>SEARCH POPULARITY:</b>
• <code>{popularity_str}</code>

⏳ <b>ACTIVE PASSES:</b>
• ⚡ 1h: <code>{pass_1h}</code> | 📅 24h: <code>{pass_24h}</code> | 🛡️ 7d: <code>{pass_7d}</code> | 👑 30d: <code>{pass_30d}</code>

📩 <b>OUTSTANDING TICKETS:</b>
• 🎫 <b>Pending Support:</b> <code>{pending_tickets} tickets</code> {"⚠️" if pending_tickets > 0 else ""}

🔌 <b>API STATUS:</b>
• 📱 Mobile: {API_STATUSES.get('mobile', '🟢')} | 📄 PAN: {API_STATUSES.get('pan', '🟢')}
• 🚗 Vehicle 1: {API_STATUSES.get('vehicle1', '🟢')} | 🚙 Vehicle 2: {API_STATUSES.get('vehicle2', '🟢')} | 🕵️ Leak: {API_STATUSES.get('leak', '🟢')}

⚡ <b>SYSTEM INFO:</b>
• 🔧 <b>Maintenance:</b> {maintenance_status}
• 🖥️ <b>Server CPU:</b> <code>{cpu_usage}%</code> | 💾 <b>RAM:</b> <code>{ram_usage}%</code>
• ⏱️ <b>Bot Uptime:</b> <code>{uptime_str}</code>
━━━━━━━━━━━━━━━━━━━━

📝 <b>Quick Commands:</b>
• Add credits: <code>/addcredit &lt;user_id&gt; &lt;amount&gt;</code>
• Remove credits: <code>/removecredit &lt;user_id&gt; &lt;amount&gt;</code>
• User info: <code>/userinfo &lt;user_id&gt;</code>
• Ban User: <code>/ban &lt;user_id&gt;</code>
• Unban User: <code>/unban &lt;user_id&gt;</code>
• Gen Promo Code: <code>/genpromo &lt;code&gt; &lt;credits&gt; &lt;max_uses&gt;</code>
• Support Reply: <code>/reply &lt;user_id&gt; &lt;message&gt;</code>
━━━━━━━━━━━━━━━━━━━━"""
    
    maint_btn_text = "🔧 Enable Maintenance" if not is_maintenance else "🔧 Disable Maintenance"
    
    keyboard = [
        [InlineKeyboardButton("📊 Refresh Stats", callback_data="admin_refresh")],
        [InlineKeyboardButton("🔌 API Health Manager", callback_data="admin_api_health")],
        [InlineKeyboardButton(maint_btn_text, callback_data="admin_toggle_maint")],
        [InlineKeyboardButton("📢 Send Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 Back to Start", callback_data="start")]
    ]
    
    query = update.callback_query
    if query:
        from telegram.error import BadRequest
        try:
            await query.edit_message_text(admin_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            await query.answer()
            await send_temp_message(context, user_id, "✅ <b>Stats Refreshed Successfully!</b>")
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await query.answer()
                await send_temp_message(context, user_id, "ℹ️ <b>Stats are already up to date!</b>")
            else:
                try:
                    await query.answer()
                except Exception:
                    pass
                raise e
    else:
        await update.effective_message.reply_text(admin_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_admin_panel(update, context)

async def addcredit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addcredit <user_id> <amount>", parse_mode='HTML')
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Error: User ID and Amount must be numbers.", parse_mode='HTML')
        return
        
    res = db.users.update_one({"user_id": target_id}, {"$inc": {"credits": amount}})
    if res.matched_count > 0:
        await update.message.reply_text(f"✅ Successfully added <b>{amount} credits</b> to User ID <code>{target_id}</code>.", parse_mode='HTML')
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎁 <b>Credits Added!</b>\n━━━━━━━━━━━━━━━━━━━━\nAdmin has added <b>{amount} credits</b> to your account.\n💰 Use /profile to view your balance.",
                parse_mode='HTML'
            )
        except Exception:
            pass
    else:
        await update.message.reply_text("❌ User not found in database.", parse_mode='HTML')

async def removecredit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /removecredit <user_id> <amount>", parse_mode='HTML')
        return
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Error: User ID and Amount must be numbers.", parse_mode='HTML')
        return
        
    res = db.users.update_one({"user_id": target_id}, {"$inc": {"credits": -amount}})
    if res.matched_count > 0:
        target = db.users.find_one({"user_id": target_id})
        new_balance = target.get('credits', 0)
        await update.message.reply_text(f"✅ Successfully removed <b>{amount} credits</b> from User ID <code>{target_id}</code>. New balance: <code>{new_balance}</code>.", parse_mode='HTML')
    else:
        await update.message.reply_text("❌ User not found in database.", parse_mode='HTML')

async def userinfo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("Usage: /userinfo <user_id>", parse_mode='HTML')
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Error: User ID must be a number.", parse_mode='HTML')
        return
        
    target = db.users.find_one({"user_id": target_id})
    if not target:
        await update.message.reply_text("❌ User not found in database.", parse_mode='HTML')
        return
        
    time_left = get_pass_time_left(target)
    if time_left > 0:
        if time_left >= 86400:
            status_str = f"Active ({time_left // 86400}d {(time_left % 86400) // 3600}h left)"
        else:
            status_str = f"Active ({time_left // 3600}h {(time_left % 3600) // 60}m left)"
    else:
        status_str = "Expired"
        
    info_text = f"""👤 <b>USER DETAILS</b>
━━━━━━━━━━━━━━━━━━━━
🆔 <b>User ID:</b> <code>{target['user_id']}</code>
👤 <b>First Name:</b> {escape_html(target.get('first_name'))}
🔑 <b>Username:</b> @{escape_html(target.get('username')) if target.get('username') else 'N/A'}
⏳ <b>Time Pass:</b> {status_str}
💰 <b>Credits:</b> <code>{target.get('credits', 0)}</code>
👥 <b>Total Referred:</b> <code>{target.get('total_referred', 0)}</code>
📅 <b>Joined Date:</b> {target.get('joined_at').strftime('%Y-%m-%d %H:%M:%S')} UTC
━━━━━━━━━━━━━━━━━━━━"""
    await update.message.reply_text(info_text, parse_mode='HTML')

async def addpass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addpass <user_id> <hours>", parse_mode='HTML')
        return
    try:
        target_id = int(context.args[0])
        hours = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Error: User ID and Hours must be integers.", parse_mode='HTML')
        return
        
    target = db.users.find_one({"user_id": target_id})
    if not target:
        await update.message.reply_text("❌ User not found in database.", parse_mode='HTML')
        return
        
    now = datetime.utcnow()
    current_expiry = target.get('pass_expiry')
    if current_expiry:
        if current_expiry.tzinfo is not None:
            current_expiry = current_expiry.astimezone(timezone.utc).replace(tzinfo=None)
        start_time = max(current_expiry, now)
    else:
        # Fallback using joined_at
        joined_at = target.get('joined_at')
        if joined_at:
            if joined_at.tzinfo is not None:
                joined_at = joined_at.astimezone(timezone.utc).replace(tzinfo=None)
            legacy_left = 3600 - (now - joined_at).total_seconds()
            if legacy_left > 0:
                start_time = now + timedelta(seconds=legacy_left)
            else:
                start_time = now
        else:
            start_time = now
            
    new_expiry = start_time + timedelta(hours=hours)
    db.users.update_one({"user_id": target_id}, {"$set": {"pass_expiry": new_expiry}})
    
    await update.message.reply_text(
        f"✅ Successfully added <b>{hours} hours</b> of Time Pass to User ID <code>{target_id}</code>.\n"
        f"📅 New Expiry: <code>{new_expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC</code>",
        parse_mode='HTML'
    )
    
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🎁 <b>Time Pass Added!</b>\n━━━━━━━━━━━━━━━━━━━━\nAdmin has added <b>{hours} hours</b> of unlimited OSINT search access to your account.\n⚡ Check /profile to view your pass status.",
            parse_mode='HTML'
        )
    except Exception:
        pass

async def addpassdays_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addpassdays <user_id> <days>", parse_mode='HTML')
        return
    try:
        target_id = int(context.args[0])
        days = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Error: User ID and Days must be integers.", parse_mode='HTML')
        return
        
    target = db.users.find_one({"user_id": target_id})
    if not target:
        await update.message.reply_text("❌ User not found in database.", parse_mode='HTML')
        return
        
    now = datetime.utcnow()
    current_expiry = target.get('pass_expiry')
    if current_expiry:
        if current_expiry.tzinfo is not None:
            current_expiry = current_expiry.astimezone(timezone.utc).replace(tzinfo=None)
        start_time = max(current_expiry, now)
    else:
        # Fallback using joined_at
        joined_at = target.get('joined_at')
        if joined_at:
            if joined_at.tzinfo is not None:
                joined_at = joined_at.astimezone(timezone.utc).replace(tzinfo=None)
            legacy_left = 3600 - (now - joined_at).total_seconds()
            if legacy_left > 0:
                start_time = now + timedelta(seconds=legacy_left)
            else:
                start_time = now
        else:
            start_time = now
            
    new_expiry = start_time + timedelta(days=days)
    db.users.update_one({"user_id": target_id}, {"$set": {"pass_expiry": new_expiry}})
    
    await update.message.reply_text(
        f"✅ Successfully added <b>{days} days</b> of Time Pass to User ID <code>{target_id}</code>.\n"
        f"📅 New Expiry: <code>{new_expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC</code>",
        parse_mode='HTML'
    )
    
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🎁 <b>Time Pass Added!</b>\n━━━━━━━━━━━━━━━━━━━━\nAdmin has added <b>{days} days</b> of unlimited OSINT search access to your account.\n⚡ Check /profile to view your pass status.",
            parse_mode='HTML'
        )
    except Exception:
        pass


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
        
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ <b>Reply Required:</b>\n"
            "To send a broadcast, please <b>reply to the target message</b> (text, image, video, document, etc.) with <code>/broadcast</code>.",
            parse_mode='HTML'
        )
        return
        
    target_msg = update.message.reply_to_message
    users = list(db.users.find({}))
    success = 0
    fail = 0
    
    status_msg = await update.message.reply_text("📢 <b>Sending broadcast...</b>", parse_mode='HTML')
    
    for u in users:
        u_id = u['user_id']
        try:
            # Copy the message exactly, including its original markup (buttons)
            await target_msg.copy(chat_id=u_id, reply_markup=target_msg.reply_markup)
            success += 1
        except Exception:
            fail += 1
            
    await status_msg.edit_text(
        f"📢 <b>Broadcast Completed!</b>\n━━━━━━━━━━━━━━━━━━━━\n✅ <b>Success:</b> <code>{success}</code>\n❌ <b>Failed:</b> <code>{fail}</code>",
        parse_mode='HTML'
    )

# ==================== FORMATTING HELPERS ====================

def escape_html(val):
    """Escape HTML special characters"""
    if val is None:
        return ""
    if not isinstance(val, str):
        val = str(val)
    return html.escape(val)

def safe_get(data, *keys, default='N/A'):
    """Safely get nested dict values"""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return escape_html(default)
    val = data if data is not None else default
    return escape_html(val)

def format_header(emoji, title):
    """Create consistent header"""
    return f"{emoji} <b>{title}</b>\n━━━━━━━━━━━━━━━━━━━━"

def add_field(emoji, label, value, is_code=True):
    """Format a single field consistently and return it with a newline if valid, else return empty string"""
    if value is None:
        return ""
    val_str = str(value).strip()
    if val_str.upper() in ['', 'N/A', 'NA', 'NONE', 'NULL']:
        return ""
    escaped_value = escape_html(val_str)
    if is_code:
        escaped_value = f"<code>{escaped_value}</code>"
    return f"{emoji} <b>{label}:</b> {escaped_value}\n"

def format_separator():
    """Section separator"""
    return "━━━━━━━━━━━━━━━━━━━━"

def format_subseparator():
    """Sub-section separator"""
    return "────────────────────────"

def format_error(title, message):
    """Format error messages"""
    return f"""❌ <b>{title}</b>
{format_separator()}
⚠️ {escape_html(message)}
{format_separator()}"""

def handle_api_exception(name: str, e: Exception) -> str:
    """Helper to convert request/decoding exceptions into user-friendly error text"""
    import requests
    if isinstance(e, requests.exceptions.Timeout):
        return format_error(f"{name} Timeout", "The server took too long to respond. Please try again.")
    elif isinstance(e, requests.exceptions.ConnectionError):
        return format_error(f"{name} Offline", "Unable to establish connection to the database provider.")
    elif isinstance(e, (json.JSONDecodeError, ValueError)):
        return format_error(f"{name} Error", "Received an invalid response format from the database server.")
    return format_error(f"{name} Error", str(e))

async def update_api_status_loop():
    """Periodically check API status in background"""
    await asyncio.sleep(5) # Delay initial check to let bot start smoothly
    apis = {
        "mobile": MOBILE_API.format("9876543210"),
        "vehicle1": VEHICLE_API_1.format("DL3CAS1234"),
        "vehicle2": VEHICLE_API_2.format("DL3CAS1234"),
        "pan": PAN_API.format("ABCDE1234F"),
        "github": GITHUB_API.format("octocat"),
        "leak": LEAK_API.format("test@gmail.com")
    }
    
    async def ping(name, url):
        try:
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(
                None, lambda: requests.get(url, timeout=3)
            )
            if res.status_code < 500:
                return name, "🟢"
            else:
                return name, "🔴"
        except Exception:
            return name, "🔴"

    while True:
        try:
            tasks = [ping(name, url) for name, url in apis.items()]
            results = await asyncio.gather(*tasks)
            for name, status in results:
                API_STATUSES[name] = status
        except Exception as e:
            logger.error(f"Error in background API check: {e}")
        await asyncio.sleep(300)

async def send_temp_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, parse_mode: str = 'HTML', delay: int = 15, reply_markup=None):
    """Sends a message and schedules it to be deleted after `delay` seconds"""
    try:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        # Schedule the deletion task to run in the background
        asyncio.create_task(delete_message_after_delay(context, chat_id, msg.message_id, delay))
        return msg
    except Exception as e:
        logger.error(f"Error sending temporary message: {e}")
        return None

async def delete_message_after_delay(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int):
    """Delays for `delay` seconds, then deletes the specified message"""
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        # Ignore errors if the message was already deleted by the user
        pass

def format_no_results(query):
    """Format no results message"""
    return f"""❌ <b>No Results</b>
{format_separator()}
🔍 <b>Query:</b> <code>{escape_html(query)}</code>
📊 <b>Status:</b> No information found
{format_separator()}
💡 Try another query or check the format"""

def extract_results(data):
    """Extract results from various API response formats"""
    results = []
    
    if isinstance(data, dict):
        if 'data' in data:
            d = data['data']
            if isinstance(d, dict):
                results = d.get('results', [])
                if not results:
                    results = d.get('records', [])
                if not results:
                    for key in ['mobile', 'name', 'email']:
                        if key in d:
                            results = [d]
                            break
            elif isinstance(d, list):
                results = d
        
        if not results and 'results' in data:
            results = data['results']
        
        if not results and 'records' in data:
            results = data['records']
    
    return results if results else []

def mask_val(val, is_phone=False):
    """Mask string values with Unicode block element █, keeping first and last characters for words of length > 2, keeping short words <= 2 visible, and preserving commas."""
    if val is None:
        return ""
    val_str = str(val).strip()
    if not val_str:
        return ""
    if val_str.upper() in ['N/A', 'NA', 'NONE', 'NULL']:
        return val_str
        
    if is_phone:
        alphas = [i for i, c in enumerate(val_str) if c.isalnum()]
        if len(alphas) <= 2:
            chars = list(val_str)
            for idx in alphas:
                chars[idx] = "█"
            return "".join(chars)
        else:
            chars = list(val_str)
            for idx in alphas[1:-1]:
                chars[idx] = "█"
            return "".join(chars)
            
    # Standard string (Names, Addresses, Doc numbers)
    words = val_str.split(" ")
    masked_words = []
    for word in words:
        if not word:
            continue
            
        if word.isdigit() and len(word) == 6:
            masked_words.append("█" * 5 + word[-1])
            continue
            
        if len(word) <= 2:
            masked_words.append(word)
        else:
            word_chars = list(word)
            for idx in range(1, len(word) - 1):
                if word_chars[idx] != ',':
                    word_chars[idx] = '█'
            masked_words.append("".join(word_chars))
            
    return " ".join(masked_words)

def append_lock_message(text):
    """Appends a locking reminder block at the end of the search results"""
    if text and text.startswith("❌"):
        return text
    return text + f"\n\n⚠️ <b>DETAILS MASKED (0 Credits)</b>\n{format_separator()}\n🔒 These details are masked because you have <b>0 credits</b>.\n💰 Buy credits or refer friends to unlock the full details!"

def get_masked_keyboard():
    """Returns the locking keyboard buttons to buy credits or view profile"""
    keyboard = [
        [InlineKeyboardButton("💳 Buy Credits", callback_data="buy_credits")],
        [InlineKeyboardButton("👤 View Profile", callback_data="profile")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def send_formatted_message(update: Update, text: str, msg_to_edit=None, reply_markup=None):
    """Send a message, splitting it safely to not break HTML tags and stay under 4000 chars"""
    if text.startswith("❌") and reply_markup:
        try:
            keyboard = reply_markup.inline_keyboard
            if any(btn.callback_data == 'buy_credits' for row in keyboard for btn in row):
                reply_markup = None
        except Exception:
            pass

    if len(text) <= 4000:
        if msg_to_edit:
            await msg_to_edit.edit_text(text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)
        else:
            await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)
        return

    lines = text.split('\n')
    chunks = []
    current_chunk = []
    current_len = 0
    
    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if current_len + line_len > 4000:
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_len = 0
        current_chunk.append(line)
        current_len += line_len
        
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
        
    if msg_to_edit:
        await msg_to_edit.edit_text(chunks[0], reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)
    else:
        await update.effective_message.reply_text(chunks[0], reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)
        
    for chunk in chunks[1:]:
        await update.effective_message.reply_text(chunk, parse_mode='HTML', disable_web_page_preview=True)

# ==================== SEARCH FUNCTIONS ====================

async def search_mobile_info(number: str, masked: bool = False) -> str:
    """Search mobile number information"""
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: requests.get(MOBILE_API.format(number), timeout=15)
        )
        raw_text = response.text.strip()
        last_brace = raw_text.rfind('}')
        if last_brace != -1:
            raw_text = raw_text[:last_brace + 1]
        data = json.loads(raw_text)
        
        if isinstance(data, dict) and data.get('status') == 'success' and data.get('data', {}).get('records'):
            record = data['data']['records'][0]
            
            result = format_header("📱", "MOBILE NUMBER DETAILS") + "\n"
            result += add_field("📞", "Number", mask_val(data['data'].get('mobile'), is_phone=True) if masked else data['data'].get('mobile'))
            result += add_field("👤", "Name", mask_val(record.get('name')) if masked else record.get('name'), False)
            result += add_field("👨", "Father", mask_val(record.get('father_name')) if masked else record.get('father_name'), False)
            result += add_field("📡", "Circle", mask_val(record.get('circle')) if masked else record.get('circle'), False)
            result += add_field("🔄", "Alternate", mask_val(record.get('alternate_mobile'), is_phone=True) if masked else record.get('alternate_mobile'))
            result += add_field("🆔", "ID", mask_val(record.get('id'), is_phone=True) if masked else record.get('id'))
            
            addr = mask_val(record.get('address')) if masked else record.get('address')
            addr_field = add_field("📍", "Address", addr, False)
            if addr_field:
                result += format_separator() + "\n" + addr_field
            
            return result.strip()
        
        return format_no_results(number)
        
    except Exception as e:
        logger.error(f"Mobile search error: {e}")
        return handle_api_exception("Mobile API", e)

async def search_vehicle_info(rc: str, api_choice: int = 1, masked: bool = False) -> str:
    """Search vehicle registration information"""
    try:
        if api_choice == 1:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: requests.get(VEHICLE_API_1.format(rc), timeout=15)
            )
            data = response.json()
            
            if isinstance(data, dict) and data.get('success') and data.get('vehicle_info'):
                v = data['vehicle_info']
                
                result = format_header("🚗", "VEHICLE DETAILS") + "\n"
                result += add_field("🔢", "RC", mask_val(safe_get(v, 'registration_number'), is_phone=True) if masked else safe_get(v, 'registration_number'))
                
                # Ownership Info
                own = v.get('ownership', {})
                result += add_field("👤", "Owner", mask_val(own.get('owner_name')) if masked else own.get('owner_name'), False)
                result += add_field("👨", "Father", mask_val(own.get('father_name')) if masked else own.get('father_name'), False)
                result += add_field("🔢", "Owner Serial", mask_val(own.get('owner_serial')) if masked else own.get('owner_serial'))
                
                # Specs Info
                specs = v.get('vehicle_specs', {})
                result += add_field("🏭", "Maker", mask_val(specs.get('model_name')) if masked else specs.get('model_name'), False)
                result += add_field("🚘", "Model", mask_val(specs.get('maker_model')) if masked else specs.get('maker_model'), False)
                result += add_field("🚌", "Class", mask_val(specs.get('vehicle_class')) if masked else specs.get('vehicle_class'), False)
                result += add_field("⛽", "Fuel", mask_val(specs.get('fuel_type')) if masked else specs.get('fuel_type'), False)
                result += add_field("⚙️", "CC", mask_val(specs.get('cubic_capacity')) if masked else specs.get('cubic_capacity'))
                result += add_field("💺", "Seats", mask_val(specs.get('seating_capacity')) if masked else specs.get('seating_capacity'))
                result += add_field("⚙️", "Chassis", mask_val(specs.get('chassis_number'), is_phone=True) if masked else specs.get('chassis_number'))
                result += add_field("⚙️", "Engine", mask_val(specs.get('engine_number'), is_phone=True) if masked else specs.get('engine_number'))
                
                # Insurance Info
                ins = v.get('insurance', {})
                ins_company = add_field("🛡️", "Insurance", mask_val(ins.get('insurance_company')) if masked else ins.get('insurance_company'), False)
                ins_policy = add_field("📄", "Policy", mask_val(ins.get('insurance_number'), is_phone=True) if masked else ins.get('insurance_number'))
                ins_expiry = add_field("📅", "Expiry", mask_val(ins.get('insurance_expiry')) if masked else ins.get('insurance_expiry'))
                if ins_company or ins_policy or ins_expiry:
                    result += format_separator() + "\n"
                    result += ins_company + ins_policy + ins_expiry
                
                # Validity Info
                val = v.get('validity', {})
                val_reg = add_field("📅", "Reg Date", mask_val(val.get('registration_date')) if masked else val.get('registration_date'))
                val_age = add_field("⏳", "Age", mask_val(val.get('vehicle_age')) if masked else val.get('vehicle_age'), False)
                val_fit = add_field("✅", "Fitness Upto", mask_val(val.get('fitness_upto')) if masked else val.get('fitness_upto'))
                val_tax = add_field("💰", "Tax Paid Upto", mask_val(val.get('tax_upto')) if masked else val.get('tax_upto'))
                puc_num = val.get('puc_number')
                puc_field = add_field("🛡️", "PUC No", mask_val(puc_num, is_phone=True) if masked else puc_num)
                puc_expiry = add_field("📅", "PUC Upto", mask_val(val.get('puc_upto')) if masked else val.get('puc_upto'))
                
                if val_reg or val_age or val_fit or val_tax or puc_field or puc_expiry:
                    result += format_separator() + "\n"
                    result += val_reg + val_age + val_fit + val_tax + puc_field + puc_expiry
                
                # RTO Info
                rto = v.get('rto_contact', {})
                rto_val = ""
                rto_city = rto.get('city')
                rto_code = rto.get('code')
                if rto_city and rto_city != 'N/A' and rto_code and rto_code != 'N/A':
                    rto_val = f"{rto_city} ({rto_code})"
                elif rto_city and rto_city != 'N/A':
                    rto_val = rto_city
                elif rto_code and rto_code != 'N/A':
                    rto_val = rto_code
                
                rto_field = add_field("🏢", "RTO", mask_val(rto_val) if masked else rto_val, False)
                rto_phone = add_field("📞", "RTO Phone", mask_val(rto.get('phone'), is_phone=True) if masked else rto.get('phone'))
                
                # Address extraction (rto_contact.address or ownership.registered_rto fallback)
                addr = rto.get('address')
                if not addr or addr == 'N/A':
                    addr = own.get('registered_rto')
                addr_field = add_field("📍", "Address", mask_val(addr) if masked else addr, False)
                
                if rto_field or rto_phone or addr_field:
                    result += format_separator() + "\n"
                    result += rto_field + rto_phone + addr_field
                
                return result.strip()
            
            return format_no_results(rc)
        
        else:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: requests.get(VEHICLE_API_2.format(rc), timeout=25)
            )
            data = response.json()
            
            if isinstance(data, dict) and data:
                result = format_header("🚙", "VEHICLE DETAILS (API 2)") + "\n"
                
                # Check if there is a nested 'formatted' or 'Formatted' key
                v_data = {}
                formatted = data.get('formatted', data.get('Formatted'))
                if isinstance(formatted, dict):
                    v_data = formatted.get('all_fields', formatted)
                if not v_data:
                    v_data = data.get('raw_data', data.get('Raw Data', {}))
                if not v_data:
                    v_data = data
                
                if isinstance(v_data, dict):
                    fields = {
                        'registration_number': ('🔢', 'RC'),
                        'vehicle_number': ('🔢', 'RC'),
                        'owner_name': ('👤', 'Owner'),
                        'father_name': ('👨', 'Father'),
                        'maker_model': ('🚘', 'Model'),
                        'modal_name': ('🚘', 'Model'),
                        'model_name': ('🏭', 'Maker') if ('maker_model' in v_data or 'modal_name' in v_data) else ('🚘', 'Model'),
                        'maker': ('🏭', 'Maker'),
                        'fuel_type': ('⛽', 'Fuel'),
                        'cubic_capacity': ('⚙️', 'CC'),
                        'registration_date': ('📅', 'Reg Date'),
                        'registered_rto': ('🏢', 'RTO'),
                        'rto_location': ('🏢', 'RTO'),
                        'phone': ('📞', 'Phone'),
                        'address': ('📍', 'Address'),
                    }
                    
                    shown_keys = set()
                    shown_labels = set()
                    for key, (emoji, label) in fields.items():
                        val = v_data.get(key)
                        if val:
                            val_str = str(val).strip()
                            if val_str.upper() not in ['', 'N/A', 'NA', 'NONE', 'NULL']:
                                shown_keys.add(key)
                                if label not in shown_labels:
                                    is_code = key in ['registration_number', 'vehicle_number']
                                    is_phone_like = key in ['registration_number', 'vehicle_number', 'phone']
                                    val_to_show = mask_val(val, is_phone=is_phone_like) if masked else val
                                    field_str = add_field(emoji, label, val_to_show, is_code)
                                    if field_str:
                                        result += field_str
                                        shown_labels.add(label)
                    
                    # Add any extra fields (excluding objects or dicts, and excluding fields already shown)
                    extra_fields = {k: v for k, v in v_data.items() 
                                  if k not in shown_keys and v and not isinstance(v, (dict, list))}
                    
                    extra_fields_str = ""
                    for key, value in extra_fields.items():
                        val_str = str(value).strip()
                        if val_str.upper() not in ['', 'N/A', 'NA', 'NONE', 'NULL']:
                             label = key.replace('_', ' ').title()
                             is_code = any(x in key.lower() for x in ['number', 'no', 'code', 'id', 'license', 'pan', 'aadhaar'])
                             is_phone_like = any(x in key.lower() for x in ['number', 'no', 'code', 'id', 'license', 'pan', 'aadhaar', 'phone'])
                             val_to_show = mask_val(val_str, is_phone=is_phone_like) if masked else val_str
                             extra_fields_str += add_field("📋", label, val_to_show, is_code)
                    
                    if extra_fields_str:
                        result += format_separator() + "\n" + extra_fields_str
                    
                    return result.strip()
            
            return format_no_results(rc)
            
    except Exception as e:
        logger.error(f"Vehicle search error: {e}")
        return handle_api_exception("Vehicle API", e)

async def search_pan_info(pan: str, masked: bool = False) -> str:
    """Search PAN card information"""
    try:
        pointer = PAN_API.format(pan)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: requests.get(pointer, timeout=15)
        )
        data = response.json()
        
        if isinstance(data, dict) and data.get('success') and data.get('pan_info'):
            p = data['pan_info']
            
            raw_gender = p.get('gender')
            gender = None
            if raw_gender:
                if str(raw_gender).strip().upper() == 'M':
                    gender = 'Male'
                elif str(raw_gender).strip().upper() == 'F':
                    gender = 'Female'
                else:
                    gender = raw_gender
            
            result = format_header("📄", "PAN CARD DETAILS") + "\n"
            result += add_field("📇", "PAN", mask_val(p.get('pan_number'), is_phone=True) if masked else p.get('pan_number'))
            result += add_field("👤", "Name", mask_val(p.get('name')) if masked else p.get('name'), False)
            result += add_field("👨", "Father", mask_val(p.get('father_name')) if masked else p.get('father_name'), False)
            result += add_field("📅", "DOB", mask_val(p.get('dob')) if masked else p.get('dob'), False)
            result += add_field("👥", "Gender", mask_val(gender) if masked else gender, False)
            
            income = p.get('monthly_income')
            masked_income = mask_val(income) if masked else income
            income_str = f"₹{masked_income}/month" if income is not None and str(income).strip().upper() not in ['', 'N/A', 'NA', 'NONE', 'NULL'] else None
            result += add_field("💰", "Income", income_str, False)
            result += add_field("📞", "Phone", mask_val(p.get('phone'), is_phone=True) if masked else p.get('phone'))
            
            addr_field = add_field("📍", "Address", mask_val(p.get('address')) if masked else p.get('address'), False)
            if addr_field:
                result += format_separator() + "\n" + addr_field
            
            return result.strip()
        
        return format_no_results(pan)
        
    except Exception as e:
        logger.error(f"PAN search error: {e}")
        return handle_api_exception("PAN API", e)

async def search_github_info(username: str, masked: bool = False) -> str:
    """Search GitHub profile information"""
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: requests.get(GITHUB_API.format(username), timeout=15)
        )
        if response.status_code == 404:
            return format_no_results(username)
        
        d = response.json()
        if not isinstance(d, dict):
            return format_error("GitHub API Error", "Invalid response format from server.")
        
        result = format_header("💻", "GITHUB PROFILE") + "\n"
        result += add_field("🔑", "Username", mask_val(d.get('login')) if masked else d.get('login'))
        result += add_field("👤", "Name", mask_val(d.get('name')) if masked else d.get('name'), False)
        result += add_field("🏢", "Company", mask_val(d.get('company')) if masked else d.get('company'), False)
        result += add_field("📍", "Location", mask_val(d.get('location')) if masked else d.get('location'), False)
        result += add_field("📝", "Bio", mask_val(d.get('bio')) if masked else d.get('bio'), False)
        result += add_field("🌐", "Blog", mask_val(d.get('blog')) if masked else d.get('blog'), False)
        
        stats_str = ""
        stats_str += add_field("📚", "Repos", d.get('public_repos'), False)
        stats_str += add_field("👥", "Followers", d.get('followers'), False)
        stats_str += add_field("👣", "Following", d.get('following'), False)
        stats_str += add_field("🔗", "Profile", mask_val(d.get('html_url')) if masked else d.get('html_url'), False)
        
        if stats_str:
            result += format_separator() + "\n" + stats_str
            
        return result.strip()
        
    except Exception as e:
        logger.error(f"GitHub search error: {e}")
        return handle_api_exception("GitHub API", e)



def format_leak_page(results, query, page_index=0, masked=False):
    """Format a single page of leak results (5 records per page) and return (text, reply_markup)"""
    total_records = len(results)
    records_per_page = 5
    total_pages = (total_records + records_per_page - 1) // records_per_page
    
    # Bound check
    if page_index < 0:
        page_index = 0
    if page_index >= total_pages:
        page_index = total_pages - 1
        
    start_idx = page_index * records_per_page
    end_idx = min(start_idx + records_per_page, total_records)
    page_results = results[start_idx:end_idx]
    
    # Build text
    result = format_header("🕵️", "LEAK OSINT REPORT") + "\n\n"
    
    if page_results:
        for idx, record in enumerate(page_results, start_idx + 1):
            result += f"<b>Record #{idx}</b>\n"
            
            # Priority fields first
            field_map = {
                'mobile': ('📱', 'Mobile'),
                'name': ('👤', 'Name'),
                'father_name': ('👨', 'Father'),
                'fname': ('👨', 'Father'),
                'circle': ('📡', 'Circle'),
                'alternate_mobile': ('🔄', 'Alternate'),
                'alt': ('🔄', 'Alternate'),
                'email': ('📧', 'Email'),
                'id': ('🆔', 'ID'),
                'aadhaar': ('🆔', 'Aadhaar'),
                'dob': ('📅', 'DOB'),
                'gender': ('👥', 'Gender'),
                'address': ('📍', 'Address'),
            }
            
            shown_fields = set()
            record_fields_str = ""
            for key, (emoji, label) in field_map.items():
                val = record.get(key)
                if val:
                    val_str = str(val).strip()
                    if val_str.upper() not in ['', 'N/A', 'NA', 'NONE', 'NULL']:
                        is_code = key in ['mobile', 'alt', 'alternate_mobile', 'id', 'aadhaar', 'email', 'pan']
                        is_phone_like = key in ['mobile', 'alt', 'alternate_mobile', 'id', 'aadhaar']
                        val_to_show = mask_val(val_str, is_phone=is_phone_like) if masked else val_str
                        record_fields_str += add_field(emoji, label, val_to_show, is_code)
                        shown_fields.add(key)
            
            # Show extra fields
            extra_fields = {k: v for k, v in record.items() 
                          if k not in shown_fields and v and not k.startswith('_')}
            for key, value in extra_fields.items():
                val_str = str(value).strip()
                if val_str.upper() not in ['', 'N/A', 'NA', 'NONE', 'NULL']:
                    is_code = any(x in key.lower() for x in ['number', 'no', 'code', 'id', 'license', 'pan', 'aadhaar', 'email', 'phone', 'mobile'])
                    is_phone_like = any(x in key.lower() for x in ['number', 'no', 'code', 'id', 'license', 'pan', 'aadhaar', 'phone', 'mobile'])
                    label = key.replace('_', ' ').title()
                    val_to_show = mask_val(val_str, is_phone=is_phone_like) if masked else val_str
                    record_fields_str += add_field("🔹", label, val_to_show, is_code)
            
            result += record_fields_str
            result += format_subseparator() + "\n\n"
        
        result = result.rstrip()
        if result.endswith(format_subseparator()):
            result = result[:-len(format_subseparator())].rstrip()
    else:
        result += "ℹ️ No detailed records found."
        
    # Build pagination keyboard
    keyboard = []
    if total_pages > 1:
        row = []
        if page_index > 0:
            row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"leak_page:{page_index - 1}"))
        else:
            row.append(InlineKeyboardButton("❌ Prev", callback_data="none"))
            
        row.append(InlineKeyboardButton(f"{page_index + 1} / {total_pages}", callback_data="none"))
        
        if page_index < total_pages - 1:
            row.append(InlineKeyboardButton("Next ▶️", callback_data=f"leak_page:{page_index + 1}"))
        else:
            row.append(InlineKeyboardButton("Next ❌", callback_data="none"))
            
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("🔙 Back to Start", callback_data="start")])
    
    return result.strip(), InlineKeyboardMarkup(keyboard)

async def search_leak_info(query: str):
    """Search leak database for information and return raw results list or error string"""
    try:
        logger.info(f"Searching leak API for: {query}")
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, lambda: requests.get(LEAK_API.format(query), timeout=20)
        )
        
        if response.status_code != 200:
            return f"Server returned status {response.status_code}"
        
        data = response.json()
        if isinstance(data, dict) and 'error' in data:
            return data['error']
            
        return extract_results(data)
        
    except requests.exceptions.Timeout:
        return "Timeout: API took too long to respond. Please try again."
    except requests.exceptions.ConnectionError:
        return "Connection Error: API server unreachable.\n💡 The Cloudflare tunnel may have expired."
    except Exception as e:
        logger.error(f"Leak error: {e}")
        return str(e)

# ==================== COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    user_id = user.id
    
    # Check if banned (admins bypass)
    user_data = db.users.find_one({"user_id": user_id})
    if user_data and user_data.get('banned', False) and user_id not in ADMIN_IDS:
        if update.message:
            await update.message.reply_text("❌ <b>Your account has been banned by the Administrator.</b>", parse_mode='HTML')
        return

    # Check if this is a referral link (starts with ref_)
    ref_id = None
    if context.args and context.args[0].startswith("ref_"):
        try:
            ref_id = int(context.args[0].split("_")[1])
        except (ValueError, IndexError):
            pass
            
    if not user_data:
        # New user registration!
        user_data = register_user(user, ref_id)
        
        # Send welcome gift notification to new user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🎉 <b>Welcome to DetailDrop!</b> You received <b>1-Day Free Pass</b> & <b>10 Credits</b> 🎁",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to send welcome gift notification to {user_id}: {e}")
        
        # Reward the referrer if valid and not banned
        if ref_id and ref_id != user_id:
            referrer = db.users.find_one({"user_id": ref_id})
            if referrer and not referrer.get('banned', False):
                db.users.update_one({"user_id": ref_id}, {"$inc": {"credits": 2, "total_referred": 1}})
                # Notify referrer
                try:
                    await context.bot.send_message(
                        chat_id=ref_id,
                        text=f"🎉 <b>New Referral!</b>\n━━━━━━━━━━━━━━━━━━━━\n👤 <b>{escape_html(user.first_name)}</b> joined using your referral link.\n💰 <b>+2 Credits</b> have been added to your balance!",
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify referrer: {e}")

    keyboard = [
        [InlineKeyboardButton("🔎 Search DB Panel", callback_data='menu_search')],
        [InlineKeyboardButton("💰 Earn & Rewards", callback_data='menu_rewards')],
        [InlineKeyboardButton("👤 My Account", callback_data='menu_account'),
         InlineKeyboardButton("💳 Support & Buy", callback_data='menu_support')],
        [InlineKeyboardButton("📖 Help Guide", callback_data='menu_help')]
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("📊 Admin Panel", callback_data='admin_panel')])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome = "🕵️ <i>Cyber-intelligence at your fingertips. Select a category below to search.</i>"
    
    if update.message:
        await update.message.reply_text(welcome, reply_markup=reply_markup, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.edit_message_text(welcome, reply_markup=reply_markup, parse_mode='HTML')

# ==================== DIRECT COMMANDS ====================

async def mobile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct mobile search command"""
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /mobile 9876543210"),
            parse_mode='HTML'
        )
        return
        
    num = context.args[0].strip()
    if not num.isdigit() or len(num) != 10:
        await update.message.reply_text(
            format_error("Invalid Input", "Please enter a valid 10-digit mobile number"),
            parse_mode='HTML'
        )
        return
    
    user = update.effective_user
    allowed, masked, err_msg, reply_markup = await check_user_access(user, context, query_type='mobile')
    if not allowed:
        await update.message.reply_text(err_msg, reply_markup=reply_markup, parse_mode='HTML')
        return
        
    msg = await update.message.reply_text("🔍 <b>Searching...</b>", parse_mode='HTML')
    result = await search_mobile_info(num, masked=masked)
    
    if masked:
        result = append_lock_message(result)
        reply_markup = get_masked_keyboard()
        
    await send_formatted_message(update, result, msg, reply_markup=reply_markup)

async def vehicle1_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct vehicle API 1 search command"""
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /vehicle1 DL3CAS1234"),
            parse_mode='HTML'
        )
        return
        
    rc = context.args[0].strip().upper()
    if len(rc) < 8:
        await update.message.reply_text(
            format_error("Invalid Input", "Vehicle number must be at least 8 characters"),
            parse_mode='HTML'
        )
        return
    
    user = update.effective_user
    allowed, masked, err_msg, reply_markup = await check_user_access(user, context, query_type='vehicle1')
    if not allowed:
        await update.message.reply_text(err_msg, reply_markup=reply_markup, parse_mode='HTML')
        return
        
    msg = await update.message.reply_text("🔍 <b>Searching API 1...</b>", parse_mode='HTML')
    result = await search_vehicle_info(rc, 1, masked=masked)
    
    if masked:
        result = append_lock_message(result)
        reply_markup = get_masked_keyboard()
        
    await send_formatted_message(update, result, msg, reply_markup=reply_markup)

async def vehicle2_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct vehicle API 2 search command"""
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /vehicle2 DL3CAS1234"),
            parse_mode='HTML'
        )
        return
        
    rc = context.args[0].strip().upper()
    if len(rc) < 8:
        await update.message.reply_text(
            format_error("Invalid Input", "Vehicle number must be at least 8 characters"),
            parse_mode='HTML'
        )
        return
    
    user = update.effective_user
    allowed, masked, err_msg, reply_markup = await check_user_access(user, context, query_type='vehicle2')
    if not allowed:
        await update.message.reply_text(err_msg, reply_markup=reply_markup, parse_mode='HTML')
        return
        
    msg = await update.message.reply_text("🔍 <b>Searching API 2...</b>", parse_mode='HTML')
    result = await search_vehicle_info(rc, 2, masked=masked)
    
    if masked:
        result = append_lock_message(result)
        reply_markup = get_masked_keyboard()
        
    await send_formatted_message(update, result, msg, reply_markup=reply_markup)

async def pan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct PAN search command"""
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /pan ABCDE1234F"),
            parse_mode='HTML'
        )
        return
        
    pan = context.args[0].strip().upper()
    if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan):
        await update.message.reply_text(
            format_error("Invalid Input", "Format should be: ABCDE1234F"),
            parse_mode='HTML'
        )
        return
    
    user = update.effective_user
    allowed, masked, err_msg, reply_markup = await check_user_access(user, context, query_type='pan')
    if not allowed:
        await update.message.reply_text(err_msg, reply_markup=reply_markup, parse_mode='HTML')
        return
        
    msg = await update.message.reply_text("🔍 <b>Searching...</b>", parse_mode='HTML')
    result = await search_pan_info(pan, masked=masked)
    
    if masked:
        result = append_lock_message(result)
        reply_markup = get_masked_keyboard()
        
    await send_formatted_message(update, result, msg, reply_markup=reply_markup)

async def github_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct GitHub search command"""
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /github username"),
            parse_mode='HTML'
        )
        return
        
    username = context.args[0].strip()
    if not username or ' ' in username:
        await update.message.reply_text(
            format_error("Invalid Input", "Please enter a valid GitHub username"),
            parse_mode='HTML'
        )
        return
    
    user = update.effective_user
    allowed, masked, err_msg, reply_markup = await check_user_access(user, context, query_type='github')
    if not allowed:
        await update.message.reply_text(err_msg, reply_markup=reply_markup, parse_mode='HTML')
        return
        
    msg = await update.message.reply_text("🔍 <b>Searching...</b>", parse_mode='HTML')
    result = await search_github_info(username, masked=masked)
    
    if masked:
        result = append_lock_message(result)
        reply_markup = get_masked_keyboard()
        
    await send_formatted_message(update, result, msg, reply_markup=reply_markup)

async def leak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct leak search command"""
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /leak phone or email"),
            parse_mode='HTML'
        )
        return
    
    user = update.effective_user
    allowed, masked, err_msg, reply_markup = await check_user_access(user, context, query_type='leak')
    if not allowed:
        await update.message.reply_text(err_msg, reply_markup=reply_markup, parse_mode='HTML')
        return
        
    query = ' '.join(context.args).strip()
    if not query:
        await update.message.reply_text(
            format_error("Invalid Input", "Please enter phone or email"),
            parse_mode='HTML'
        )
        return
        
    msg = await update.message.reply_text("🔍 <b>Searching leak database...</b>", parse_mode='HTML')
    results = await search_leak_info(query)
    
    if isinstance(results, str):
        await msg.edit_text(format_error("Error", results), parse_mode='HTML')
        return
        
    if not results:
        await msg.edit_text(format_no_results(query), parse_mode='HTML')
        return
        
    context.user_data['leak_query'] = query
    context.user_data['leak_results'] = results
    context.user_data['leak_masked'] = masked
    
    text, reply_markup = format_leak_page(results, query, 0, masked=masked)
    if masked:
        text = append_lock_message(text)
        reply_markup = get_masked_keyboard()
        
    await msg.edit_text(text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)



# ==================== CONVERSATION HANDLERS ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses"""
    query = update.callback_query
    user_id = update.effective_user.id
    option = query.data
    
    # Check if banned (admins bypass)
    user_data = db.users.find_one({"user_id": user_id})
    if user_data and user_data.get('banned', False) and user_id not in ADMIN_IDS:
        await query.answer()
        await send_temp_message(context, user_id, "❌ <b>Your account has been banned by the Administrator.</b>")
        return ConversationHandler.END
        
    # Pre-check search query options for bans, maintenance, and force join
    if option in ['mobile', 'vehicle1', 'vehicle2', 'pan', 'github', 'leak']:
        allowed, masked, err_msg, reply_markup = await check_user_access(update.effective_user, context, deduct_credit=False)
        if not allowed:
            if err_msg == FORCE_JOIN_TEXT:
                # If blocked due to force join, answer the callback and edit the lock screen inline
                await query.answer()
                await query.edit_message_text(
                    err_msg,
                    reply_markup=reply_markup,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
            else:
                # Banned or Maintenance: show temporary HTML message
                await query.answer()
                await send_temp_message(context, user_id, err_msg)
            return ConversationHandler.END

    await query.answer()
    
    if option.startswith('leak_page:'):
        page_index = int(option.split(':')[1])
        results = context.user_data.get('leak_results')
        l_query = context.user_data.get('leak_query', '')
        masked = context.user_data.get('leak_masked', False)
        if results:
            text, reply_markup = format_leak_page(results, l_query, page_index, masked=masked)
            if masked:
                text = append_lock_message(text)
                reply_markup = get_masked_keyboard()
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)
        else:
            await query.edit_message_text(format_error("Session Expired", "Please search again using /leak."), parse_mode='HTML')
        return ConversationHandler.END
        
    elif option == 'menu_search':
        # Check Force Join
        joined = await check_force_join(user_id, context.bot)
        if not joined:
            await query.edit_message_text(
                FORCE_JOIN_TEXT,
                reply_markup=get_force_join_keyboard(),
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            return ConversationHandler.END
            
        keyboard = [
            [InlineKeyboardButton("📱 Mobile Search", callback_data='mobile'),
             InlineKeyboardButton("🕵️ Leak OSINT", callback_data='leak')],
            [InlineKeyboardButton("🚗 Vehicle API 1", callback_data='vehicle1'),
             InlineKeyboardButton("🚙 Vehicle API 2", callback_data='vehicle2')],
            [InlineKeyboardButton("📄 PAN Card", callback_data='pan')],
            [InlineKeyboardButton("💻 GitHub Lookup", callback_data='github')],
            [InlineKeyboardButton("🔙 Back to Home", callback_data='start')]
        ]
        text = f"""🔎 <b>OSINT SEARCH PANEL</b>
━━━━━━━━━━━━━━━━━━━━
Select one of the query types below or use the quick commands to start searching immediately.

📖 <b>Quick Search Commands:</b>
• 📱 Mobile: <code>/mobile 9876543210</code>
• 🚗 Vehicle 1: <code>/vehicle1 DL3CAS1234</code>
• 🚙 Vehicle 2: <code>/vehicle2 DL3CAS1234</code>
• 📄 PAN: <code>/pan ABCDE1234F</code>
• 💻 GitHub: <code>/github username</code>
• 🕵️ Leak: <code>/leak email_or_phone</code>
━━━━━━━━━━━━━━━━━━━━"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return ConversationHandler.END

    elif option == 'verify_force_join':
        joined, missing = await check_force_join_status(user_id, context.bot)
        if joined:
            await query.answer()
            await send_temp_message(context, user_id, "✅ <b>Verification Successful! Access Granted.</b>")
            # Show the Search DB Panel (menu_search)
            keyboard = [
                [InlineKeyboardButton("📱 Mobile Search", callback_data='mobile'),
                 InlineKeyboardButton("🕵️ Leak OSINT", callback_data='leak')],
                [InlineKeyboardButton("🚗 Vehicle API 1", callback_data='vehicle1'),
                 InlineKeyboardButton("🚙 Vehicle API 2", callback_data='vehicle2')],
                [InlineKeyboardButton("📄 PAN Card", callback_data='pan')],
                [InlineKeyboardButton("💻 GitHub Lookup", callback_data='github')],
                [InlineKeyboardButton("🔙 Back to Home", callback_data='start')]
            ]
            text = """🔎 <b>OSINT SEARCH PANEL</b>
━━━━━━━━━━━━━━━━━━━━
Select one of the query types below or use the quick commands to start searching immediately.

📖 <b>Quick Search Commands:</b>
• 📱 Mobile: <code>/mobile 9876543210</code>
• 🚗 Vehicle 1: <code>/vehicle1 DL3CAS1234</code>
• 🚙 Vehicle 2: <code>/vehicle2 DL3CAS1234</code>
• 📄 PAN: <code>/pan ABCDE1234F</code>
• 💻 GitHub: <code>/github username</code>
• 🕵️ Leak: <code>/leak email_or_phone</code>
━━━━━━━━━━━━━━━━━━━━"""
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        else:
            if missing == "both":
                msg = "❌ <b>Verification Failed:</b> You must join both our Public Group and Channel first!"
            elif missing == "group":
                msg = "❌ <b>Verification Failed:</b> You haven't joined our Public Group yet!"
            else:
                msg = "❌ <b>Verification Failed:</b> You haven't joined our Public Channel yet!"
            await query.answer()
            await send_temp_message(context, user_id, msg)
        return ConversationHandler.END

    elif option == 'menu_rewards':
        keyboard = [
            [InlineKeyboardButton("🎁 Daily Check-in", callback_data='checkin'),
             InlineKeyboardButton("🏆 Leaderboard", callback_data='leaderboard')],
            [InlineKeyboardButton("🔙 Back to Home", callback_data='start')]
        ]
        text = f"""💰 <b>EARN & REWARDS</b>
━━━━━━━━━━━━━━━━━━━━
Get free search credits to run queries:

🎁 <b>Daily Check-in:</b> Claim +1 free credit every 24 hours.
👥 <b>Referrals:</b> Earn +2 credits instantly for every friend who joins using your link.
🏷️ <b>Promo Codes:</b> Claim promo codes released by admins.

💡 <i>To redeem a promo code, type: <code>/claim &lt;code&gt;</code></i>
━━━━━━━━━━━━━━━━━━━━"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return ConversationHandler.END

    elif option == 'menu_help':
        help_text = """📖 <b>DETAILDROP BOT USER GUIDE</b>
━━━━━━━━━━━━━━━━━━━━

🔍 <b>1. OSINT SEARCH ENGINES</b>
<i>Full searches cost 1 credit. Free searches return masked details.</i>

📱 <b>Mobile Search</b>
<code>/mobile [phone_number]</code>
↳ <i>Finds Name, Father, Address, alternate phone, and circle.</i>

🚗 <b>Vehicle RTO Details</b>
<code>/vehicle1 [RC]</code> or <code>/vehicle2 [RC]</code>
↳ <i>Finds Owner Name, Model, Insurance details, Reg dates.</i>

📄 <b>PAN Card Lookup</b>
<code>/pan [pan_number]</code>
↳ <i>Finds Full Name, Father's Name, DOB, Income, and Phone.</i>

🕵️ <b>OSINT Leak Breaches</b>
<code>/leak [email_or_phone]</code>
↳ <i>Finds database leak credentials and breach source.</i>

💻 <b>GitHub Profiles</b>
<code>/github [username]</code>
↳ <i>Finds Developer bio, repositories count, and stats.</i>

━━━━━━━━━━━━━━━━━━━━

🎁 <b>2. EARN FREE SEARCH CREDITS</b>
<i>Obtain search credits without paying:</i>

▪️ <b>Daily Check-in</b>
↳ Claim <code>+1 Credit</code> daily by sending `/checkin`.

▪️ <b>Referral Rewards</b>
↳ Share your referral link (from My Account). Get <code>+2 Credits</code> per join.

▪️ <b>Claim Promo Codes</b>
↳ Redeem codes using <code>/claim [code]</code> (e.g., <code>/claim FREE10</code>).

━━━━━━━━━━━━━━━━━━━━

📩 <b>3. HELP & SUPPORT TICKETS</b>
<i>Have issues? Submit a support request directly to admins:</i>

👉 <code>/support [your message]</code>
↳ <i>Our administrators will reply directly to your chat.</i>
━━━━━━━━━━━━━━━━━━━━"""
        keyboard = [[InlineKeyboardButton("🔙 Back to Home", callback_data="start")]]
        await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return ConversationHandler.END

    elif option == 'menu_support':
        text_template = f"Hi! I want to buy a Time Pass for DetailDropBot. My User ID is {user_id}"
        import urllib.parse
        encoded_text = urllib.parse.quote(text_template)
        admin_link = f"https://t.me/{ADMIN_USERNAME}?text={encoded_text}"
        
        text = f"""💳 <b>SUPPORT & BUY TIME PASSES</b>
━━━━━━━━━━━━━━━━━━━━
Get a Time Pass to continue searching bank, vehicle, mobile, pan, leak, and github details with <b>unlimited queries</b>!

🏷️ <b>Pricing Packages:</b>
• ⚡ <b>Flash Pass (1 Hour):</b> ₹15
• 📅 <b>Day Pass (24 Hours):</b> ₹29
• 🛡️ <b>Weekly Pass (7 Days):</b> ₹79
• 👑 <b>VIP Month Pass (30 Days):</b> ₹199

🛒 <b>How to Buy:</b>
Click the button below to message the admin (<b>@{ADMIN_USERNAME}</b>) directly. You will be redirected with your User ID pre-filled.

📩 <b>Support Ticket System:</b>
If you face any issues, submit a support ticket using:
<code>/support &lt;your message&gt;</code>
━━━━━━━━━━━━━━━━━━━━"""
        keyboard = [
            [InlineKeyboardButton("💬 Message Admin to Buy", url=admin_link)],
            [InlineKeyboardButton("📩 Support Info", callback_data="support_info")],
            [InlineKeyboardButton("🔙 Back to Home", callback_data="start")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return ConversationHandler.END

    elif option == 'mobile':
        if not has_user_access_only(user_id):
            allowed, masked, err_msg, reply_markup = await check_user_access(update.effective_user, context, deduct_credit=False)
        keyboard = [[InlineKeyboardButton("🔙 Back to Search", callback_data='menu_search')]]
        await query.edit_message_text(
            "📱 Send 10-digit mobile number:\nExample: <code>9876543210</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return WAITING_MOBILE
        
    elif option == 'vehicle':
        keyboard = [
            [InlineKeyboardButton("API 1", callback_data='vehicle1'), 
             InlineKeyboardButton("API 2", callback_data='vehicle2')],
            [InlineKeyboardButton("🔙 Back", callback_data='start')],
        ]
        await query.edit_message_text(
            "🚗 Select API:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
        
    elif option == 'vehicle1':
        context.user_data['vehicle_api'] = 1
        keyboard = [[InlineKeyboardButton("🔙 Back to Search", callback_data='menu_search')]]
        await query.edit_message_text(
            "🚗 API 1: Send vehicle number\nExample: <code>DL3CAS1234</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return WAITING_VEHICLE
        
    elif option == 'vehicle2':
        context.user_data['vehicle_api'] = 2
        keyboard = [[InlineKeyboardButton("🔙 Back to Search", callback_data='menu_search')]]
        await query.edit_message_text(
            "🚙 API 2: Send vehicle number\nExample: <code>DL3CAS1234</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return WAITING_VEHICLE
        
    elif option == 'pan':
        keyboard = [[InlineKeyboardButton("🔙 Back to Search", callback_data='menu_search')]]
        await query.edit_message_text(
            "📄 Send PAN number:\nExample: <code>ABCDE1234F</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return WAITING_PAN
        
    elif option == 'github':
        keyboard = [[InlineKeyboardButton("🔙 Back to Search", callback_data='menu_search')]]
        await query.edit_message_text(
            "💻 Send GitHub username:\nExample: <code>octocat</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return WAITING_GITHUB
        
    elif option == 'leak':
        keyboard = [[InlineKeyboardButton("🔙 Back to Search", callback_data='menu_search')]]
        await query.edit_message_text(
            "🕵️ Send phone or email:\nExample: <code>test@gmail.com</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return WAITING_LEAK
        
    elif option == 'ifsc':
        keyboard = [[InlineKeyboardButton("🔙 Back to Search", callback_data='menu_search')]]
        await query.edit_message_text(
            "🏦 Send IFSC code:\nExample: <code>SBIN0001234</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return WAITING_IFSC
        
    elif option == 'start':
        await start(update, context)
        return ConversationHandler.END

    elif option == 'profile' or option == 'menu_account':
        await show_profile(update, context)
        return ConversationHandler.END
        
    elif option == 'buy_credits':
        await show_buy_credits(update, context)
        return ConversationHandler.END

    elif option == 'admin_panel':
        await show_admin_panel(update, context)
        return ConversationHandler.END

    elif option == 'checkin':
        user = update.effective_user
        user_id = user.id
        user_data = db.users.find_one({"user_id": user_id})
        if user_data and user_data.get('banned', False) and user_id not in ADMIN_IDS:
            await query.answer()
            await send_temp_message(context, user_id, "🚫 <b>Access Denied:</b> Your account has been blocked.")
            return ConversationHandler.END
            
        if not user_data:
            user_data = register_user(user)
            
        last_checkin = user_data.get('last_checkin')
        now = datetime.utcnow()
        if last_checkin:
            if last_checkin.tzinfo is not None:
                last_checkin = last_checkin.replace(tzinfo=None)
            elapsed = now - last_checkin
            if elapsed.total_seconds() < 86400:
                time_left = 86400 - elapsed.total_seconds()
                hours = int(time_left // 3600)
                minutes = int((time_left % 3600) // 60)
                await query.answer()
                await send_temp_message(context, user_id, f"⏳ <b>Already Claimed:</b> Please try again in <b>{hours}h {minutes}m</b>.")
                return ConversationHandler.END
                
        # Reward
        db.users.update_one(
            {"user_id": user_id},
            {"$inc": {"credits": 1}, "$set": {"last_checkin": now}}
        )
        await query.answer()
        await send_temp_message(context, user_id, "🎁 <b>Daily Check-in Successful!</b> +1 Credit has been added to your profile.")
        await show_profile(update, context)
        return ConversationHandler.END
        
    elif option == 'leaderboard':
        await leaderboard_cmd(update, context)
        return ConversationHandler.END
        
    elif option == 'support_info':
        await query.answer()
        await send_temp_message(
            context,
            user_id,
            "📩 <b>Support Ticket:</b>\nSubmit your support query using the command:\n<code>/support &lt;your message&gt;</code>"
        )
        return ConversationHandler.END
        
    elif option == 'admin_toggle_maint':
        if user_id not in ADMIN_IDS:
            await query.answer()
            await send_temp_message(context, user_id, "⚠️ <b>Unauthorized:</b> You do not have permission to use this command.")
            return ConversationHandler.END
        settings_doc = db.settings.find_one({"_id": "global_settings"})
        is_maintenance = settings_doc.get('maintenance_mode', False) if settings_doc else False
        db.settings.update_one({"_id": "global_settings"}, {"$set": {"maintenance_mode": not is_maintenance}})
        await query.answer()
        status_text = "<b>disabled</b> 🟢" if is_maintenance else "<b>enabled</b> 🔴"
        await send_temp_message(context, user_id, f"⚙️ <b>Maintenance mode</b> has been {status_text}.")
        await show_admin_panel(update, context)
        return ConversationHandler.END
        
    elif option == 'admin_api_health' or option == 'admin_refresh_api':
        if user_id not in ADMIN_IDS:
            await query.answer()
            await send_temp_message(context, user_id, "⚠️ <b>Unauthorized:</b> You do not have permission to use this command.")
            return ConversationHandler.END
        await query.edit_message_text("🔌 <b>Pinging all API endpoints...</b>\n<i>Please wait a few seconds.</i>", parse_mode='HTML')
        health_text = await check_api_health()
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh status", callback_data="admin_refresh_api")],
            [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel")]
        ]
        await query.edit_message_text(health_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return ConversationHandler.END

    elif option == 'admin_refresh':
        await show_admin_panel(update, context)
        return ConversationHandler.END

    elif option == 'admin_broadcast':
        if user_id not in ADMIN_IDS:
            await query.answer()
            await send_temp_message(context, user_id, "⚠️ <b>Unauthorized:</b> You do not have permission to use this command.")
            return ConversationHandler.END
        broadcast_instr = f"""📢 <b>Send Broadcast</b>
━━━━━━━━━━━━━━━━━━━━
To send a broadcast message to all users, please <b>reply to the target message</b> (text, image, video, file, buttons, etc.) with the command:
<code>/broadcast</code>
━━━━━━━━━━━━━━━━━━━━"""
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_refresh")]
        ]
        await query.edit_message_text(broadcast_instr, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return ConversationHandler.END

async def handle_mobile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mobile number input from conversation"""
    num = update.message.text.strip()
    if not num.isdigit() or len(num) != 10:
        await update.message.reply_text(
            format_error("Invalid Input", "Please enter a valid 10-digit mobile number"),
            parse_mode='HTML'
        )
        return WAITING_MOBILE
    
    user = update.effective_user
    allowed, masked, err_msg, reply_markup = await check_user_access(user, context, query_type='mobile')
    if not allowed:
        await update.message.reply_text(err_msg, reply_markup=reply_markup, parse_mode='HTML')
        return ConversationHandler.END
        
    msg = await update.message.reply_text("🔍 <b>Searching...</b>", parse_mode='HTML')
    result = await search_mobile_info(num, masked=masked)
    
    if masked:
        result = append_lock_message(result)
        reply_markup = get_masked_keyboard()
        
    await send_formatted_message(update, result, msg, reply_markup=reply_markup)
    return ConversationHandler.END

async def handle_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle vehicle number input from conversation"""
    rc = update.message.text.strip().upper()
    api = context.user_data.get('vehicle_api', 1)
    
    if len(rc) < 8:
        await update.message.reply_text(
            format_error("Invalid Input", "Vehicle number must be at least 8 characters"),
            parse_mode='HTML'
        )
        return WAITING_VEHICLE
    
    user = update.effective_user
    allowed, masked, err_msg, reply_markup = await check_user_access(user, context, query_type=f'vehicle{api}')
    if not allowed:
        await update.message.reply_text(err_msg, reply_markup=reply_markup, parse_mode='HTML')
        return ConversationHandler.END
        
    api_name = "API 1" if api == 1 else "API 2"
    msg = await update.message.reply_text(f"🔍 <b>Searching {api_name}...</b>", parse_mode='HTML')
    result = await search_vehicle_info(rc, api, masked=masked)
    
    if masked:
        result = append_lock_message(result)
        reply_markup = get_masked_keyboard()
        
    await send_formatted_message(update, result, msg, reply_markup=reply_markup)
    return ConversationHandler.END

async def handle_pan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PAN number input from conversation"""
    pan = update.message.text.strip().upper()
    if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan):
        await update.message.reply_text(
            format_error("Invalid Input", "Format should be: ABCDE1234F"),
            parse_mode='HTML'
        )
        return WAITING_PAN
    
    user = update.effective_user
    allowed, masked, err_msg, reply_markup = await check_user_access(user, context, query_type='pan')
    if not allowed:
        await update.message.reply_text(err_msg, reply_markup=reply_markup, parse_mode='HTML')
        return ConversationHandler.END
        
    msg = await update.message.reply_text("🔍 <b>Searching...</b>", parse_mode='HTML')
    result = await search_pan_info(pan, masked=masked)
    
    if masked:
        result = append_lock_message(result)
        reply_markup = get_masked_keyboard()
        
    await send_formatted_message(update, result, msg, reply_markup=reply_markup)
    return ConversationHandler.END

async def handle_github(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle GitHub username input from conversation"""
    username = update.message.text.strip()
    if not username or ' ' in username:
        await update.message.reply_text(
            format_error("Invalid Input", "Please enter a valid GitHub username"),
            parse_mode='HTML'
        )
        return WAITING_GITHUB
    
    user = update.effective_user
    allowed, masked, err_msg, reply_markup = await check_user_access(user, context, query_type='github')
    if not allowed:
        await update.message.reply_text(err_msg, reply_markup=reply_markup, parse_mode='HTML')
        return ConversationHandler.END
        
    msg = await update.message.reply_text("🔍 <b>Searching...</b>", parse_mode='HTML')
    result = await search_github_info(username, masked=masked)
    
    if masked:
        result = append_lock_message(result)
        reply_markup = get_masked_keyboard()
        
    await send_formatted_message(update, result, msg, reply_markup=reply_markup)
    return ConversationHandler.END

async def handle_leak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle leak query input from conversation"""
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text(
            format_error("Invalid Input", "Please enter a phone number or email"),
            parse_mode='HTML'
        )
        return WAITING_LEAK
    
    user = update.effective_user
    allowed, masked, err_msg, reply_markup = await check_user_access(user, context, query_type='leak')
    if not allowed:
        await update.message.reply_text(err_msg, reply_markup=reply_markup, parse_mode='HTML')
        return ConversationHandler.END
        
    msg = await update.message.reply_text("🔍 <b>Searching leak database...</b>", parse_mode='HTML')
    results = await search_leak_info(query)
    
    if isinstance(results, str):
        await msg.edit_text(format_error("Error", results), parse_mode='HTML')
        return ConversationHandler.END
        
    if not results:
        await msg.edit_text(format_no_results(query), parse_mode='HTML')
        return ConversationHandler.END
        
    context.user_data['leak_query'] = query
    context.user_data['leak_results'] = results
    context.user_data['leak_masked'] = masked
    
    text, reply_markup = format_leak_page(results, query, 0, masked=masked)
    if masked:
        text = append_lock_message(text)
        reply_markup = get_masked_keyboard()
        
    await msg.edit_text(text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)
    return ConversationHandler.END



# ==================== NEW FEATURES & COMMANDS ====================

async def check_api_health() -> str:
    """Ping all APIs and return formatted health status string"""
    apis = {
        "Mobile API": MOBILE_API.format("9876543210"),
        "Vehicle API 1": VEHICLE_API_1.format("DL3CAS1234"),
        "Vehicle API 2": VEHICLE_API_2.format("DL3CAS1234"),
        "PAN API": PAN_API.format("ABCDE1234F"),
        "GitHub API": GITHUB_API.format("octocat"),
        "IFSC API": IFSC_API.format("SBIN0001234"),
        "Leak API": LEAK_API.format("test@gmail.com")
    }
    
    result = "🔌 <b>API HEALTH DASHBOARD</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    
    async def ping_api(name, url):
        try:
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(
                None, lambda: requests.get(url, timeout=3)
            )
            if res.status_code < 500:
                return f"🟢 <b>{name}:</b> Online (HTTP {res.status_code})\n"
            else:
                return f"🔴 <b>{name}:</b> Server Error (HTTP {res.status_code})\n"
        except Exception:
            return f"🔴 <b>{name}:</b> Offline\n"
            
    tasks = [ping_api(name, url) for name, url in apis.items()]
    statuses = await asyncio.gather(*tasks)
    
    for s in statuses:
        result += s
        
    result += "━━━━━━━━━━━━━━━━━━━━\n"
    return result

async def checkin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User Daily Check-in command"""
    user = update.effective_user
    user_id = user.id
    
    user_data = db.users.find_one({"user_id": user_id})
    if not user_data:
        user_data = register_user(user)
        
    if user_data.get('banned', False) and user_id not in ADMIN_IDS:
        return
        
    last_checkin = user_data.get('last_checkin')
    now = datetime.utcnow()
    
    if last_checkin:
        if last_checkin.tzinfo is not None:
            last_checkin = last_checkin.replace(tzinfo=None)
        elapsed = now - last_checkin
        if elapsed.total_seconds() < 86400:
            time_left = 86400 - elapsed.total_seconds()
            hours = int(time_left // 3600)
            minutes = int((time_left % 3600) // 60)
            await update.message.reply_text(
                f"⏳ <b>Already Claimed!</b>\n━━━━━━━━━━━━━━━━━━━━\nYou have already checked in today.\n💡 Please try again in <b>{hours}h {minutes}m</b>.",
                parse_mode='HTML'
            )
            return
            
    db.users.update_one(
        {"user_id": user_id},
        {"$inc": {"credits": 1}, "$set": {"last_checkin": now}}
    )
    
    await update.message.reply_text(
        f"🎁 <b>Daily Check-in Successful!</b>\n━━━━━━━━━━━━━━━━━━━━\n🎉 <b>+1 Credit</b> has been added to your balance!\n💰 Use /profile to view your balance.",
        parse_mode='HTML'
    )

async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top referrers"""
    user = update.effective_user
    user_id = user.id
    
    user_data = db.users.find_one({"user_id": user_id})
    if user_data and user_data.get('banned', False) and user_id not in ADMIN_IDS:
        return
        
    top_users = db.users.find({}).sort("total_referred", -1).limit(10)
    
    text = f"🏆 <b>REFERRAL LEADERBOARD</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    rank = 1
    emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
    
    for u in top_users:
        ref_count = u.get('total_referred', 0)
        first_name = escape_html(u.get('first_name', 'User'))
        username = u.get('username')
        user_mention = f"@{escape_html(username)}" if username else first_name
        
        rank_emoji = emojis.get(rank, "🔹")
        text += f"{rank_emoji} <b>{rank}.</b> {user_mention} — <code>{ref_count} refs</code>\n"
        rank += 1
        
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Start", callback_data="start")]]
    
    query = update.callback_query
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    else:
        await update.message.reply_text(text, parse_mode='HTML')

async def support_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User support request command"""
    user = update.effective_user
    user_id = user.id
    
    user_data = db.users.find_one({"user_id": user_id})
    if user_data and user_data.get('banned', False) and user_id not in ADMIN_IDS:
        return
        
    if not user_data:
        user_data = register_user(user)
        
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /support <your message>\nExample: /support Hi, my credits didn't update."),
            parse_mode='HTML'
        )
        return
        
    message_text = " ".join(context.args)
    
    admin_notified = 0
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📩 <b>NEW SUPPORT TICKET</b>\n━━━━━━━━━━━━━━━━━━━━\n👤 <b>From:</b> {escape_html(user.first_name)} (@{escape_html(user.username) if user.username else 'N/A'})\n🆔 <b>User ID:</b> <code>{user_id}</code>\n📝 <b>Message:</b> <i>{escape_html(message_text)}</i>\n━━━━━━━━━━━━━━━━━━━━\n💡 <i>To reply, use: <code>/reply {user_id} &lt;your reply&gt;</code></i>",
                parse_mode='HTML'
            )
            admin_notified += 1
        except Exception as e:
            logger.error(f"Failed to send support ticket to admin {admin_id}: {e}")
            
    if admin_notified > 0:
        db.tickets.insert_one({
            "user_id": user_id,
            "message": message_text,
            "submitted_at": datetime.utcnow(),
            "status": "pending"
        })
        await update.message.reply_text(
            "✅ <b>Support Ticket Submitted!</b>\n━━━━━━━━━━━━━━━━━━━━\nYour query has been forwarded to the administration. We will reply to you shortly.",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            format_error("Error", "Support system is currently unreachable. Please try again later."),
            parse_mode='HTML'
        )

async def reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin reply to support ticket command"""
    if update.effective_user.id not in ADMIN_IDS:
        return
        
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /reply <user_id> <reply message>",
            parse_mode='HTML'
        )
        return
        
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Error: User ID must be a number.", parse_mode='HTML')
        return
        
    reply_text = " ".join(context.args[1:])
    
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"📩 <b>SUPPORT REPLY</b>\n━━━━━━━━━━━━━━━━━━━━\n🛠️ <b>Admin Team:</b> <i>{escape_html(reply_text)}</i>\n━━━━━━━━━━━━━━━━━━━━",
            parse_mode='HTML'
        )
        db.tickets.update_many(
            {"user_id": target_id, "status": "pending"},
            {"$set": {"status": "replied", "replied_at": datetime.utcnow()}}
        )
        await update.message.reply_text(f"✅ Reply successfully sent to User ID <code>{target_id}</code>.", parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send reply to user: {e}", parse_mode='HTML')

async def genpromo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin generate promo code command"""
    if update.effective_user.id not in ADMIN_IDS:
        return
        
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /genpromo <code> <credits> <max_uses>",
            parse_mode='HTML'
        )
        return
        
    code = context.args[0].strip().upper()
    try:
        credits = int(context.args[1])
        max_uses = int(context.args[2])
    except ValueError:
        await update.message.reply_text("Error: Credits and Max Uses must be integers.", parse_mode='HTML')
        return
        
    existing = db.promocodes.find_one({"code": code})
    if existing:
        await update.message.reply_text(f"❌ Promo code <code>{code}</code> already exists.", parse_mode='HTML')
        return
        
    db.promocodes.insert_one({
        "code": code,
        "credits": credits,
        "max_uses": max_uses,
        "uses_count": 0,
        "claimed_by": []
    })
    
    await update.message.reply_text(
        f"✅ <b>Promo Code Created!</b>\n━━━━━━━━━━━━━━━━━━━━\n🔑 <b>Code:</b> <code>{code}</code>\n💰 <b>Credits:</b> <code>{credits}</code>\n👥 <b>Max Uses:</b> <code>{max_uses}</code>\n━━━━━━━━━━━━━━━━━━━━",
        parse_mode='HTML'
    )

async def claim_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User claim promo code command"""
    user = update.effective_user
    user_id = user.id
    
    user_data = db.users.find_one({"user_id": user_id})
    if user_data and user_data.get('banned', False) and user_id not in ADMIN_IDS:
        return
        
    if not user_data:
        user_data = register_user(user)
        
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /claim <code>\nExample: /claim FREE10"),
            parse_mode='HTML'
        )
        return
        
    code = context.args[0].strip().upper()
    promo = db.promocodes.find_one({"code": code})
    
    if not promo:
        await update.message.reply_text(
            format_error("Invalid Code", "This promo code does not exist or has expired."),
            parse_mode='HTML'
        )
        return
        
    if user_id in promo.get('claimed_by', []):
        await update.message.reply_text(
            format_error("Already Claimed", "You have already claimed this promo code!"),
            parse_mode='HTML'
        )
        return
        
    if promo.get('uses_count', 0) >= promo.get('max_uses', 0):
        await update.message.reply_text(
            format_error("Limit Reached", "This promo code's maximum claims limit has been reached."),
            parse_mode='HTML'
        )
        return
        
    credits_reward = promo.get('credits', 0)
    db.promocodes.update_one(
        {"code": code},
        {"$inc": {"uses_count": 1}, "$push": {"claimed_by": user_id}}
    )
    db.users.update_one(
        {"user_id": user_id},
        {"$inc": {"credits": credits_reward}}
    )
    
    await update.message.reply_text(
        f"🎉 <b>Promo Code Claimed!</b>\n━━━━━━━━━━━━━━━━━━━━\n💰 <b>+{credits_reward} Credits</b> have been added to your balance!\n👤 Use /profile to view your balance.",
        parse_mode='HTML'
    )

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin ban user command"""
    if update.effective_user.id not in ADMIN_IDS:
        return
        
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>", parse_mode='HTML')
        return
        
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Error: User ID must be a number.", parse_mode='HTML')
        return
        
    res = db.users.update_one({"user_id": target_id}, {"$set": {"banned": True}})
    if res.matched_count > 0:
        await update.message.reply_text(f"✅ User ID <code>{target_id}</code> has been successfully <b>BANNED</b>.", parse_mode='HTML')
        try:
            await context.bot.send_message(chat_id=target_id, text="❌ <b>Your account has been banned by the Administrator.</b>", parse_mode='HTML')
        except Exception:
            pass
    else:
        await update.message.reply_text("❌ User not found in database.", parse_mode='HTML')

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin unban user command"""
    if update.effective_user.id not in ADMIN_IDS:
        return
        
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>", parse_mode='HTML')
        return
        
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Error: User ID must be a number.", parse_mode='HTML')
        return
        
    res = db.users.update_one({"user_id": target_id}, {"$set": {"banned": False}})
    if res.matched_count > 0:
        await update.message.reply_text(f"✅ User ID <code>{target_id}</code> has been successfully <b>UNBANNED</b>.", parse_mode='HTML')
        try:
            await context.bot.send_message(chat_id=target_id, text="✅ <b>Your account has been unbanned by the Administrator. Access restored.</b>", parse_mode='HTML')
        except Exception:
            pass
    else:
        await update.message.reply_text("❌ User not found in database.", parse_mode='HTML')

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User Help command"""
    user_id = update.effective_user.id
    user_data = db.users.find_one({"user_id": user_id})
    if user_data and user_data.get('banned', False) and user_id not in ADMIN_IDS:
        return
        
    help_text = """📖 <b>DETAILDROP BOT USER GUIDE</b>
━━━━━━━━━━━━━━━━━━━━

🔍 <b>1. OSINT SEARCH ENGINES</b>
<i>Full searches cost 1 credit. Free searches return masked details.</i>

📱 <b>Mobile Search</b>
<code>/mobile [phone_number]</code>
↳ <i>Finds Name, Father, Address, alternate phone, and circle.</i>

🚗 <b>Vehicle RTO Details</b>
<code>/vehicle1 [RC]</code> or <code>/vehicle2 [RC]</code>
↳ <i>Finds Owner Name, Model, Insurance details, Reg dates.</i>

📄 <b>PAN Card Lookup</b>
<code>/pan [pan_number]</code>
↳ <i>Finds Full Name, Father's Name, DOB, Income, and Phone.</i>

🕵️ <b>OSINT Leak Breaches</b>
<code>/leak [email_or_phone]</code>
↳ <i>Finds database leak credentials and breach source.</i>

💻 <b>GitHub Profiles</b>
<code>/github [username]</code>
↳ <i>Finds Developer bio, repositories count, and stats.</i>

━━━━━━━━━━━━━━━━━━━━

🎁 <b>2. EARN FREE SEARCH CREDITS</b>
<i>Obtain search credits without paying:</i>

▪️ <b>Daily Check-in</b>
↳ Claim <code>+1 Credit</code> daily by sending `/checkin`.

▪️ <b>Referral Rewards</b>
↳ Share your referral link (from My Account). Get <code>+2 Credits</code> per join.

▪️ <b>Claim Promo Codes</b>
↳ Redeem codes using <code>/claim [code]</code> (e.g., <code>/claim FREE10</code>).

━━━━━━━━━━━━━━━━━━━━

📩 <b>3. HELP & SUPPORT TICKETS</b>
<i>Have issues? Submit a support request directly to admins:</i>

👉 <code>/support [your message]</code>
↳ <i>Our administrators will reply directly to your chat.</i>
━━━━━━━━━━━━━━━━━━━━
<i>💡 Tip: Click 'Search DB Panel' on the home dashboard to run queries using buttons!</i>"""
    await update.message.reply_text(help_text, parse_mode='HTML')

async def adminhelp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin Help command"""
    if update.effective_user.id not in ADMIN_IDS:
        return
        
    admin_help_text = """👑 <b>DETAILDROP ADMIN COMMAND GUIDE</b>
━━━━━━━━━━━━━━━━━━━━
Here is the category-wise administrative control panel commands:

💰 <b>1. CREDIT & WALLET OPERATIONS</b>
Manage credit balances for users directly:
• <code>/addcredit &lt;user_id&gt; &lt;amount&gt;</code> — Give credits to a user.
• <code>/removecredit &lt;user_id&gt; &lt;amount&gt;</code> — Deduct credits from a user's wallet.

🚫 <b>2. USER ACCESS CONTROL & AUDITING</b>
Investigate and block malicious actors:
• <code>/ban &lt;user_id&gt;</code> — Restrict access. Banned users are blocked immediately from running any query.
• <code>/unban &lt;user_id&gt;</code> — Restore bot access.
• <code>/userinfo &lt;user_id&gt;</code> — Pull user profile stats, joined date, total referrals, and bypass status.
• <b>Maintenance Mode:</b> Toggle it from the Admin Panel (`/admin`) to block non-admin users during updates.

📩 <b>3. SUPPORT TICKET REPLIES</b>
Address user queries directly:
• <code>/reply &lt;user_id&gt; &lt;message&gt;</code> — Send a direct notification with your reply back to the user.

🏷️ <b>4. PROMO CODE GENERATOR</b>
Create coupon codes for marketing or gifts:
• <code>/genpromo &lt;code&gt; &lt;credits&gt; &lt;max_uses&gt;</code> — Generate a redeemable code (e.g. <code>/genpromo FREE10 10 50</code>).

📢 <b>5. BROADCAST SYSTEM</b>
• <b>Usage:</b> Reply to any channel post or message containing text, photo, video, document, voice note, or interactive buttons with <code>/broadcast</code> to forward it exactly as-is to all users.
━━━━━━━━━━━━━━━━━━━━"""
    await update.message.reply_text(admin_help_text, parse_mode='HTML')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current operation"""
    await update.message.reply_text(
        format_error("Cancelled", "Operation cancelled by user\nUse /start to begin again"),
        parse_mode='HTML'
    )
    return ConversationHandler.END

# ==================== DUMMY SERVER FOR RENDER ====================

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"DetailDropBot is running and healthy!")

    def log_message(self, format, *args):
        # Silence default HTTP logging to keep console clean
        return

def run_dummy_server():
    """Starts a simple HTTP server on the specified port to satisfy Render's health checks"""
    port = int(os.environ.get("PORT", 8080))
    server_address = ('', port)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    logger.info(f"Starting health check web server on port {port}...")
    try:
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"Health check web server failed: {e}")

# ==================== GLOBAL ERROR HANDLER ====================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to notify the user if possible"""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Send a friendly error message to the user if the update was a message
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ <b>An unexpected error occurred.</b>\nPlease try again later.",
                parse_mode='HTML'
            )
        except Exception:
            pass

async def post_init(application: Application) -> None:
    """Async startup task initialization"""
    asyncio.create_task(update_api_status_loop())

# ==================== MAIN ====================

def main():
    """Main function to run the bot"""
    print("""
+------------------------------+
|     DetailDrop Bot v3.0      |
|     Uniform Format Edition   |
|     Starting...              |
+------------------------------+
    """)
    
    # Start the dummy web server in a daemon thread to bind to PORT for Render
    if "PORT" in os.environ:
        threading.Thread(target=run_dummy_server, daemon=True).start()
        
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_error_handler(error_handler)
    
    # Conversation handler for button flow
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(private_chat_only(button_handler))],
        states={
            WAITING_MOBILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, private_chat_only(handle_mobile)), CallbackQueryHandler(private_chat_only(button_handler))],
            WAITING_VEHICLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, private_chat_only(handle_vehicle)), CallbackQueryHandler(private_chat_only(button_handler))],
            WAITING_PAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, private_chat_only(handle_pan)), CallbackQueryHandler(private_chat_only(button_handler))],
            WAITING_GITHUB: [MessageHandler(filters.TEXT & ~filters.COMMAND, private_chat_only(handle_github)), CallbackQueryHandler(private_chat_only(button_handler))],
            WAITING_LEAK: [MessageHandler(filters.TEXT & ~filters.COMMAND, private_chat_only(handle_leak)), CallbackQueryHandler(private_chat_only(button_handler))],
        },
        fallbacks=[CommandHandler('cancel', private_chat_only(cancel))],
    )
    
    # Add all handlers
    app.add_handler(CommandHandler('start', private_chat_only(start)))
    app.add_handler(CommandHandler('profile', private_chat_only(show_profile)))
    app.add_handler(CommandHandler('buy', private_chat_only(show_buy_credits)))
    app.add_handler(CommandHandler('admin', private_chat_only(admin_cmd)))
    app.add_handler(CommandHandler('addcredit', private_chat_only(addcredit_cmd)))
    app.add_handler(CommandHandler('removecredit', private_chat_only(removecredit_cmd)))
    app.add_handler(CommandHandler('addpass', private_chat_only(addpass_cmd)))
    app.add_handler(CommandHandler('addpassdays', private_chat_only(addpassdays_cmd)))
    app.add_handler(CommandHandler('userinfo', private_chat_only(userinfo_cmd)))
    app.add_handler(CommandHandler('broadcast', private_chat_only(broadcast_cmd)))
    app.add_handler(CommandHandler('mobile', private_chat_only(mobile_cmd)))
    app.add_handler(CommandHandler('vehicle1', private_chat_only(vehicle1_cmd)))
    app.add_handler(CommandHandler('vehicle2', private_chat_only(vehicle2_cmd)))
    app.add_handler(CommandHandler('vehicle', private_chat_only(vehicle1_cmd)))  # Alias
    app.add_handler(CommandHandler('pan', private_chat_only(pan_cmd)))
    app.add_handler(CommandHandler('github', private_chat_only(github_cmd)))
    app.add_handler(CommandHandler('leak', private_chat_only(leak_cmd)))
    app.add_handler(CommandHandler('checkin', private_chat_only(checkin_cmd)))
    app.add_handler(CommandHandler('leaderboard', private_chat_only(leaderboard_cmd)))
    app.add_handler(CommandHandler('support', private_chat_only(support_cmd)))
    app.add_handler(CommandHandler('reply', private_chat_only(reply_cmd)))
    app.add_handler(CommandHandler('genpromo', private_chat_only(genpromo_cmd)))
    app.add_handler(CommandHandler('claim', private_chat_only(claim_cmd)))
    app.add_handler(CommandHandler('ban', private_chat_only(ban_cmd)))
    app.add_handler(CommandHandler('unban', private_chat_only(unban_cmd)))
    app.add_handler(CommandHandler('help', private_chat_only(help_cmd)))
    app.add_handler(CommandHandler('adminhelp', private_chat_only(adminhelp_cmd)))
    app.add_handler(conv_handler)
    
    print("[INFO] Bot is running!")
    print("[INFO] Press Ctrl+C to stop")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()