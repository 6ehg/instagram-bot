import asyncio
import json
import os
import random
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

# --- الآي دي الخاص بك كمالك رئيسي للبوت ---
MASTER_ADMIN_ID = 6836512592 
USERS_FILE = "allowed_users.json"

active_tasks = {}
account_history = {} # ذاكرة مؤقتة لمقارنة التغيرات (البايو، الصورة، الستوري، التبنيد)

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    default_users = [MASTER_ADMIN_ID]
    save_users(default_users)
    return default_users

def save_users(users_list):
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(users_list, f)
    except Exception as e:
        print(f"Error saving users: {e}")

# --- إعداد خادم ويب وهمي لمنع انطفاء المنصة (Flask) ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Ultra-Pro Instagram Monitoring Bot is Active!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web_server, daemon=True).start()

# --- أوامر التحكم للبوت ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    allowed_users = load_users()
    
    if user_id not in allowed_users:
        await update.message.reply_text("عذراً، هذا البوت خاص ولا يسمح لك باستخدامه! 🔒")
        return

    msg = (
        "أهلاً بك في منظومة مراقبة إنستغرام الذكية والخارقة! 🕵️‍♂️🔥\n\n"
        "أمر المراقبة الشاملة (تغيرات، ستوري، تبنيد):\n"
        "👉 /track username\n\n"
    )
    if user_id == MASTER_ADMIN_ID:
        msg += (
            "أوامر الإدارة (خاصة بك):\n"
            "➕ /adduser [ID] - لإضافة مستخدم جديد\n"
            "➖ /removeuser [ID] - لحذف مستخدم\n"
            "📋 /userslist - لعرض المستخدمين المصرح لهم"
        )
    await update.message.reply_text(msg)

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != MASTER_ADMIN_ID:
        await update.message.reply_text("هذا الأمر مخصص لمالك البوت الرئيسي فقط! ❌")
        return

    if not context.args:
        await update.message.reply_text("الرجاء كتابة الآي دي المراد إضافته. مثال:\n/adduser 123456789")
        return

    try:
        new_user_id = int(context.args[0])
        allowed_users = load_users()
        if new_user_id in allowed_users:
            await update.message.reply_text("هذا المستخدم مضاف مسبقاً بالفعل! ⚠️")
            return
        
        allowed_users.append(new_user_id)
        save_users(allowed_users)
        await update.message.reply_text(f"✅ تم إضافة المستخدم بنجاح برقم: `{new_user_id}`", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("الآي دي يجب أن يكون أرقاماً صحيحة فقط! ❌")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != MASTER_ADMIN_ID:
        await update.message.reply_text("هذا الأمر مخصص لمالك البوت الرئيسي فقط! ❌")
        return

    if not context.args:
        await update.message.reply_text("الرجاء كتابة الآي دي المراد حذفه. مثال:\n/removeuser 123456789")
        return

    try:
        target_id = int(context.args[0])
        if target_id == MASTER_ADMIN_ID:
            await update.message.reply_text("لا يمكنك حذف المالك الأساسي للبوت! 🛑")
            return
            
        allowed_users = load_users()
        if target_id not in allowed_users:
            await update.message.reply_text("هذا المستخدم غير موجود في قائمة المصرح لهم! 🔍")
            return
            
        allowed_users.remove(target_id)
        save_users(allowed_users)
        await update.message.reply_text(f"🗑 تم حذف المستخدم `{target_id}` بنجاح من البوت.", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("الآي دي يجب أن يكون أرقاماً صحيحة فقط! ❌")

async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != MASTER_ADMIN_ID:
        await update.message.reply_text("هذا الأمر مخصص لمالك البوت الرئيسي فقط! ❌")
        return

    allowed_users = load_users()
    users_str = "\n".join([f"- `{uid}`" for uid in allowed_users])
    await update.message.reply_text(f"👥 **قائمة المستخدمين المسموح لهم:**\n{users_str}", parse_mode="Markdown")

# --- محرك الفحص المتطور الشامل ---

async def check_account_status(username):
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, 
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
            )
            
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15"
            ]
            
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=random.choice(user_agents)
            )
            
            page = await context.new_page()
            url = f"https://www.instagram.com/{username}/"
            response = await page.goto(url, timeout=60000)
            
            # 1. كاشف التبنيد والإغلاق (Ban Detector)
            if response and response.status >= 400:
                await browser.close()
                return False, {"status": "BANNED_OR_NOT_FOUND"}, None

            await page.wait_for_timeout(4000)
            
            # تنظيف الشاشة للحصول على صورة احترافية
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
            await page.wait_for_timeout(1000)
            
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
                return False, {"status": "BANNED_OR_NOT_FOUND"}, None

            # 2. استخراج البيانات المتقدمة (البايو، الصورة الشخصية، التوثيق، الستوري)
            profile_info = await page.evaluate("""() => {
                try {
                    const metaDes = document.querySelector('meta[property="og:description"]');
                    let text = metaDes ? metaDes.content : "";
                    const isVerified = document.querySelector("svg[aria-label='Verified']") !== null;
                    const profileImg = document.querySelector("header img") ? document.querySelector("header img").src : "";
                    const hasStory = document.querySelector("header canvas") !== null;
                    return { description: text, verified: isVerified, profile_pic: profileImg, has_story: hasStory };
                } catch (e) {
                    return { description: "", verified: false, profile_pic: "", has_story: false };
                }
            }""")
            
            if not profile_info.get("description") or "isn't available" in profile_info.get("description"):
                await browser.close()
                return False, {"status": "BANNED_OR_NOT_FOUND"}, None

            profile_info["status"] = "ACTIVE"

            screenshot_path = f"active_{username}_{int(datetime.now().timestamp())}.png"
            await page.screenshot(path=screenshot_path, full_page=False)
            await browser.close()
            
            return True, profile_info, screenshot_path
            
    except Exception as e:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        return False, None, None

