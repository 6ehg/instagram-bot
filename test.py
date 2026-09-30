import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from playwright.async_api import async_playwright

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في بوت مراقبة إنستغرام الذكي والمطور! 🕵️‍♂️✨\n\n"
        "لأخذ لقطة شاشة صافية ومراقبة الحسابات، أرسل الأمر هكذا:\n"
        "/track username"
    )

async def check_and_send(context: ContextTypes.DEFAULT_TYPE, chat_id: int, username: str, start_time: datetime):
    screenshot_path = f"{username}.png"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-gpu"])
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            
            url = f"https://www.instagram.com/{username}/"
            response = await page.goto(url, timeout=60000)
            
            if response and response.status == 404:
                await browser.close()
                return False
            
            await page.wait_for_timeout(5000)
            
            try:
                await page.evaluate("""() => {
                    const dialogs = document.querySelectorAll("div[role='dialog'], div._a23z, div._a8k-");
                    dialogs.forEach(el => el.remove());
                    document.body.style.overflow = 'auto';
                    document.documentElement.style.overflow = 'auto';
                }""")
            except Exception:
                pass
            
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(2000)
            
            is_not_found = await page.evaluate("""() => {
                const bodyText = document.body.innerText;
                return bodyText.includes("Sorry, this page isn't available.") || bodyText.includes("عذراً، هذه الصفحة غير متوفرة.");
            }""")
            
            if is_not_found:
                await browser.close()
                return False
            
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
            
        found_time = datetime.now()
        total_duration = found_time - start_time
        
        hours, remainder = divmod(int(total_duration.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        time_str = ""
        if hours > 0:
            time_str += f"{hours} ساعة و "
        if minutes > 0:
            time_str += f"{minutes} دقيقة و "
        time_str += f"{seconds} ثانية"
        
        desc = profile_info.get("description", "لا توجد تفاصيل")
        verified_badge = "نعم (موثق)" if profile_info.get("verified") else "لا (غير موثق)"
        
        caption = (
            f"تم العثور على الحساب: @{username}\n"
            f"-----------------------------------\n"
            f"التفاصيل: {desc}\n"
            f"حالة التوثيق: {verified_badge}\n"
            f"مدة غياب الحساب / وقت الفحص: {time_str}"
        )
        
        with open(screenshot_path, "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption
            )
        return True
        
    except Exception:
        return False
await context.bot.send_message(chat_id=chat_id, text=f"⏳ الحساب @{username} غير موجود حالياً. بدأت مراقبته وسأخبرك فور ظهوره!")
    
    while True:
        await asyncio.sleep(120)
        found = await check_and_send(context, chat_id, username, start_time)
        if found:
            break

async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("الرجاء كتابة اليوزر بعد الأمر. مثال:\n/track elonmusk")
        return
    
    username = context.args[0].replace("@", "").strip()
    chat_id = update.effective_chat.id
    
    start_time = datetime.now()
    
    status_message = await update.message.reply_text(f"🔍 جاري فحص حساب @{username}...")
    
    success = await check_and_send(context, chat_id, username, start_time)
    
    if success:
        await status_message.delete()
    else:
        await status_message.delete()
        asyncio.create_task(background_monitor(context, chat_id, username, start_time))

def main():
    TOKEN = "8830810802:AAFbv4TqX-DJT6uidBwz9aM4aA2cucl_tOo"
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    
    print("البوت يعمل الآن بصور صافية وبدون أخطاء...")
    app.run_polling()

if__name__ == "__main__":
    main()
async def background_monitor(context: ContextTypes.DEFAULT_TYPE, chat_id: int, username: str, start_time: datetime):
