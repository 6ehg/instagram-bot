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
    
    status_message = await update.message.reply_text(f"🔍 جاري فحص حساب @{username}، إغلاق النوافذ، والتقاط صورة واضحة...")
    
    start_time = datetime.now()
    screenshot_path = f"{username}.png"
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-gpu"])
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            
            url = f"https://www.instagram.com/{username}/"
            await page.goto(url, timeout=60000)
            
            # 1. الانتظار حتى تفتح الصفحة مبدئياً
            await page.wait_for_timeout(4000)
            
            # 2. إغلاق وحذف نافذة تسجيل الدخول المنبثقة وتعتيم الخلفية من الـ DOM جذرياً
            try:
                await page.evaluate("""() => {
                    const dialogs = document.querySelectorAll("div[role='dialog'], div._a23z, div._a8k_, div[class*='x1n2onr6']");
                    dialogs.forEach(el => el.remove());
                    
                    // إزالة طبقات التعتيم السوداء الخلفية
                    const backdrops = document.querySelectorAll("div[class*='x1s85apg'], div._acaz");
                    backdrops.forEach(el => el.remove());
                    
                    document.body.style.overflow = 'auto';
                    document.documentElement.style.overflow = 'auto';
                }""")
            except Exception:
                pass
            
            # 3. ضغطة زر Escape احتياطية لإلغاء أي نافذة متبقية
            await page.keyboard.press("Escape")
            
            # 4. الانتظار حتى تختفي النافذة تماماً وتستقر بيانات المتابعين والحساب وتوضح الصورة
            await page.wait_for_timeout(3000)
            
            # استخراج معلومات الحساب بدقة
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
            
            # 5. التقاط لقطة الشاشة النظيفة بعد إزالة النافذة واستقرار العناصر
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

async def run_bot(token):
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    print(f"تم تشغيل البوت برمز التوكن: {token[:10]}...")

async def main():
    tokens = [
        "8875867251:AAHEH5njF9zHBk_slXVo54ngOxg4dBoqY8U",
        "8505165316:AAGIOPf61KpHSwLUuJrYS_HDla7J21KMgIA",
        "8956798204:AAGlyC_Ygh3YPB4GcBD5ZO8J0uZlhR7JExM"
    ]
    
    await asyncio.gather(*(run_bot(token) for token in tokens))
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
