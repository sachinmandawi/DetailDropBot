# 🔎 DetailDropBot v3.0

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Telegram-Bot-blue?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram">
  <img src="https://img.shields.io/badge/Database-MongoDB-green?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License">
</p>

---

## 🌟 Overview
**DetailDropBot** is an advanced, multi-source intelligence OSINT Telegram Bot designed to fetch vehicle, mobile, PAN card, leak databases, and bank branch details under a uniform and masked framework.

---

## 🚀 Features

- 📱 **Mobile Lookup:** Name, circle, alternate phone numbers, and addresses.
- 🚗 **Double Vehicle APIs:** Supports fallback routing between two high-performance RTO databases.
- 📄 **PAN Card Lookup:** Name, Father's Name, DOB, Gender, Income and Address.
- 🕵️ **Leak OSINT Search:** Custom Cloudflare tunnel integration for email/phone leak databases with pagination.
- 🏦 **IFSC Bank Lookup:** Complete branch state, MICR, UPI, IMPS, NEFT, and RTGS payment statuses.
- 🎟️ **Promo Codes & Referral System:** Integrated dynamic credit rewards (+2 per referral) and free time-based passes.
- 🔐 **Force Join Verification:** Precise group and channel membership checks with custom top-bar Telegram alerts.

---

## 🛠️ Architecture & Flow

```mermaid
graph TD
    User([Telegram User]) -->|Callback / Command| Bot[DetailDropBot Core]
    Bot -->|Precheck| Access{Access Check}
    Access -->|Not Joined| JoinScreen[Force Join Screen]
    Access -->|No Credits| MaskedQuery[Masked Search Query]
    Access -->|Active Pass / Credit| FullQuery[Full Search Query]
    
    FullQuery & MaskedQuery --> APIs[(External OSINT APIs)]
    APIs --> ResultFormatter[Response Masker / Formatter]
    ResultFormatter --> User
```

---

## ⚙️ Configuration Variables

To deploy **DetailDropBot**, set the following environment variables:

| Environment Variable | Description |
| :--- | :--- |
| `BOT_TOKEN` | Your Telegram Bot Token from [@BotFather](https://t.me/BotFather) |
| `MONGO_URI` | MongoDB Atlas Connection String |
| `PORT` | Port for Render health-check HTTP server (Default: `8080`) |

---

## 📖 Quick Start Command Guide

### 🔍 Search Engines
* `/mobile <number>` — Search 10-digit mobile number details
* `/vehicle1 <RC>` — Check RTO database (API 1)
* `/vehicle2 <RC>` — Check RTO database (API 2)
* `/pan <PAN>` — Retrieve PAN card record
* `/leak <email_or_phone>` — Scan leak databases
* `/ifsc <IFSC>` — View bank branch payment details

### 👥 User Controls
* `/start` — Launch user menu panel
* `/profile` — View credits, time-passes, and invite link
* `/claim <code>` — Redeem promotional vouchers
* `/checkin` — Claim +1 free daily credit
* `/leaderboard` — Show top referring members

### 👑 Admin Management
* `/admin` — Open statistics dashboard
* `/addcredit <user_id> <amount>` — Add credits
* `/removecredit <user_id> <amount>` — Deduct credits
* `/addpass <user_id> <hours>` — Grant hourly time-pass
* `/addpassdays <user_id> <days>` — Grant daily time-pass
* `/userinfo <user_id>` — Fetch detailed user profile
* `/ban` / `/unban <user_id>` — Suspend/restore access
* `/reply <user_id> <msg>` — Reply to user support tickets
* `/broadcast` (Reply to message) — Send global broadcast
