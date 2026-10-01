import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from playwright.async_api import async_playwright

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في بوت مراقبة إنستغرام الذكي! 🕵️‍♂️✨\n\n"
        "لأخذ لقطة شاشة نظيفة ومعرفة معلومات الحساب، أرسل الأمر هكذا:\n"
        "/track username"
    )

async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("الرجاء كتابة اليوزر بعد الأمر. مثال:\n/track elonmusk")
        return
    
    username = context.args[0].replace("@", "").strip()
    chat_id = update.effective_chat.id
    
    status_message = await update.message.reply_text(f"🔍 جاري فحص حساب @{username} على سطح المكتب وإغلاق النافذة...")
    
    start_time = datetime.now()
    screenshot_path = f"{username}.png"
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-gpu"])
            # شاشة كمبيوتر مكتبي واسعة ونظامية تماماً
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            
            url = f"https://www.instagram.com/{username}/"
            await page.goto(url, timeout=60000)
            
            # الانتظار حتى تظهر الصفحة والنافذة
            await page.wait_for_timeout(4000)
            
            # إغلاق النافذة المنبثقة وحذفها بالكامل من الشاشة بطريقة برمجية دقيقة
            try:
                await page.evaluate("""() => {
                    const dialogs = document.querySelectorAll("div[role='dialog'], div._a23z");
                    dialogs.forEach(el => el.remove());
                    
                    document.body.style.overflow = 'auto';
                    document.documentElement.style.overflow = 'auto';
                }""")
            except Exception:
                pass
            
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(2000)
            
            # استخراج معلومات الحساب وحالة التوثيق
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
            
            # تمرير بسيط والتقاط الصورة بمقاس دقيق لمنع ظهور المساحات البيضاء الفارغة
            await page.evaluate("window.scrollTo(0, 100);")
            await page.wait_for_timeout(1000)
            await page.screenshot(path=screenshot_path, full_page=False, clip={"x": 0, "y": 0, "width": 1280, "height": 720})
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
    # استخدام التوكن الجديد الخاص بك مباشرة
    TOKEN = "8875867251:AAHEH5njF9zHBk_slXVo54ngOxg4dBoqY8U"
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    
    print("البوت يعمل الآن بنظام الكمبيوتر وإغلاق النوافذ...")
    app.run_polling()

if __name__ == "__main__":
    main()
