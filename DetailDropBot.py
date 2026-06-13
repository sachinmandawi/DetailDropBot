#!/usr/bin/env python3
"""
DetailDrop Telegram Bot
Multi-source intelligence search bot - Uniform Format v3.0
"""

import requests
import json
import logging
import re
import asyncio
import html
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8683454343:AAFzsIOx2mWpxbXNdqlO7rr0n_BsxbTdYM4")

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

async def send_formatted_message(update: Update, text: str, msg_to_edit=None):
    """Send a message, splitting it safely to not break HTML tags and stay under 4000 chars"""
    if len(text) <= 4000:
        if msg_to_edit:
            await msg_to_edit.edit_text(text, parse_mode='HTML', disable_web_page_preview=True)
        else:
            await update.effective_message.reply_text(text, parse_mode='HTML', disable_web_page_preview=True)
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
        await msg_to_edit.edit_text(chunks[0], parse_mode='HTML', disable_web_page_preview=True)
    else:
        await update.effective_message.reply_text(chunks[0], parse_mode='HTML', disable_web_page_preview=True)
        
    for chunk in chunks[1:]:
        await update.effective_message.reply_text(chunk, parse_mode='HTML', disable_web_page_preview=True)
# ==================== SEARCH FUNCTIONS ====================

async def search_mobile_info(number: str) -> str:
    """Search mobile number information"""
    try:
        response = requests.get(MOBILE_API.format(number), timeout=15)
        raw_text = response.text.strip()
        last_brace = raw_text.rfind('}')
        if last_brace != -1:
            raw_text = raw_text[:last_brace + 1]
        data = json.loads(raw_text)
        
        if data.get('status') == 'success' and data.get('data', {}).get('records'):
            record = data['data']['records'][0]
            
            result = format_header("📱", "MOBILE NUMBER DETAILS") + "\n"
            result += add_field("📞", "Number", data['data'].get('mobile'))
            result += add_field("👤", "Name", record.get('name'), False)
            result += add_field("👨", "Father", record.get('father_name'), False)
            result += add_field("📡", "Circle", record.get('circle'), False)
            result += add_field("🔄", "Alternate", record.get('alternate_mobile'))
            result += add_field("🆔", "ID", record.get('id'))
            
            addr_field = add_field("📍", "Address", record.get('address'), False)
            if addr_field:
                result += format_separator() + "\n" + addr_field
            
            return result.strip()
        
        return format_no_results(number)
        
    except Exception as e:
        logger.error(f"Mobile search error: {e}")
        return format_error("Error", str(e))

