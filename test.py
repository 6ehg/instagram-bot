import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from playwright.async_api import async_playwright

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في بوت مراقبة إنستغرام الذكي! 🕵️‍♂️✨\n\n"
        "لأخذ لقطة شاشة واضحة ونظيفة ومعرفة معلومات الحساب، أرسل الأمر هكذا:\n"
        "/track username"
    )

async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("الرجاء كتابة اليوزر بعد الأمر. مثال:\n/track elonmusk")
        return
    
    username = context.args[0].replace("@", "").strip()
    chat_id = update.effective_chat.id
    
    status_message = await update.message.reply_text(f"🔍 جاري فحص حساب @{username} والتقاط صورة واضحة...")
    
    start_time = datetime.now()
    screenshot_path = f"{username}.png"
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-gpu"])
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            
            url = f"https://www.instagram.com/{username}/"
            await page.goto(url, timeout=60000)
            
            await page.wait_for_timeout(5000)
            
            try:
                await page.evaluate("""() => {
                    const dialogs = document.querySelectorAll("div[role='dialog'], div._a23z, div._a8k_");
                    dialogs.forEach(el => el.remove());
                    
                    document.body.style.overflow = 'auto';
                    document.documentElement.style.overflow = 'auto';
                }""")
            except Exception:
                pass
            
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(2000)
            
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
            
            await page.screenshot(path=screenshot_path, full_page=False)
            await browser.close()
            
        end_time = datetime.now()
        duration = (end_time - start_time).seconds
        
        desc = profile_info.get("description", "لا توجد تفاصيل")
        verified_badge = "✅ نعم (موثق)" if profile_info.get("verified") else "❌ لا (غير موثق)"
        
        caption = (
            f"👤 معلومات حساب إنستغرام: @{username}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 التفاصيل: {desc}\n"
            f"🏅 حالة التوثيق: {verified_badge}\n"
            f"⏱️ استغرقت العملية: {duration} ثانية"
        )
        
        with open(screenshot_path, "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                parse_mode="Markdown"
            )
            
        await status_message.delete()
        
    except Exception as e:
        await status_message.edit_text(f"❌ حدث خطأ أثناء فحص الحساب @{username}:\n{e}")

def main():
    TOKEN = "8875867251:AAHEH5njF9zHBk_slXVo54ngOxg4dBoqY8U"
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    
    print("البوت يعمل الآن بوضوح عالي جداً...")
    app.run_polling()

if __name__ == "__main__":
    main()
