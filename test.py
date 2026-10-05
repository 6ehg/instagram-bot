import asyncio
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    CommandHandler, 
    CallbackQueryHandler
)
from playwright.async_api import async_playwright

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في بوت مراقبة إنستغرام الذكي والمطور! 🕵️‍♂️✨\n\n"
        "لبدء مراقبة حساب حتى يتم فك البند عنه وإرسال تقرير مفصل، أرسل الأمر هكذا:\n"
        "/track username"
    )

# دالة فحص حالة الحساب فقط (للتأكد هل هو شغال أم لا)
async def check_account_status(username):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, 
                args=["--disable-gpu", "--no-sandbox", "--disable-setuid-sandbox"]
            )
            context_browser = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context_browser.new_page()
            url = f"https://www.instagram.com/{username}/"
            
            response = await page.goto(url, timeout=40000)
            
            # إذا الصفحة غير موجودة أو فيها خطأ
            if response and response.status >= 400:
                await browser.close()
                return False, "غير متوفر", False

            await page.wait_for_timeout(2000)
            
            # فحص إذا كان الحساب محذوفاً أو عليه باند واضح
            content = await page.content()
            is_banned = "Sorry, this page isn't available." in content or "عذراً، هذه الصفحة غير متوفرة." in content
            
            if is_banned:
                await browser.close()
                return False, "الحساب محظور أو مغلق (Ban/Integrity)", False

            # استخراج معلومات الحساب إذا كان شغالاً
            profile_info = await page.evaluate("""() => {
                try {
                    const metaDes = document.querySelector('meta[property="og:description"]');
                    let text = metaDes ? metaDes.content : "غير متوفر";
                    const isVerified = document.querySelector("svg[aria-label='Verified']") !== null;
                    return { description: text, verified: isVerified };
                } catch (e) {
                    return { description: "غير متوفر", verified: false };
                }
            }""")
            
            # أخذ سكرين شوت للحالة النشطة
            screenshot_path = f"active_{username}_{int(datetime.now().timestamp())}.png"
            await page.screenshot(path=screenshot_path, full_page=False)
            await browser.close()
            
            return True, profile_info, screenshot_path
            
    except Exception as e:
        return False, str(e), False

# دالة المراقبة المستمرة في الخلفية
async def monitor_account_background(chat_id, username, context, initial_message):
    start_time = datetime.now()
    await initial_message.edit_text(f"👀 بدأت مراقبة الحساب @{username} في الخلفية...\nسيتم إخبارك فوراً وإرسال التقرير عند فك البند عنه وعودته للعمل!")
    
    while True:
        try:
            is_active, info, screenshot_path = await check_account_status(username)
            
            if is_active:
                # تم فك البند وأصبح الحساب نشطاً!
                end_time = datetime.now()
                duration = end_time - start_time
                total_seconds = int(duration.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                
                desc = info.get("description", "لا توجد تفاصيل")
                verified_badge = "✅ نعم (موثق)" if info.get("verified") else "❌ لا (غير موثق)"
                
                # صياغة التقرير الاحترافي المطابق لصورتك
                caption = (f"🎉 **تم فك البند عن الحساب!**\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 اليوزر: @{username}\n"
                    f"🔗 الرابط: https://instagram.com/{username}\n"
                    f"📊 التفاصيل: {desc}\n"
                    f"🏅 حالة التوثيق: {verified_badge}\n"
                    f"🕒 بدء المراقبة: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"🔓 وقت فك البند: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"⏱️ مدة المراقبة: {hours} hours {minutes} minutes ({round(duration.total_seconds() / 3600, 2)} hours)\n\n"
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
                
                # تنظيف الصورة المؤقتة
                if os.path.exists(screenshot_path):
                    os.remove(screenshot_path)
                    
                # حفظ في السجل
                with open("search_log.txt", "a", encoding="utf-8") as log_file:
                    log_file.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unbanned tracked @{username}\n")
                    
                break # الخروج وإيقاف المراقبة لأنه تم فك البند
            
            else:
                # الحساب ما زال مغلقاً، ننتظر دقيقتين ثم نعاود الفحص
                await asyncio.sleep(120)
                
        except Exception as e:
            await asyncio.sleep(120)

async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("الرجاء كتابة اليوزر بعد الأمر. مثال:\n/track elonmusk")
        return
    
    username = context.args[0].replace("@", "").strip()
    chat_id = update.effective_chat.id
    
    status_message = await update.message.reply_text(f"🔍 جاري إعداد مراقبة الحساب @{username}...")
    
    # تشغيل المراقبة في الخلفية
    asyncio.create_task(monitor_account_background(chat_id, username, context, status_message))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("refresh_"):
        username = query.data.replace("refresh_", "")
        chat_id = query.message.chat_id
        status_msg = await query.message.reply_text(f"🔄 جاري الفحص اليدوي السريع لـ @{username}...")
        
        is_active, info, screenshot_path = await check_account_status(username)
        if is_active:
            desc = info.get("description", "لا توجد تفاصيل")
            caption = f"👤 حساب @{username} شغال حالياً!\n📊 التفاصيل: {desc}"
            with open(screenshot_path, "rb") as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
            os.remove(screenshot_path)
        else:
            await query.message.reply_text(f"❌ الحساب @{username} ما زال مغلقاً أو محظوراً حالياً.")
        await status_msg.delete()

async def run_bot(token):
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    print(f"تم تشغيل البوت برمز التوكن: {token[:10]}...")

async def main():
    # جميع التوكنات الستة مدمجة هنا للعمل بالتوازي
    tokens = [
        "8875867251:AAHEH5njF9zHBk_slXVo54ngOxg4dBoqY8U",
        "8505165316:AAGIOPf61KpHSwLUuJrYS_HDla7J21KMgIA",
        "8956798204:AAGlyC_Ygh3YPB4GcBD5ZO8J0uZlhR7JExM",
        "8588371425:AAGiJgzXg_bxks7hdoR8bLm26z9s0NOIC_c",
        "8964756105:AAH4wa4yqm0cO1Zt3Y_lxIi5hEc6yc2KNMs",
        "8487717218:AAHEOFV-KJz8HJORsl4JvSWPBWxVFM3sqEg"
    ]
    
    await asyncio.gather(*(run_bot(token) for token in tokens))
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