async def search_vehicle_info(rc: str, api_choice: int = 1) -> str:
    """Search vehicle registration information"""
    try:
        if api_choice == 1:
            response = requests.get(VEHICLE_API_1.format(rc), timeout=15)
            data = response.json()
            
            if data.get('success') and data.get('vehicle_info'):
                v = data['vehicle_info']
                
                result = format_header("🚗", "VEHICLE DETAILS") + "\n"
                result += add_field("🔢", "RC", safe_get(v, 'registration_number'))
                
                # Ownership Info
                own = v.get('ownership', {})
                result += add_field("👤", "Owner", own.get('owner_name'), False)
                result += add_field("👨", "Father", own.get('father_name'), False)
                result += add_field("🔢", "Owner Serial", own.get('owner_serial'))
                
                # Specs Info
                specs = v.get('vehicle_specs', {})
                result += add_field("🏭", "Maker", specs.get('model_name'), False)
                result += add_field("🚘", "Model", specs.get('maker_model'), False)
                result += add_field("🚌", "Class", specs.get('vehicle_class'), False)
                result += add_field("⛽", "Fuel", specs.get('fuel_type'), False)
                result += add_field("⚙️", "CC", specs.get('cubic_capacity'))
                result += add_field("💺", "Seats", specs.get('seating_capacity'))
                result += add_field("⚙️", "Chassis", specs.get('chassis_number'))
                result += add_field("⚙️", "Engine", specs.get('engine_number'))
                
                # Insurance Info
                ins = v.get('insurance', {})
                ins_company = add_field("🛡️", "Insurance", ins.get('insurance_company'), False)
                ins_policy = add_field("📄", "Policy", ins.get('insurance_number'))
                ins_expiry = add_field("📅", "Expiry", ins.get('insurance_expiry'))
                if ins_company or ins_policy or ins_expiry:
                    result += format_separator() + "\n"
                    result += ins_company + ins_policy + ins_expiry
                
                # Validity Info
                val = v.get('validity', {})
                val_reg = add_field("📅", "Reg Date", val.get('registration_date'))
                val_age = add_field("⏳", "Age", val.get('vehicle_age'), False)
                val_fit = add_field("✅", "Fitness Upto", val.get('fitness_upto'))
                val_tax = add_field("💰", "Tax Paid Upto", val.get('tax_upto'))
                puc_num = val.get('puc_number')
                puc_field = add_field("🛡️", "PUC No", puc_num)
                puc_expiry = add_field("📅", "PUC Upto", val.get('puc_upto'))
                
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
                
                rto_field = add_field("🏢", "RTO", rto_val, False)
                rto_phone = add_field("📞", "RTO Phone", rto.get('phone'))
                
                # Address extraction (rto_contact.address or ownership.registered_rto fallback)
                addr = rto.get('address')
                if not addr or addr == 'N/A':
                    addr = own.get('registered_rto')
                addr_field = add_field("📍", "Address", addr, False)
                
                if rto_field or rto_phone or addr_field:
                    result += format_separator() + "\n"
                    result += rto_field + rto_phone + addr_field
                
                return result.strip()
            
            return format_no_results(rc)
        
        else:
            response = requests.get(VEHICLE_API_2.format(rc), timeout=25)
            data = response.json()
            
            if data:
                result = format_header("🚙", "VEHICLE DETAILS (API 2)") + "\n"
                
                # Check if there is a nested 'formatted' or 'Formatted' key
                v_data = {}
                if isinstance(data, dict):
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
                                    field_str = add_field(emoji, label, val, is_code)
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
                            extra_fields_str += add_field("📋", label, val_str, is_code)
                    
                    if extra_fields_str:
                        result += format_separator() + "\n" + extra_fields_str
                    
                    return result.strip()
            
            return format_no_results(rc)
            
    except Exception as e:
        logger.error(f"Vehicle search error: {e}")
        return format_error("Error", str(e))

async def search_pan_info(pan: str) -> str:
    """Search PAN card information"""
    try:
        response = requests.get(PAN_API.format(pan), timeout=15)
        data = response.json()
        
        if data.get('success') and data.get('pan_info'):
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
            result += add_field("📇", "PAN", p.get('pan_number'))
            result += add_field("👤", "Name", p.get('name'), False)
            result += add_field("👨", "Father", p.get('father_name'), False)
            result += add_field("📅", "DOB", p.get('dob'), False)
            result += add_field("👥", "Gender", gender, False)
            
            income = p.get('monthly_income')
            income_str = f"₹{income}/month" if income is not None and str(income).strip().upper() not in ['', 'N/A', 'NA', 'NONE', 'NULL'] else None
            result += add_field("💰", "Income", income_str, False)
            result += add_field("📞", "Phone", p.get('phone'))
            
            addr_field = add_field("📍", "Address", p.get('address'), False)
            if addr_field:
                result += format_separator() + "\n" + addr_field
            
            return result.strip()
        
        return format_no_results(pan)
        
    except Exception as e:
        logger.error(f"PAN search error: {e}")
        return format_error("Error", str(e))

async def search_github_info(username: str) -> str:
    """Search GitHub profile information"""
    try:
        response = requests.get(GITHUB_API.format(username), timeout=15)
        if response.status_code == 404:
            return format_no_results(username)
        
        d = response.json()
        
        result = format_header("💻", "GITHUB PROFILE") + "\n"
        result += add_field("🔑", "Username", d.get('login'))
        result += add_field("👤", "Name", d.get('name'), False)
        result += add_field("🏢", "Company", d.get('company'), False)
        result += add_field("📍", "Location", d.get('location'), False)
        result += add_field("📝", "Bio", d.get('bio'), False)
        result += add_field("🌐", "Blog", d.get('blog'), False)
        
        stats_str = ""
        stats_str += add_field("📚", "Repos", d.get('public_repos'), False)
        stats_str += add_field("👥", "Followers", d.get('followers'), False)
        stats_str += add_field("👣", "Following", d.get('following'), False)
        stats_str += add_field("🔗", "Profile", d.get('html_url'), False)
        
        if stats_str:
            result += format_separator() + "\n" + stats_str
            
        return result.strip()
        
    except Exception as e:
        logger.error(f"GitHub search error: {e}")
        return format_error("Error", str(e))

