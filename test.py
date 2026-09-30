import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from playwright.async_api import async_playwright

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في بوت مراقبة إنستغرام الاحترافي! 🕵️‍♂️\n\n"
        "لأخذ لقطة شاشة وفحص أي حساب، أرسل الأمر هكذا:\n"
        "/track username\n\n"
        "مثال:\n/track elonmusk"
    )

async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("الرجاء كتابة اليوزر بعد الأمر. مثال:\n/track elonmusk")
        return
    
    username = context.args[0].replace("@", "").strip()
    chat_id = update.effective_chat.id
    
    status_message = await update.message.reply_text(f"🔍 جاري فتح حساب @{username} وإزالة نافذة تسجيل الدخول...")
    
    start_time = datetime.now()
    screenshot_path = f"{username}.png"
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-gpu"])
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            
            url = f"https://www.instagram.com/{username}/"
            await page.goto(url, timeout=60000)
            
            # الانتظار قليلاً حتى تظهر النافذة المزعجة
            await page.wait_for_timeout(4000)
            
            # محاولة النقر على زر الإغلاق (X) إذا ظهرت النافذة
            try:
                # زر الإغلاق في انستغرام غالباً يكون عبارة عن زر أو أيقونة SVG داخل النافذة المنبثقة
                close_button = page.locator("div[role='dialog'] svg[aria-label='Close'], button:has(svg[aria-label='Close'])")
                if await close_button.is_visible(timeout=3000):
                    await close_button.click()
                    await page.wait_for_timeout(1000) # انتظار حتى تختفي النافذة
            except Exception:
                pass # لو لم تظهر النافذة، يكمل البوت بشكل طبيعي بدون مشاكل
            
            await page.screenshot(path=screenshot_path, full_page=False)
            await browser.close()
            
        end_time = datetime.now()
        duration = (end_time - start_time).seconds
        
        with open(screenshot_path, "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=f"📸 لقطة شاشة للحساب: @{username}\n⏱️ استغرقت العملية: {duration} ثانية"
            )
            
        await status_message.delete()
        
    except Exception as e:
        await status_message.edit_text(f"❌ حدث خطأ أثناء فحص الحساب @{username}:\n{e}")

def main():
    TOKEN = "8830810802:AAFbv4TqX-DJT6uidBwz9aM4aA2cucl_tOo"
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    
    print("البوت يعمل الآن ومزود بميزة إغلاق النوافذ المنبثقة...")
    app.run_polling()

if __name__ == "__main__":
    main()
