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
        "أهلاً بك في بوت مراقبة إنستغرام الذكي! 🕵️‍♂️✨\n\n"
        "أرسل الأمر هكذا لمراقبة أي حساب بصمت حتى يفتح:\n"
        "/track username"
    )

async def check_account_status(username):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-gpu"])
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            
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
                "Profile isn't available",
                "isn't available",
                "Sorry, this page isn't available",
                "عذراً، هذه الصفحة غير متوفرة",
                "The link you followed may be broken",
                "Page not found"
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
        return False, None, None

async def monitor_account_background(chat_id, username, context, initial_message):
    start_time = datetime.now()
    await initial_message.edit_text(f"👀 بدأت مراقبة الحساب @{username} بصمت...\nسأنتظر حتى يفتح الحساب حقيقة وسأرسل لك التقرير فوراً عند عودته!")
    
    while True:
        try:is_active, info, screenshot_path = await check_account_status(username)
            
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
                    
                with open("search_log.txt", "a", encoding="utf-8") as log_file:
                    log_file.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unbanned tracked @{username}\n")
                    
                break
            else:
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
    asyncio.create_task(monitor_account_background(chat_id, username, context, status_message))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("refresh_"):
        username = query.data.replace("refresh_", "")
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

async def run_bot(token):
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    print(f"تم تشغيل البوت بنجاح برمز التوكن: {token[:10]}...")

async def main():
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