# --- محرك المراقبة الشامل في الخلفية ---

async def monitor_account_background(chat_id, username, context, initial_message):
    start_time = datetime.now()
    await initial_message.edit_text(
        f"🕵️‍♂️ **بدأت المراقبة الفائقة للحساب @{username}**\n"
        f"سيقوم البوت بمراقبة (التبنيد/الفتح، تغيرات البايو، الصور الشخصية، والستوريات) بدقة متناهية!"
    )
    
    while True:
        try:
            is_active, info, screenshot_path = await check_account_status(username)
            last_state = account_history.get(username, {})

            # 1. حالة فك البند / أو صمود الحساب
            if is_active:
                desc = info.get("description", "لا توجد تفاصيل")
                verified_badge = "✅ نعم (موثق)" if info.get("verified") else "❌ لا (غير موثق)"
                
                changes = []
                
                # فحص تغير البايو أو التفاصيل
                if last_state.get("description") and last_state.get("description") != desc:
                    changes.append("📝 <b>تغيير في البايو أو الإحصائيات!</b>")
                
                # فحص الصورة الشخصية
                if last_state.get("profile_pic") and last_state.get("profile_pic") != info.get("profile_pic"):
                    changes.append("🖼️ <b>قام الحساب بتغيير الصورة الشخصية!</b>")
                    
                # فحص الستوري
                if info.get("has_story") and not last_state.get("has_story", False):
                    changes.append("📸 <b>تنبيه: الحساب نشر ستوري جديدة الآن!</b>")

                # إذا كان الحساب مبند مسبقاً وتفعل الآن (فك البند)
                if last_state.get("status") == "BANNED_OR_NOT_FOUND":
                    caption = (
                        f"🎉 <b>تم فك البند عن الحساب أو أصبح متوفراً الآن!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 اليوزر: @{username}\n"
                        f"🔗 الرابط: https://instagram.com/{username}\n"
                        f"📊 التفاصيل: {desc}\n"
                        f"🏅 التوثيق: {verified_badge}\n"
                        f"🕒 وقت الاكتشاف: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    keyboard = [[InlineKeyboardButton("🔄 فحص جديد", callback_data=f"refresh_{username}")]]
                    with open(screenshot_path, "rb") as photo:
                        await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
                
                # إذا حدثت تغييرات في الحساب المباشر
                elif changes:
                    change_caption = f"🔔 <b>تحديثات جديدة للحساب @{username}:</b>\n\n" + "\n".join(changes)
                    with open(screenshot_path, "rb") as photo:
                        await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=change_caption, parse_mode="HTML")

                # حفظ الحالة الأخيرة
                account_history[username] = info

                if screenshot_path and os.path.exists(screenshot_path):
                    os.remove(screenshot_path)

            # 2. حالة تبنيد أو إغلاق الحساب
            else:
                if info and info.get("status") == "BANNED_OR_NOT_FOUND":
                    if last_state.get("status") != "BANNED_OR_NOT_FOUND":
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"🚨 <b>تنبيه عاجل!</b>\n\nالحساب المراقَب <code>@{username}</code> مقفل أو تعرض للتبنيد/الحظر الآن!",
                            parse_mode="HTML"
                        )
                        account_history[username] = {"status": "BANNED_OR_NOT_FOUND"}

            # فحص دوري كل 3 إلى 5 دقائق بدون إجهاد
            sleep_time = random.randint(180, 300)
            await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            break
        except Exception as e:
            await asyncio.sleep(180)

async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    allowed_users = load_users()
    if user_id not in allowed_users:
        await update.message.reply_text("عذراً، هذا الأمر مخصص للمصرح لهم فقط! ❌")
        return

    if not context.args:
        await update.message.reply_text("الرجاء كتابة اليوزر بعد الأمر. مثال:\n/track elonmusk")
        return
    
    username = context.args[0].replace("@", "").strip()
    chat_id = update.effective_chat.id
    
    status_message = await update.message.reply_text(f"🔍 جاري تشغيل الرادار الخفي للحساب @{username}...")
    task = asyncio.create_task(monitor_account_background(chat_id, username, context, status_message))
    active_tasks[username] = task

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    allowed_users = load_users()
    if user_id not in allowed_users:
        await query.answer("هذا الزر ليس لك!", show_alert=True)
        return

    await query.answer()
    
    if query.data.startswith("refresh_"):
        username = query.data.replace("refresh_", "")
        chat_id = query.message.chat_id
        status_msg = await query.message.reply_text(f"🔄 جاري الفحص اللحظي لـ @{username}...")
        
        is_active, info, screenshot_path = await check_account_status(username)
        if is_active:
            desc = info.get("description", "لا توجد تفاصيل")
            caption = f"👤 **الحساب @{username} متوفر ونشط!**\n📊 التفاصيل: {desc}"
            with open(screenshot_path, "rb") as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, parse_mode="Markdown")
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
        else:
            await query.message.reply_text(f"❌ الحساب @{username} غير متوفر حالياً (مبند أو مقفل).")
        await status_msg.delete()

def main():
    # التوكن الخاص بك
    token = "8929977949:AAGNBKP_PuNMQe4FC6ps5dpCDZ8PDp8bMNU"
    
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("userslist", users_list))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("تم تشغيل منظومة المراقبة الشاملة بنجاح (جاهزة للعمل 24/7 على Railway)...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
