import asyncio
import os
import json
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    CommandHandler, 
    CallbackQueryHandler
)
from playwright.async_api import async_playwright

# --- الآي دي الخاص بك المسموح له باستخدام البوتات ---
ADMIN_USER_ID = 6836512592

# --- الـ sessionid الخاص بحسابك الوهمي ---
INSTAGRAM_SESSION_ID = "29263544035%3A6QmJFFM4KBu8DG%3A11%3AAYljKBPj0DrJnYSALDXcEt3uw7WN30A-Gre-bidQdg"

# --- ملف لحفظ الحسابات قيد المراقبة لضمان عدم ضياعها عند إعادة التشغيل ---
DATA_FILE = "tracking_data.json"
active_tasks = {}  # لتخزين مهام الـ asyncio النشطة

# --- إعداد خادم ويب وهمي لمنع انطفاء المنصة ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bots are running and active!"

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
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("عذراً، هذا البوت خاص ولا يسمح لأحد باستخدامه غير مالكه! 🔒")
        return

    await update.message.reply_text(
        "أهلاً بك يا مالكي في بوت مراقبة إنستغرام المطوّر! 🕵️‍♂️✨\n\n"
        " الأوامر المتاحة:\n"
        "• /track username - لبدء مراقبة حساب\n"
        "• /stop username - لإيقاف مراقبة حساب\n"
        "• /list - لعرض الحسابات قيد المراقبة حالياً"
    )

async def check_account_status(username):
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, 
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
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
                return False, None, None

            await page.wait_for_timeout(3000)
            
            try:
                await page.evaluate("""() => {
                    const dialogs = document.querySelectorAll("div[role='dialog']");
                    dialogs.forEach(el => el.style.display = 'none');
                    const backdrops = document.querySelectorAll("div._acaz, div[class*='x1s85apg']");
                    backdrops.forEach(el => el.style.display = 'none');
                    document.body.style.overflow = 'auto';
                    document.documentElement.style.overflow = 'auto';
                }""")
            except Exception:
                pass
            
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1500)
            
            page_content = await page.content()
            page_text = await page.evaluate("() => document.body.innerText")
            
            not_available_phrases = [
                "Profile isn't available", "isn't available", 
                "Sorry, this page isn't available", "عذراً، هذه الصفحة غير متوفرة", 
                "The link you followed may be broken", "Page not found"
            ]
            
            is_unavailable = any(phrase.lower() in page_content.lower() or phrase.lower() in page_text.lower() for phrase in not_available_phrases)
            
            if is_unavailable:
                await browser.close()
                return False, None, None

            profile_info = await page.evaluate("""() => {
                try {
                    const metaDes = document.querySelector('meta[property="og:description"]');
                    let text = metaDes ? metaDes.content : "";
                    const isVerified = document.querySelector("svg[aria-label='Verified']") !== null;
                    return { description: text, verified: isVerified };
                } catch (e) {
                    return { description: "", verified: false };
                }
            }""")
            
            if not profile_info.get("description") or "isn't available" in profile_info.get("description"):
                await browser.close()
                return False, None, None

            screenshot_path = f"active_{username}_{int(datetime.now().timestamp())}.png"
            await page.screenshot(path=screenshot_path, full_page=False)
            await browser.close()
            
            return True, profile_info, screenshot_path
            
    except Exception as e:
        if browser:
            try:
                await browser.close()
            except:
                pass
        return False, None, None

