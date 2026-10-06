import asyncio
import os
import json
import threading
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    CommandHandler
)
from playwright.async_api import async_playwright

# --- الأيدي المسموح له فقط ---
ALLOWED_USER_IDS = [
    6836512592,  # الأيدي الخاص بك
]

# --- الـ sessionid الخاص بك ---
INSTAGRAM_SESSION_ID = "29263544035%3A6QmJFFM4KBu8DG%3A11%3AAYljKBPj0DrJnYSALDXcEt3uw7WN30A-Gre-bidQdg"

DATA_FILE = "tracking_data.json"
active_tasks = {}

# --- سيرفر بسيط لمنع إغلاق المنصة ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is active!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web_server, daemon=True).start()
# ---------------------------------------------

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        return
    await update.message.reply_text(
        "أهلاً بك! بوت مراقبة إنستغرام (تنبيه عند الإغلاق وعند العودة).\n\n"
        "الأوامر:\n"
        "• /track [يوزر] : لبدء المراقبة\n"
        "• /stop [يوزر] : لإيقاف المراقبة\n"
        "• /list : لعرض الحسابات"
    )

async def check_account_status(username):
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, 
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"]
            )
            context = await browser.new_context(viewport={"width": 1440, "height": 900})
            await context.add_cookies([
                {
                    "name": "sessionid",
                    "value": INSTAGRAM_SESSION_ID,
                    "domain": ".instagram.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True
                }
            ])
            
            page = await context.new_page()
            url = f"https://www.instagram.com/{username}/"
            response = await page.goto(url, timeout=60000)
            
            if response and response.status >= 400:
                await browser.close()
                return False, None

            await page.wait_for_timeout(3000)
            page_content = await page.content()
            page_text = await page.evaluate("() => document.body.innerText")
            
            not_available_phrases = [
                "Profile isn't available", "isn't available", 
                "Sorry, this page isn't available", "عذراً، هذه الصفحة غير متوفرة"
            ]
            
            is_unavailable = any(phrase.lower() in page_content.lower() or phrase.lower() in page_text.lower() for phrase in not_available_phrases)
            
            if is_unavailable:
                await browser.close()
                return False, None

            screenshot_path = f"active_{username}_{int(datetime.now().timestamp())}.png"
            await page.screenshot(path=screenshot_path, full_page=False)
            await browser.close()
            
            return True, screenshot_path
            
    except Exception as e:
        if browser:
            try:
                await browser.close()
            except:
                pass
        return False, None

async def monitor_account_background(chat_id, username, context):
    try:
        while True:
            is_active, screenshot_path = await check_account_status(username)
            current_data = load_data()
            
            if username not in current_data:
                break
                
            last_status = current_data[username].get("last_status")

            # 1. إذا الحساب كان شغال وفجأة تغلق/تبند
            if not is_active and last_status == "active":
                caption = f"🚨 **تنبيه: تم إغلاق/بند الحساب!**\n🔗 https://instagram.com/{username}"
                await context.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
                
                current_data[username]["last_status"] = "inactive"
                save_data(current_data)

            # 2. إذا الحساب كان مقفول ورجع اشتغل
            elif is_active and last_status == "inactive":
                caption = f"🎉 **تم فك البند ورجع الحساب للعمل بنجاح!**\n🔗 https://instagram.com/{username}"
                
                if screenshot_path and os.path.exists(screenshot_path):
                    with open(screenshot_path, "rb") as photo:
                        await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, parse_mode="Markdown")
                    os.remove(screenshot_path)
                else:
                    await context.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
                
                current_data[username]["last_status"] = "active"
                save_data(current_data)

            await asyncio.sleep(120)  # يفحص كل دقيقتين
            
    except asyncio.CancelledError:
        pass

async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        return

    if not context.args:
        await update.message.reply_text("الرجاء كتابة اليوزر. مثال:\n/track username")
        return
    
    username = context.args[0].replace("@", "").strip()
    chat_id = update.effective_chat.id
    
    if username in active_tasks and not active_tasks[username].done():
        await update.message.reply_text(f"⚠️ الحساب @{username} قيد المراقبة بالفعل!")
        return

    # فحص أولي لمعرفة حالته الحالية عند البدء
    is_active, _ = await check_account_status(username)
    initial_status = "active" if is_active else "inactive"

    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data = load_data()
    data[username] = {
        "chat_id": chat_id,
        "start_time": start_time,
        "last_status": initial_status
    }
    save_data(data)

    task = asyncio.create_task(monitor_account_background(chat_id, username, context))
    active_tasks[username] = task

    status_text = "يعمل حالياً ✅" if is_active else "مغلق/مبدأ حالياً ❌"
    await update.message.reply_text(f"👀 تمت إضافة الحساب @{username} للمراقبة!\nالحالة الآن: {status_text}\nسأبلغك فوراً إذا تغيرت حالته (سواء أغلق أو عاد للعمل).")

async def stop_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        return

    if not context.args:
        await update.message.reply_text("الرجاء كتابة اليوزر المراد إيقافه.")
        return
    
    username = context.args[0].replace("@", "").strip()
    
    if username in active_tasks:
        active_tasks[username].cancel()
        del active_tasks[username]
    
    data = load_data()
    if username in data:
        del data[username]
        save_data(data)
        await update.message.reply_text(f"🛑 تم إيقاف مراقبة الحساب @{username}.")
    else:
        await update.message.reply_text(f"⚠ الحساب @{username} غير موجود.")

async def list_tracked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        return

    data = load_data()
    if not data:
        await update.message.reply_text("📁 لا توجد حسابات قيد المراقبة حالياً.")
        return
    
    msg = "📋 **الحسابات قيد المراقبة:**\n\n"
    for username, info in data.items():
        status = "🟢 شغال" if info.get('last_status') == "active" else "🔴 مغلق/مبند"
        msg += f"• @{username} - {status}\n  🕒 بدأ في: {info.get('start_time')}\n\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

def main():
    token = "8487717218:AAHEOFV-KJz8HJORsl4JvSWPBWxVFM3sqEg"
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    app.add_handler(CommandHandler("stop", stop_user))
    app.add_handler(CommandHandler("list", list_tracked))
    
    app.run_polling()

if __name__ == "__main__":
    main()
