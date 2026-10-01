from datetime import datetime
import time
import telebot
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# التوكن الخاص بك الذي أرسلته
TOKEN = "8830810802:AAFbv4TqX-DJT6uidBwz9aM4aA2cucl_tOo"
bot = telebot.TeleBot(TOKEN)

# قاموس لحفظ الحسابات قيد المراقبة
tracked_accounts = {}


@bot.message_handler(commands=['start'])
def send_welcome(message):
  bot.reply_to(
      message,
      "أهلاً بك في بوت مراقبة انستغرام! 🚀\n"
      "استخدم الأمر هكذا لمراقبة أي حساب:\n"
      "`/track username`",
      parse_mode="Markdown",
  )


@bot.message_handler(commands=['track'])
def track_account(message):
  try:
    # استخراج اليوزر من رسالة المستخدم
    args = message.text.split()
    if len(args) < 2:
      bot.reply_to(
          message,
          "الرجاء كتابة اليوزر بعد الأمر بشكل صحيح.\nمثال: `/track instagram`",
          parse_mode="Markdown",
      )
      return

    username = args[1].replace("@", "").strip()
    tracked_accounts[username] = datetime.now()

    bot.reply_to(
        message,
        f"⏳ تم بدء مراقبة الحساب: @{username}\nسيتم فحص حالته وإعلامك فوراً عند رصد أي تغير!",
    )

    # بدء عملية الفحص والتقاط الصورة
    check_instagram_status(username, message.chat.id)

  except Exception as e:
    bot.reply_to(message, f"حدث خطأ: {e}")


def check_instagram_status(username, chat_id):
  start_time = tracked_accounts.get(username)
  url = f"https://www.instagram.com/{username}/"

  # إعداد متصفح وهمي خفي (Headless) للعمل في الخلفية
  options = Options()
  options.add_argument("--headless")
  options.add_argument("--disable-gpu")
  options.add_argument("--no-sandbox")
  options.add_argument(
      "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  )

  driver = webdriver.Chrome(options=options)

  try:
    driver.get(url)
    time.sleep(6)  # انتظار تحميل الصفحة بالكامل

    # التقاط صورة الشاشة وحفظها
    screenshot_path = f"{username}_screen.png"
    driver.save_screenshot(screenshot_path)

    # حساب المدة الزمنية المستغرقة منذ بدء المراقبة
    end_time = datetime.now()
    duration_seconds = int((end_time - start_time).total_seconds())

    # تحويل الثواني إلى صيغة (أيام، ساعات، دقائق)
    days = duration_seconds // 86400
    hours = (duration_seconds % 86400) // 3600
    minutes = (duration_seconds % 3600) // 60
    duration_str = f"{days} أيام و {hours} ساعات و {minutes} دقائق"

    # إرسال الصورة والنتيجة لتليجرام
    with open(screenshot_path, "rb") as photo:
      bot.send_photo(
          chat_id,
          photo,
          caption=(
              f"🎉 تنبيه بخصوص الحساب: @{username}\n\n"
              f"⏱️ المدة الزمنية المستغرقة: {duration_str}\n"
              "📸 تم التقاط صورة البروفايل بنجاح!"
          ),
          parse_mode="Markdown",
      )

  except Exception as e:
    print(f"خطأ أثناء فحص الحساب: {e}")
  finally:
    driver.quit()


# تشغيل البوت باستمرار
print("البوت يعمل الآن ومستعد لتلقي الأوامر...")
bot.infinity_polling()
