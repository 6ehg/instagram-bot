import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from playwright.async_api import async_playwright

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك يا فنان! بوت مراقبة الحسابات جاهز 🚀\n"
        "أمر المراقبة المستمرة:\n/track username"
    )

async def monitor_account(context: ContextTypes.DEFAULT_TYPE, chat_id: int, username: str, start_time: datetime):
    screenshot_path = f"{username}_{chat_id}.png"
    attempt = 1
    
    while True:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=["--disable-gpu"])
                page = await browser.new_page(viewport={"width": 1280, "height": 800})
                
                url = f"https://www.instagram.com/{username}/"
                response = await page.goto(url, timeout=60000)
                
                if response and response.status == 404:
                    await browser.close()
                    await asyncio.sleep(30)
                    attempt += 1
                    continue
                
                await page.wait_for_timeout(2000)
                
                try:
                    await page.evaluate("""() => {
                        const overlays = document.querySelectorAll("div[role='dialog'], div._a23z, div._aacl, div._a8k_, div[class*='x1n2onr6']");
                        overlays.forEach(el => el.remove());
                        
                        const semiTrans = document.querySelectorAll("div[style*='background-color']");
                        semiTrans.forEach(el => {
                            const bg = window.getComputedStyle(el).backgroundColor;
                            if (bg.includes('rgba') || bg.includes('rgb')) {
                                el.style.display = 'none';
                            }
                        });
                        
                        document.body.style.overflow = 'auto';
                        document.documentElement.style.overflow = 'auto';
                    }""")
                except Exception:
                    pass
                
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500) # انتظار أقل من ثانية لضمان صفاء الصورة ووضوحها
                
                is_not_found = await page.evaluate("""() => {
                    const bodyText = document.body.innerText;
                    return bodyText.includes("Sorry, this page isn't available.") || bodyText.includes("عذراً، هذه الصفحة غير متوفرة.");
                }""")
                
                if is_not_found:
                    await browser.close()
                    await asyncio.sleep(30)
                    attempt += 1
                    continue
                
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
            
            if hours > 0:
                time_str = f"{hours} ساعة و {minutes} دقيقة و {seconds} ثانية"elif minutes > 0:
                time_str = f"{minutes} دقيقة و {seconds} ثانية"
            else:
                time_str = f"{seconds} ثانية"
            
            desc = profile_info.get("description", "لا توجد تفاصيل")
            
            if profile_info.get("verified"):
                verified_badge = "نعم (موثق)"
            else:
                verified_badge = "لا (غير موثق)"
            
            caption = (
                f"🚨 **تم رصد ظهور الحساب بنجاح!**\n"
                f"👤 اليوزر: @{username}\n"
                f"⏱ المدة حتى ظهر: {time_str}\n"
                f"🔄 عدد المحاولات: {attempt}\n"
                f"-----------------------------------\n"
                f"التفاصيل: {desc}\n"
                f"حالة التوثيق: {verified_badge}"
            )
            
            with open(screenshot_path, "rb") as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
            break
            
        except Exception:
            await asyncio.sleep(30)
            attempt += 1
            continue

async def track_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("أكتب اليوزر بعد الأمر للمراقبة المستمرة، مثل:\n/track username")
        return
    username = context.args[0].replace("@", "").strip()
    chat_id = update.effective_chat.id
    start_time = datetime.now()
    
    await update.message.reply_text(f"👀 جاري بدء المراقبة المستمرة للحساب @{username}...\nسأقوم بتنبيهك فور ظهوره وإرسال المدة بدقة!")
    
    context.application.create_task(monitor_account(context, chat_id, username, start_time))

async def run_bot(token):
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    print(f"تم تشغيل البوت بنجاح برمز التوكن: {token[:10]}...")

async def main():
    tokens = [
        "8875867251:AAHEH5njF9zHBk_slXVo54ngOxg4dBoqY8U"
    ]
    
    await asyncio.gather(*(run_bot(token) for token in tokens))
    
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
