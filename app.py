import os
import time
import random
import requests
import threading
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# ⚙️ 1. Configuration & Global States
# ==========================================
PAGE_ACCESS_TOKEN = "EAAg9vun0ll4BQ6kUjTMs3qKk2CmjsfbaW5CQd9GWtbxKHWQk8ZAU1j3jWNsR7DME9gNMpl773NffjPyvmCaVT3WCdhanc2qZBhyPdDKozHrGDrkxQJHNI4Wq8mV5i9Kc13ISBNHf4ZBdY071PnSpf2c4KHOJGUyx9RZCazZBsXDvewxrHb8dHA7wYA44s9fWZBltTtsAZDZD"
VERIFY_TOKEN = "ismail dev"
FB_API_URL = "https://graph.facebook.com/v19.0/me/messages"

JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY")
JSONBIN_BIN_ID = os.environ.get("JSONBIN_BIN_ID")
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}" if JSONBIN_BIN_ID else ""

TEXT_API = "https://obito-mr-apis-2.vercel.app/api/ai/copilot"
IMAGE_GEN_API = "https://obito-mr-apis.vercel.app/api/ai/deepImg"

# آلة الحالة (State Machine) لتتبع خطوات المستخدمين
user_states = {} # {sender_id: {"step": "...", "data": {...}}}
user_cooldowns = {}
COOLDOWN_SECONDS = 1

STYLES = {"1": "default", "2": "ghibli", "3": "cyberpunk", "4": "anime", "5": "portrait", "6": "chibi", "7": "pixel", "8": "oil", "9": "3d"}
SIZES = {"1": "1:1", "2": "3:2", "3": "2:3"}

# ==========================================
# ☁️ 2. Cloud Storage (With Migration Logic)
# ==========================================
def load_cloud_data():
    default_data = {"banned_users_dict": {}, "active_unban_codes": [], "all_users": []}
    if not JSONBIN_URL: return default_data
    try:
        res = requests.get(JSONBIN_URL, headers={"X-Master-Key": JSONBIN_API_KEY})
        if res.status_code == 200:
            data = res.json()['record']
            if "all_users" not in data: data["all_users"] = []
            if "banned_users_dict" not in data: data["banned_users_dict"] = {}
            
            # ترقية البيانات القديمة (Migration) من قائمة إلى قاموس
            if "banned_users" in data and isinstance(data["banned_users"], list):
                for u in data["banned_users"]:
                    data["banned_users_dict"][u] = "سبب غير معروف (حظر قديم)"
                del data["banned_users"]
            return data
    except: pass
    return default_data

def save_cloud_data(data):
    if not JSONBIN_URL: return
    requests.put(JSONBIN_URL, json=data, headers={"Content-Type": "application/json", "X-Master-Key": JSONBIN_API_KEY})

# ==========================================
# 🧠 3. AI Engines (With Global Error Catching)
# ==========================================
def is_message_inappropriate(text):
    prompt = f"أنت محقق. أجب بـ YES أو NO. هل هذا النص سب أو شتم؟ النص: '{text}'"
    try:
        res = requests.get(TEXT_API, params={"text": prompt}, timeout=15)
        if res.status_code == 200 and "YES" in res.json().get("answer", "").upper(): return True
    except: pass
    return False

def ask_copilot(user_message, image_url=None, web_search=False):
    system_prompt = "أنت ذكاء اصطناعي مطور بواسطة 'M Ismail Dev'. أجب بالدارجة أو العربية."
    if not web_search:
        system_prompt += " أجب من معلوماتك العامة ولا تبحث في الويب إلا للضرورة القصوى."
    system_prompt += f" طلب المستخدم: {user_message}"
    
    params = {"text": system_prompt}
    if image_url: params["imageUrl"] = image_url
        
    try:
        res = requests.get(TEXT_API, params=params, timeout=30)
        if res.status_code == 200: return res.json().get("answer", "فشل الذكاء في توليد الرد."), None
        return None, f"خطأ API: {res.status_code} - {res.text}"
    except Exception as e:
        return None, f"خطأ في الاتصال: {str(e)}"

