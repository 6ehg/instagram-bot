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
    
    status_message = await update.message.reply_text(f"🔍 جاري تحسين الإضاءة والتقاط صورة واضحة لحساب @{username}...")
    
    start_time = datetime.now()
    screenshot_path = f"{username}.png"
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-gpu"])
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            
            url = f"https://www.instagram.com/{username}/"
            await page.goto(url, timeout=60000)
            
            # الانتظار حتى تحميل الصفحة بالكامل
            await page.wait_for_timeout(4000)
            
            # تعديل ألوان الصفحة برمجياً لإزالة السواد وجعلها خلفية بيضاء واضحة
            try:
                await page.evaluate("""() => {
                    // إزالة النوافذ المنبثقة لتسجيل الدخول
                    const dialogs = document.querySelectorAll("div[role='dialog']");
                    dialogs.forEach(el => el.remove());
                    document.body.style.overflow = 'auto';
                    
                    // تغيير خلفية الموقع بالكامل إلى الأبيض الساطع وتعديل ألوان النصوص
                    document.body.style.backgroundColor = '#ffffff';
                    const mainContainer = document.querySelector('div._aa44');
                    if (mainContainer) {
                        mainContainer.style.backgroundColor = '#ffffff';
                    }
                    
                    // تطبيق اللون الأبيض على الخلفيات الداكنة العامة في الصفحة
                    document.querySelectorAll('*').forEach(el => {
                        const bg = window.getComputedStyle(el).backgroundColor;
                        if (bg === 'rgb(0, 0, 0)'  bg === 'rgb(24, 24, 24)'  bg === 'rgb(38, 38, 38)') {
                            el.style.backgroundColor = '#ffffff';
                        }
                    });
                }""")
                await page.wait_for_timeout(1000)
            except Exception:
                pass
            
            await page.screenshot(path=screenshot_path, full_page=False)
            await browser.close()
            
        end_time = datetime.now()
        duration = (end_time - start_time).seconds
        
        with open(screenshot_path, "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=f"📸 لقطة شاشة واضحة للحساب: @{username}\n⏱️ استغرقت العملية: {duration} ثانية"
            )
            
        await status_message.delete()
        
    except Exception as e:
        await status_message.edit_text(f"❌ حدث خطأ أثناء فحص الحساب @{username}:\n{e}")

def main():
    TOKEN = "8830810802:AAFbv4TqX-DJT6uidBwz9aM4aA2cucl_tOo"
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    
    print("البوت يعمل الآن ومزود بميزة إزالة السواد وتحسين الإضاءة...")
    app.run_polling()

if __name__ == "__main__":
    main()
