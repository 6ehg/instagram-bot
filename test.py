import asyncio
import os
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from playwright.async_api import async_playwright

# --- الآي دي الأساسي لمالك البوت ---
ADMIN_USER_ID = 6836512592

# --- الـ sessionid الخاص بحسابك الوهمي لحل مشكلة الحسابات التي بها شرطة _ _ _
INSTAGRAM_SESSION_ID = "29263544035%3A6QmJFFM4KBu8DG%3A11%3AAYljKBPj0DrJnYSALDXcEt3uw7WN30A-Gre-bidQdg"

# --- قوائم إدارة لوحة التحكم ---
banned_users = set()
admins = {ADMIN_USER_ID}
users = {}
broadcast_list = []
username_to_id = {}
user_states = {}

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

def get_admin_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="manage_users")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="statistics")],
        [InlineKeyboardButton("📢 الإذاعة", callback_data="broadcast")]
    ])
    return markup

def get_manage_users_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="ban_user")],
        [InlineKeyboardButton("🔓 فك الحظر", callback_data="unban_user")],
        [InlineKeyboardButton("➕ إضافة أدمن", callback_data="add_admin")],
        [InlineKeyboardButton("➖ حذف أدمن", callback_data="remove_admin")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]
    ])
    return markup

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if user_id in banned_users:
        await update.message.reply_text("أنت محظور من استخدام هذا البوت.")
        return

    if user_id not in users:
        users[user_id] = {"username": username, "joined": datetime.now()}
        if user_id not in broadcast_list:
            broadcast_list.append(user_id)
            
    if username:
        username_to_id[username.lower()] = user_id
    
    if user_id in admins:
        await update.message.reply_text(
            "مرحبًا بك في لوحة التحكم وبوت مراقبة إنستغرام الذكي! 🕵️‍♂️✨\n\n"
            "للمراقبة السريعة، أرسل:\n/track username",
            reply_markup=get_admin_menu()
        )
    else:
        await update.message.reply_text("عذراً، هذا البوت خاص ولا يسمح لأحد باستخدامه غير مالكه! 🔒")

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
                await page.evaluate("""() => {querySelectorAll("div[role='dialog']");
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
                "Profile isn't available", "isn't available", "Sorry, this page isn't available",
                "عذراً، هذه الصفحة غير متوفرة", "The link you followed may be broken", "Page not found"
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
    await initial_message.edit_text(f"👀 بدأت مراقبة الحساب @{username} بصمت...\nسأنتظر حتى يفتح الحساب حقيقة وسأرسل لك التقرير فوراً عند عودته!")
    
    while True:
        try:
            is_active, info, screenshot_path = await check_account_status(username)
            
            if is_active:
                end_time = datetime.now()
                duration = end_time - start_time
                total_seconds = int(duration.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                
                desc = info.get("description", "لا توجد تفاصيل")
                verified_badge = "✅ نعم (موثق)" if info.get("verified") else "❌ لا (غير موثق)"
                
                caption = (
                    f"🎉 **تم فك البند عن الحساب أو أصبح موجوداً!**\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 اليوزر: @{username}\n"
                    f"🔗 الرابط: https://instagram.com/{username}\n"
                    f"📊 التفاصيل: {desc}\n"
                    f"🏅 حالة التوثيق: {verified_badge}\n"
                    f"🕒 بدء المراقبة: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"🔓 وقت الظهور/الفتح: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"⏱ مدة المراقبة: {hours} hours {minutes} minutes\n\n"
                    f"💡 هذا الحساب أصبح نشطاً وشغالاً الآن على إنستغرام."
                )
                keyboard = [[InlineKeyboardButton("🔄 فحص مرة أخرى", callback_data=f"refresh_{username}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                with open(screenshot_path, "rb") as photo:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=caption,
                        parse_mode="Markdown",
                        reply_markup=reply_markup
                    )
                
                if os.path.exists(screenshot_path):
                    os.remove(screenshot_path)
                break
            else:
                await asyncio.sleep(120)
                
        except Exception as e:
            await asyncio.sleep(120)

async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        await update.message.reply_text("عذراً، هذا الأمر مخصص للأدمنية فقط! ❌")
        return

    if not context.args:
        await update.message.reply_text("الرجاء كتابة اليوزر بعد الأمر. مثال:\n/track elonmusk")
        return
    
    username = context.args[0].replace("@", "").strip()
    chat_id = update.effective_chat.id
    
    status_message = await update.message.reply_text(f"🔍 جاري إعداد مراقبة الحساب @{username}...")
    asyncio.create_task(monitor_account_background(chat_id, username, context, status_message))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id not in admins:
        await query.answer("هذا الزر ليس لك!", show_alert=True)
        return

    await query.answer()
    data = query.data
    
    if data == "manage_users":
        await query.message.edit_text("إدارة المستخدمين:", reply_markup=get_manage_users_menu())
    
    elif data == "main_menu":
        await query.message.edit_text("مرحبًا بك في لوحة التحكم:", reply_markup=get_admin_menu())
        
    elif data == "ban_user":
        user_states[user_id] = "waiting_ban"
        await query.message.reply_text("أرسل معرف المستخدم (آي دي) أو يوزره (مثال: @username):")
    
    elif data == "unban_user":
        user_states[user_id] = "waiting_unban"
        await query.message.reply_text("أرسل معرف المستخدم أو يوزره لفك الحظر عنه:")
    
    elif data == "add_admin":
        user_states[user_id] = "waiting_add_admin"
        await query.message.reply_text("أرسل معرف المستخدم أو يوزره لإضافته كأدمن:")
    
    elif data == "remove_admin":
        user_states[user_id] = "waiting_remove_admin"
        await query.message.reply_text("أرسل معرف المستخدم أو يوزره لحذفه من الأدمن:")

    elif data == "statistics":
        total_users = len(users)
        last_users = list(users.keys())[-10:]
        last_users_str = "\n".join([f"@{users[u]['username']}" if users[u]['username'] else str(u) for u in last_users])
        stats = f"📊 Total Users: {total_users}\nLast 10 Users:\n{last_users_str}"
        await query.message.reply_text(stats)
    
    elif data == "broadcast":
        user_states[user_id] = "waiting_broadcast"
        await query.message.reply_text("أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:")

    elif data.startswith("refresh_"):
        username = data.replace("refresh_", "")
        chat_id = query.message.chat_id
        status_msg = await query.message.reply_text(f"🔄 جاري الفحص اليدوي لـ @{username}...")
        
        is_active, info, screenshot_path = await check_account_status(username)
        if is_active:
            desc = info.get("description", "لا توجد تفاصيل")
            caption = f"👤 حساب @{username} شغال حالياً!\n📊 التفاصيل: {desc}"
            with open(screenshot_path, "rb") as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
        else:
            await query.message.reply_text(f"❌ الحساب @{username} ما زال غير موجود أو مقفلاً.")
        await status_msg.delete()

def resolve_target_id(text):
    text = text.strip()
    if text.isdigit():
        return int(text)
    
    clean_username = text.replace("@", "").lower()
    if clean_username in username_to_id:
        return username_to_id[clean_username]
    
    return None

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        return

    state = user_states.get(user_id)
    if not state:
        return

    text = update.message.text.strip()
    
    if state == "waiting_ban":
        target_id = resolve_target_id(text)
        if target_id:
            banned_users.add(target_id)
            await update.message.reply_text(f"🚫 تم حظر المستخدم بنجاح: {target_id}")
        else:
            await update.message.reply_text("❌ لم يتم العثور على المستخدم! تأكد أنه أرسل /start للبوت سابقاً، أو أرسل الـ ID الرقمي مباشرة.")
            
    elif state == "waiting_unban":
        target_id = resolve_target_id(text)
        if target_id:
            banned_users.discard(target_id)
            await update.message.reply_text(f"🔓 تم فك الحظر عن المستخدم: {target_id}")
        else:
            await update.message.reply_text("❌ لم يتم العثور على المستخدم بهذا المعرف.")
            
    elif state == "waiting_add_admin":
        target_id = resolve_target_id(text)
        if target_id:
            admins.add(target_id)
            await update.message.reply_text(f"➕ تمت إضافة الأدمن بنجاح: {target_id}")
        else:
            await update.message.reply_text("❌ لم يتم العثور على المستخدم! تأكد أنه تفاعل مع البوت أولاً لكي يستطيع حفظ معرفه.")
            
    elif state == "waiting_remove_admin":
        target_id = resolve_target_id(text)
        if target_id:
            if target_id == ADMIN_USER_ID:
                await update.message.reply_text("لا يمكنك حذف المالك الأساسي!")
            else:
                admins.discard(target_id)
                await update.message.reply_text(f"➖ تم حذف الأدمن: {target_id}")
        else:
            await update.message.reply_text("❌ لم يتم العثور على هذا الأدمن.")
            
    elif state == "waiting_broadcast":
        success_count = 0
        for uid in broadcast_list:
            try:
                await context.bot.send_message(uid, text)
                success_count += 1
            except:
                pass
        await update.message.reply_text(f"📢 تم إرسال الإذاعة بنجاح إلى {success_count} مستخدم.")

    user_states.pop(user_id, None)

async def run_bot(token):
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    
    # تم تعديل طريقة تشغيل الـ Polling هنا لتصبح مستقرة ولا تنطفئ
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    print(f"تم تشغيل البوت بنجاح برمز التوكن: {token[:10]}...")

async def main():
    tokens = [
        "8487717218:AAHEOFV-KJz8HJORsl4JvSWPBWxVFM3sqEg",
        "8875867251:AAHEH5njF9zHBk_slXVo54ngOxg4dBoqY8U"
    ]
    
    await asyncio.gather(*(run_bot(token) for token in tokens))
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main()) const dialogs = document.
