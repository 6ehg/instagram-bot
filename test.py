minutes, seconds = divmod(remainder, 60)
            
            time_str = f"{hours} ساعة و {minutes} دقيقة و {seconds} ثانية" if hours > 0 else f"{minutes} دقيقة و {seconds} ثانية" if minutes > 0 else f"{seconds} ثانية"
            
            desc = profile_info.get("description", "لا توجد تفاصيل")
            verified_badge = "نعم (موثق)" if profile_info.get("verified") else "لا (غير موثق)"
            
            caption = (
                f"🚨 **تم رصد ظهور الحساب بنجاح!**\n"
                f"👤 اليوزر: @{username}\n"
                f"⏱️ المدة حتى ظهر: {time_str}\n"
                f"🔄 عدد المحاولات: {attempt}\n"
                f"-----------------------------------\n"
                f"التفاصيل: {desc}\n"
                f"حالة التوثيق: {verified_badge}"
            )
            
            with open(screenshot_path, "rb") as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
            break # إيقاف حلقة المراقبة بعد أن تم العثور عليه بنجاح
            
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
    
    await update.message.reply_text(f"👀 جاري بدء المراقبة المستمرة للحساب @{units_fix if 'units_fix' in locals() else username}...\nسأقوم بتنبيهك فور ظهوره وإرسال المدة الساطعة بدقة!")
    
    # تشغيل عملية المراقبة في الخلفية بدون تجميد البوت
    context.application.create_task(monitor_account(context, chat_id, username, start_time))

def main():
    TOKEN = "8830810802:AAFbv4TqX-DJT6uidBwz9aM4aA2cucl_tOo"
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track_user))
    print("بوت المراقبة المستمرة يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