def format_leak_page(results, query, page_index=0):
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
                        record_fields_str += add_field(emoji, label, val_str, is_code)
                        shown_fields.add(key)
            
            # Show extra fields
            extra_fields = {k: v for k, v in record.items() 
                          if k not in shown_fields and v and not k.startswith('_')}
            for key, value in extra_fields.items():
                val_str = str(value).strip()
                if val_str.upper() not in ['', 'N/A', 'NA', 'NONE', 'NULL']:
                    is_code = any(x in key.lower() for x in ['number', 'no', 'code', 'id', 'license', 'pan', 'aadhaar', 'email', 'phone', 'mobile'])
                    label = key.replace('_', ' ').title()
                    record_fields_str += add_field("🔹", label, val_str, is_code)
            
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
        response = requests.get(LEAK_API.format(query), timeout=20)
        
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
    keyboard = [
        [InlineKeyboardButton("📱 Mobile Search", callback_data='mobile')],
        [InlineKeyboardButton("🚗 Vehicle API 1", callback_data='vehicle1'), 
         InlineKeyboardButton("🚙 Vehicle API 2", callback_data='vehicle2')],
        [InlineKeyboardButton("📄 PAN Card", callback_data='pan'),
         InlineKeyboardButton("💻 GitHub", callback_data='github')],
        [InlineKeyboardButton("🕵️ Leak OSINT", callback_data='leak')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome = f"""🔍 <b>DetailDrop Bot</b>
━━━━━━━━━━━━━━━━━━━━
Welcome {update.effective_user.first_name}!

Tap one of the interactive options below to search immediately.
━━━━━━━━━━━━━━━━━━━━
📖 <b>Quick Command Guide:</b>
• 📱 Mobile: <code>/mobile 9876543210</code>
• 🚗 Vehicle 1: <code>/vehicle1 DL3CAS1234</code>
• 🚙 Vehicle 2: <code>/vehicle2 DL3CAS1234</code>
• 📄 PAN: <code>/pan ABCDE1234F</code>
• 💻 GitHub: <code>/github username</code>
• 🕵️ Leak: <code>/leak email_or_phone</code>
━━━━━━━━━━━━━━━━━━━━"""
    
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
    
    msg = await update.message.reply_text("🔍 <b>Searching...</b>", parse_mode='HTML')
    result = await search_mobile_info(context.args[0])
    await send_formatted_message(update, result, msg)

async def vehicle1_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct vehicle API 1 search command"""
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /vehicle1 DL3CAS1234"),
            parse_mode='HTML'
        )
        return
    
    msg = await update.message.reply_text("🔍 <b>Searching API 1...</b>", parse_mode='HTML')
    result = await search_vehicle_info(context.args[0].upper(), 1)
    await send_formatted_message(update, result, msg)

async def vehicle2_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct vehicle API 2 search command"""
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /vehicle2 DL3CAS1234"),
            parse_mode='HTML'
        )
        return
    
    msg = await update.message.reply_text("🔍 <b>Searching API 2...</b>", parse_mode='HTML')
    result = await search_vehicle_info(context.args[0].upper(), 2)
    await send_formatted_message(update, result, msg)

async def pan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct PAN search command"""
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /pan ABCDE1234F"),
            parse_mode='HTML'
        )
        return
    
    msg = await update.message.reply_text("🔍 <b>Searching...</b>", parse_mode='HTML')
    result = await search_pan_info(context.args[0].upper())
    await send_formatted_message(update, result, msg)

async def github_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct GitHub search command"""
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /github username"),
            parse_mode='HTML'
        )
        return
    
    msg = await update.message.reply_text("🔍 <b>Searching...</b>", parse_mode='HTML')
    result = await search_github_info(context.args[0])
    await send_formatted_message(update, result, msg)