async def monitor_account_background(chat_id, username, context, initial_message):
    start_time = datetime.now()
    await initial_message.edit_text(f"👀 بدأت مراقبة الحساب @{username} بصمت...\nسأنتظر أي تغيير في حالته (فتح/قفل)!")
    
    # حفظ في قاعدة البيانات المحلية
    data = load_data()
    data[username] = {
        "chat_id": chat_id,
        "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
        "last_status": None  # لم نحدد حالته بعد
    }
    save_data(data)

    try:
        while True:
            is_active, info, screenshot_path = await check_account_status(username)
            current_data = load_data()
            
            # إذا تم حذف الحساب من القائمة عبر أمر /stop
            if username not in current_data:
                break
                
            last_status = current_data[username].get("last_status")

            # الحالة الأولى: الحساب أصبح نشطاً (كان مقفلاً وصار مفتوحاً)
            if is_active and last_status != "active":
                end_time = datetime.now()
                desc = info.get("description", "لا توجد تفاصيل")
                verified_badge = "✅ نعم (موثق)" if info.get("verified") else "❌ لا (غير موثق)"
                
                caption = (
                    f"🎉 **تنبيه: تم فك البند أو فتح الحساب @{username}!**\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"🔗 **الرابط:** https://instagram.com/{username}\n"
                    f"📊 **التفاصيل:** {desc}\n"
                    f"🏅 **حالة التوثيق:** {verified_badge}\n"
                    f"🔓 **وقت الفتح:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                
                with open(screenshot_path, "rb") as photo:
                    await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, parse_mode="Markdown")
                
                if os.path.exists(screenshot_path):
                    os.remove(screenshot_path)
                
                # تحديث الحالة إلى نشط
                current_data[username]["last_status"] = "active"
                save_data(current_data)

            # الحالة الثانية: الحساب قفل أو تبند (كان مفتوحاً وصار مقفلاً)
            elif not is_active and last_status == "active":
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️️ **تنبيه خطير:** الحساب @{username} تم قفله أو تبنده الآن! 🚨",
                    parse_mode="Markdown"
                )
                current_data[username]["last_status"] = "inactive"
                save_data(current_data)

            await asyncio.sleep(120)
            
    except asyncio.CancelledError:
        # عند إيقاف المهمة يدوياً
        pass
    except Exception as e:
        await asyncio.sleep(120)

async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        return

    if not context.args:
        await update.message.reply_text("الرجاء كتابة اليوزر بعد الأمر. مثال:\n/track elonmusk")
        return
    
    username = context.args[0].replace("@", "").strip()
    chat_id = update.effective_chat.id
    
    if username in active_tasks and not active_tasks[username].done():
        await update.message.reply_text(f"⚠️ الحساب @{username} قيد المراقبة بالفعل!")
        return

    status_message = await update.message.reply_text(f"🔍 جاري إعداد مراقبة الحساب @{username}...")
    task = asyncio.create_task(monitor_account_background(chat_id, username, context, status_message))
    active_tasks[username] = task

async def stop_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        return

    if not context.args:
        await update.message.reply_text("الرجاء كتابة اليوزر المراد إيقافه. مثال:\n/stop elonmusk")
        return
    
    username = context.args[0].replace("@", "").strip()
    
    # إيقاف المهمة الفعالة إن وجدت
    if username in active_tasks:
        active_tasks[username].cancel()
        del active_tasks[username]
    
    # حذف من ملف الحفظ
    data = load_data()
    if username in data:
        del data[username]
        save_data(data)
        await update.message.reply_text(f"🛑 تم إيقاف مراقبة الحساب @{username} بنجاح.")
    else:
        await update.message.reply_text(f"⚠️ الحساب @{username} غير موجود في قائمة المراقبة.")

async def list_tracked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        return

    data = load_data()
    if not data:
        await update.message.reply_text("📁 لا توجد أي حسابات قيد المراقبة حالياً.")
        return
    
    msg = "📋 **قائمة الحسابات قيد المراقبة:**\n━━━━━━━━━━━━━━━━━━━\n"
    for username, info in data.items():
        msg += f"• @{username}\n  🕒 بدأ في: {info.get('start_time')}\n\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def run_bot(token):
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    app.add_handler(CommandHandler("stop", stop_user))
    app.add_handler(CommandHandler("list", list_tracked))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    print(f"تم تشغيل البوت بنجاح برمز التوكن: {token[:10]}...")

async def main():
    tokens = [
        "8487717218:AAHEOFV-KJz8HJORsl4JvSWPBWxVFM3sqEg",
        "8875867251:AAHEH5njF9zHBk_slXVo54ngOxg4dBoqY8U"
    ]
    
    # استئناف المراقبة للحسابات المحفوظة مسبقاً في حال أُعيد تشغيل السكربت
    # (يمكنك تفعيل الاستئناف التلقائي هنا لاحقاً إذا احتجت)
    
    await asyncio.gather(*(run_bot(token) for token in tokens))
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
