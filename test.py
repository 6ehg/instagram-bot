async def check_account_status(username):
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, 
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
            )
            
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0"
            ]
            
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=random.choice(user_agents),
                color_scheme="light"
            )
            
            page = await context.new_page()
            url = f"https://www.instagram.com/{username}/"
            response = await page.goto(url, timeout=60000)
            
            if response and response.status >= 400:
                await browser.close()
                return False, None, None

            await page.wait_for_timeout(3000)
            
            # --- إزالة الوضع المظلم القسري وإخفاء النوافذ المنبثقة ---
            try:
                await page.evaluate("""() => {
                    // 1. إزالة كلاسات Dark Mode من HTML و BODY
                    document.documentElement.classList.remove('dark', '_aa4d', 'style-dark');
                    document.body.classList.remove('dark', '_aa4d', 'style-dark');
                    
                    // 2. إجبار ألوان الأنماط على الوضع الفاتح الناصع
                    document.documentElement.style.setProperty('background-color', '#ffffff', 'important');
                    document.documentElement.style.setProperty('color', '#000000', 'important');
                    document.body.style.setProperty('background-color', '#ffffff', 'important');
                    document.body.style.setProperty('color', '#000000', 'important');
                    
                    // 3. تعديل كروت الميديا والحاويات لتصبح بيضاء
                    const allElements = document.querySelectorAll('*');
                    allElements.forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (style.backgroundColor === 'rgb(0, 0, 0)' || style.backgroundColor === 'rgb(18, 18, 18)') {
                            el.style.setProperty('background-color', '#ffffff', 'important');
                        }
                    });

                    // 4. إخفاء كافة النوافذ المنبثقة والإعلانات
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
            await page.wait_for_timeout(1000)
            # ---------------------------------------------------
            
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
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        return False, None, None