async def leak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct leak search command"""
    if not context.args:
        await update.message.reply_text(
            format_error("Missing Input", "Usage: /leak phone or email"),
            parse_mode='HTML'
        )
        return
    
    query = ' '.join(context.args)
    msg = await update.message.reply_text("🔍 <b>Searching leak database...</b>", parse_mode='HTML')
    results = await search_leak_info(query)
    
    if isinstance(results, str):
        # API returned an error string
        await msg.edit_text(format_error("Error", results), parse_mode='HTML')
        return
        
    if not results:
        await msg.edit_text(format_no_results(query), parse_mode='HTML')
        return
        
    # Cache results in user_data
    context.user_data['leak_query'] = query
    context.user_data['leak_results'] = results
    
    text, reply_markup = format_leak_page(results, query, 0)
    await msg.edit_text(text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)

# ==================== CONVERSATION HANDLERS ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses"""
    query = update.callback_query
    await query.answer()
    option = query.data
    
    if option.startswith('leak_page:'):
        page_index = int(option.split(':')[1])
        results = context.user_data.get('leak_results')
        l_query = context.user_data.get('leak_query', '')
        if results:
            text, reply_markup = format_leak_page(results, l_query, page_index)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)
        else:
            await query.edit_message_text(format_error("Session Expired", "Please search again using /leak."), parse_mode='HTML')
        return ConversationHandler.END
        
    elif option == 'mobile':
        await query.edit_message_text(
            "📱 Send 10-digit mobile number:\nExample: <code>9876543210</code>",
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
        await query.edit_message_text(
            "🚗 API 1: Send vehicle number\nExample: <code>DL3CAS1234</code>",
            parse_mode='HTML'
        )
        return WAITING_VEHICLE
        
    elif option == 'vehicle2':
        context.user_data['vehicle_api'] = 2
        await query.edit_message_text(
            "🚙 API 2: Send vehicle number\nExample: <code>DL3CAS1234</code>",
            parse_mode='HTML'
        )
        return WAITING_VEHICLE
        
    elif option == 'pan':
        await query.edit_message_text(
            "📄 Send PAN number:\nExample: <code>ABCDE1234F</code>",
            parse_mode='HTML'
        )
        return WAITING_PAN
        
    elif option == 'github':
        await query.edit_message_text("💻 Send GitHub username:")
        return WAITING_GITHUB
        
    elif option == 'leak':
        await query.edit_message_text("🕵️ Send phone or email:")
        return WAITING_LEAK
        
    elif option == 'start':
        await start(update, context)
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
    
    msg = await update.message.reply_text("🔍 <b>Searching...</b>", parse_mode='HTML')
    result = await search_mobile_info(num)
    await send_formatted_message(update, result, msg)
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
    
    api_name = "API 1" if api == 1 else "API 2"
    msg = await update.message.reply_text(f"🔍 <b>Searching {api_name}...</b>", parse_mode='HTML')
    result = await search_vehicle_info(rc, api)
    await send_formatted_message(update, result, msg)
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
    
    msg = await update.message.reply_text("🔍 <b>Searching...</b>", parse_mode='HTML')
    result = await search_pan_info(pan)
    await send_formatted_message(update, result, msg)
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
    
    msg = await update.message.reply_text("🔍 <b>Searching...</b>", parse_mode='HTML')
    result = await search_github_info(username)
    await send_formatted_message(update, result, msg)
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
    
    text, reply_markup = format_leak_page(results, query, 0)
    await msg.edit_text(text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)
    return ConversationHandler.END

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
        
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler for button flow
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            WAITING_MOBILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mobile)],
            WAITING_VEHICLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vehicle)],
            WAITING_PAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pan)],
            WAITING_GITHUB: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_github)],
            WAITING_LEAK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_leak)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add all handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('mobile', mobile_cmd))
    app.add_handler(CommandHandler('vehicle1', vehicle1_cmd))
    app.add_handler(CommandHandler('vehicle2', vehicle2_cmd))
    app.add_handler(CommandHandler('vehicle', vehicle1_cmd))  # Alias
    app.add_handler(CommandHandler('pan', pan_cmd))
    app.add_handler(CommandHandler('github', github_cmd))
    app.add_handler(CommandHandler('leak', leak_cmd))
    app.add_handler(conv_handler)
    
    print("[INFO] Bot is running!")
    print("[INFO] Press Ctrl+C to stop")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()