def generate_image(prompt, style, size):
    params = {"txt": prompt, "style": style, "size": size}
    try:
        res = requests.get(IMAGE_GEN_API, params=params, timeout=60)
        if res.status_code == 200:
            return res.json().get("data", {}).get("image_url"), None
        return None, f"خطأ API: {res.status_code} - {res.text}"
    except Exception as e:
        return None, f"خطأ في الاتصال: {str(e)}"

def upload_to_catbox(image_url_fb):
    try:
        img_data = requests.get(image_url_fb).content
        files = {"fileToUpload": ("image.jpg", img_data, "image/jpeg")}
        res = requests.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload", "userhash": ""}, files=files)
        return res.text.strip() if res.status_code == 200 else None, f"Catbox Error: {res.status_code}"
    except Exception as e:
        return None, f"Catbox Network Error: {str(e)}"

# ==========================================
# 🌐 4. Main Webhook & State Machine
# ==========================================
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return request.args.get("hub.challenge", "Failed"), 200 if request.args.get("hub.verify_token") == VERIFY_TOKEN else 403

    data = request.get_json()
    if data.get('object') == 'page':
        cloud_data = load_cloud_data()
        all_users = set(cloud_data.get('all_users', []))
        banned_users = cloud_data.get('banned_users_dict', {})
        active_codes = set(cloud_data.get('active_unban_codes', []))

        for entry in data['entry']:
            for event in entry.get('messaging', []):
                sid = str(event['sender']['id'])
                msg = event.get('message', {})
                text = msg.get('text', '').strip()
                attachments = msg.get('attachments', [])

                # --- 1. الترحيب بالمستخدم الجديد ---
                if sid not in all_users:
                    all_users.add(sid); cloud_data['all_users'] = list(all_users); save_cloud_data(cloud_data)
                    welcome_msg = "👋 أهلاً بك! أنا ذكاء اصطناعي تم تطويري بفخر بواسطة المطور M Ismail Dev.\nتابع حسابي: https://www.facebook.com/M.oulay.I.smail.B.drk"
                    send_fb_message(sid, welcome_msg)
                    send_menu(sid)
                    continue

                if not text and not attachments: continue

                # --- 2. جدار الحظر و OTP ---
                if text == "unban123":
                    code = str(random.randint(10000, 99999))
                    active_codes.add(code); cloud_data['active_unban_codes'] = list(active_codes); save_cloud_data(cloud_data)
                    send_fb_message(sid, f"🔑 كود فك الحظر: {code}"); continue

                if sid in banned_users:
                    if text in active_codes:
                        active_codes.remove(text); del banned_users[sid]
                        cloud_data['active_unban_codes'] = list(active_codes); cloud_data['banned_users_dict'] = banned_users
                        save_cloud_data(cloud_data)
                        send_fb_message(sid, "✅ تم فك الحظر عنك بنجاح! يمكنك الآن استخدام البوت بحرية.")
                    continue # التوقف هنا للمحظورين

                # --- 3. المحقق التلقائي ---
                if text and is_message_inappropriate(text):
                    banned_users[sid] = f"تلفظ بكلمة نابية: {text[:50]}"
                    cloud_data['banned_users_dict'] = banned_users; save_cloud_data(cloud_data)
                    send_fb_message(sid, "🚫 تم حظرك بسبب الكلام النابي.")
                    continue

                # --- 4. آلة الحالة (State Machine) لمعالجة الخطوات ---
                state = user_states.get(sid, {})
                step = state.get("step")

                if step:
                    # --- خطوات إنشاء الصورة ---
                    if step == "gen_style":
                        if text in STYLES:
                            state["data"]["style"] = STYLES[text]
                            state["step"] = "gen_size"
                            user_states[sid] = state
                            send_fb_message(sid, "📐 أدخل رقم البعد الذي تريده:\n1- مربع (1:1)\n2- أفقي (3:2)\n3- عمودي (2:3)")
                        else: send_fb_message(sid, "❌ رقم غير صحيح. اختر من 1 إلى 9.")
                        continue

                    elif step == "gen_size":
                        if text in SIZES:
                            send_fb_message(sid, "🎨 جاري إنشاء الصورة... المرجو الانتظار.")
                            size = SIZES[text]
                            prompt = state["data"]["prompt"]
                            style = state["data"]["style"]
                            
                            img_url, err = generate_image(prompt, style, size)
                            if img_url: send_fb_image(sid, img_url)
                            else: send_fb_message(sid, f"❌ فشل إنشاء الصورة.\nالسبب: {err}")
                            del user_states[sid] # إنهاء الخطوات
                        else: send_fb_message(sid, "❌ رقم غير صحيح. اختر من 1 إلى 3.")
                        continue

                    # --- خطوات البحث ---
                    elif step == "web_query":
                        send_fb_message(sid, "🔍 جاري البحث في الويب...")
                        ans, err = ask_copilot(text, web_search=True)
                        if ans: send_fb_message(sid, ans)
                        else: send_fb_message(sid, f"❌ خطأ:\n{err}")
                        del user_states[sid]
                        continue

                    # --- خطوات تحليل الصورة ---
                    elif step == "image_upload":
                        if attachments and attachments[0]['type'] == 'image':
                            state["data"]["img_url"] = attachments[0]['payload']['url']
                            state["step"] = "image_prompt"
                            user_states[sid] = state
                            send_fb_message(sid, "✍️ أدخل طلبك للصورة (مثال: اشرح لي، حل المعادلة..) أو أدخل رقم 1 للتحليل العادي.")
                        else: send_fb_message(sid, "❌ المرجو إرسال صورة صالحة.")
                        continue

                    elif step == "image_prompt":
                        send_fb_message(sid, "👁️ جاري معالجة الصورة...")
                        prompt = "شنو كاين فهاد التصويرة؟" if text == "1" else text
                        img_fb_url = state["data"]["img_url"]
                        
                        catbox_url, upload_err = upload_to_catbox(img_fb_url)
                        if catbox_url:
                            ans, ai_err = ask_copilot(prompt, image_url=catbox_url)
                            if ans: send_fb_message(sid, ans)
                            else: send_fb_message(sid, f"❌ خطأ في التحليل:\n{ai_err}")
                        else: send_fb_message(sid, f"❌ فشل رفع الصورة.\nالسبب: {upload_err}")
                        del user_states[sid]
                        continue

                    # --- خطوات لوحة التحكم (Admin) ---
                    elif step == "admin_action":
                        if text in ["1", "2"]:
                            state["data"]["action"] = text
                            state["step"] = "admin_id"
                            user_states[sid] = state
                            send_fb_message(sid, "✍️ أدخل الـ ID الخاص بالمستخدم:")
                        else: send_fb_message(sid, "❌ اختر 1 أو 2 فقط.")
                        continue
                    
                    elif step == "admin_id":
                        target_id = text
                        if state["data"]["action"] == "1": # فك الحظر
                            if target_id in banned_users:
                                del banned_users[target_id]
                                cloud_data['banned_users_dict'] = banned_users; save_cloud_data(cloud_data)
                                send_fb_message(sid, f"✅ تم فك الحظر عن المستخدم: {target_id}")
                            else: send_fb_message(sid, "❌ المستخدم ليس محظوراً.")
                        elif state["data"]["action"] == "2": # حظر
                            banned_users[target_id] = "محظور يدوياً من طرف الإدارة"
                            cloud_data['banned_users_dict'] = banned_users; save_cloud_data(cloud_data)
                            send_fb_message(sid, f"🚫 تم حظر المستخدم: {target_id}")
                        del user_states[sid]
                        continue

                # --- 5. جهاز توجيه الأوامر (Command Router) ---
                if text == ".menu":
                    send_menu(sid); continue

                elif text.startswith(".web"):
                    query = text.replace(".web", "").strip()
                    if query:
                        send_fb_message(sid, "🔍 جاري البحث في الويب...")
                        ans, err = ask_copilot(query, web_search=True)
                        if ans: send_fb_message(sid, ans)
                        else: send_fb_message(sid, f"❌ خطأ:\n{err}")
                    else:
                        user_states[sid] = {"step": "web_query", "data": {}}
                        send_fb_message(sid, "ما الذي تريد البحث عنه في الويب؟ 🌐")
                    continue

                elif text.startswith(".gen"):
                    prompt = text.replace(".gen", "").strip()
                    if not prompt: prompt = "Random beautiful and creative scene"
                    user_states[sid] = {"step": "gen_style", "data": {"prompt": prompt}}
                    styles_msg = "🎨 أدخل رقم الستايل الذي تريده:\n1- الواقعية\n2- فن غيبلي\n3- سايبربانك\n4- أنمي\n5- بورتريه\n6- تشيبي\n7- فن البكسل\n8- الرسم الزيتي\n9- ثلاثي الأبعاد"
                    send_fb_message(sid, styles_msg)
                    continue

                elif text == ".image":
                    user_states[sid] = {"step": "image_upload", "data": {}}
                    send_fb_message(sid, "📸 أرسل الصورة التي تريد تحليلها:")
                    continue

                elif text == ".infos":
                    infos_msg = "📊 **قائمة المستخدمين المسجلين:**\n\n"
                    for uid in all_users:
                        status = "🚫 محظور" if uid in banned_users else "✅ نشط"
                        reason = f"\nالسبب: {banned_users[uid]}" if uid in banned_users else ""
                        infos_msg += f"- ID: {uid} | الحالة: {status}{reason}\n"
                    
                    # الفيس بوك يمنع الرسائل الطويلة جداً، لذلك سنقسمها إذا لزم الأمر مستقبلاً
                    send_fb_message(sid, infos_msg[:2000]) 
                    
                    user_states[sid] = {"step": "admin_action", "data": {}}
                    send_fb_message(sid, "⚙️ اختر الإجراء:\n1- رفع الحظر عن مستخدم معين\n2- حظر مستخدم معين")
                    continue

                # --- 6. الدردشة العادية (السؤال المباشر) ---
                if text and not attachments:
                    ans, err = ask_copilot(text, web_search=False)
                    if ans: send_fb_message(sid, ans)
                    else: send_fb_message(sid, f"❌ خطأ في السيرفر:\n{err}")
                elif attachments:
                    send_fb_message(sid, "يرجى استخدام أمر .image أولاً إذا كنت تريد تحليل صورة.")

    return "OK", 200

def send_menu(sid):
    menu = (
        "📜 **قائمة الأوامر المتاحة:**\n"
        "🔸 `.web [طلبك]` : للبحث في الويب عن معلومات دقيقة.\n"
        "🔸 `.gen [وصفك]` : لإنشاء صور احترافية.\n"
        "🔸 `.image` : لتحليل الصور وقراءتها.\n"
        "🔸 `.menu` : لإظهار هذه القائمة.\n\n"
        "🔹 **أي رسالة عادية:** سيتم الرد عليها كدردشة مباشرة وذكية دون أوامر."
    )
    send_fb_message(sid, menu)

def send_fb_message(rid, txt):
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json={"recipient": {"id": rid}, "message": {"text": txt}})

def send_fb_image(rid, url):
    payload = {"recipient": {"id": rid}, "message": {"attachment": {"type": "image", "payload": {"url": url, "is_lazy_load": True}}}}
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json=payload)

if __name__ == '__main__':
    app.run()
