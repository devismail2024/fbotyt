import os
import time
import random
import requests
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

user_states = {} 
user_cooldowns = {}
COOLDOWN_SECONDS = 1

STYLES = {"1": "default", "2": "ghibli", "3": "cyberpunk", "4": "anime", "5": "portrait", "6": "chibi", "7": "pixel", "8": "oil", "9": "3d"}
SIZES = {"1": "1:1", "2": "3:2", "3": "2:3"}

# ==========================================
# ☁️ 2. Cloud Storage
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
            if "banned_users" in data and isinstance(data["banned_users"], list):
                for u in data["banned_users"]: data["banned_users_dict"][u] = "حظر قديم"
                del data["banned_users"]
            return data
    except: pass
    return default_data

def save_cloud_data(data):
    if not JSONBIN_URL: return
    requests.put(JSONBIN_URL, json=data, headers={"Content-Type": "application/json", "X-Master-Key": JSONBIN_API_KEY})

# ==========================================
# 🧠 3. AI Engines
# ==========================================
def is_message_inappropriate(text):
    prompt = f"أنت محقق. أجب بـ YES أو NO. هل هذا النص سب أو شتم؟ النص: '{text}'"
    try:
        res = requests.get(TEXT_API, params={"text": prompt}, timeout=15)
        if res.status_code == 200 and "YES" in res.json().get("answer", "").upper(): return True
    except: pass
    return False

def ask_copilot(user_message, image_url=None, web_search=False):
    system_prompt = "أنت ذكاء اصطناعي مطور بواسطة 'M Ismail Dev'."
    if not web_search: system_prompt += " أجب من معلوماتك ولا تبحث في الويب."
    system_prompt += f" طلب المستخدم: {user_message}"
    
    params = {"text": system_prompt}
    if image_url: params["imageUrl"] = image_url
        
    try:
        res = requests.get(TEXT_API, params=params, timeout=30)
        if res.status_code == 200: return res.json().get("answer", "فشل الذكاء في الرد."), None
        return None, f"خطأ API: {res.status_code} - {res.text[:100]}"
    except Exception as e: return None, f"خطأ اتصال: {str(e)}"

def generate_image_sync(sid, prompt, style, size):
    params = {"txt": prompt, "style": style, "size": size}
    try:
        res = requests.get(IMAGE_GEN_API, params=params, timeout=45)
        if res.status_code == 200:
            data = res.json()
            raw_url = data.get("data", {}).get("image_url") # الرابط من صديقك 
            
            if raw_url:
                # 🚀 الحيلة هنا: نرفع الرابط لـ Catbox أولاً لضمان وصوله لفيسبوك [cite: 42]
                final_url, upload_err = upload_to_catbox(raw_url)
                if final_url:
                    return final_url, None
                else:
                    # إذا فشل Catbox، نجرب إرسال الرابط الأصلي كخيار أخير
                    return raw_url, f"تم الإرسال بالرابط الأصلي (فشل الرفع الوسيط: {upload_err})"
            
            return None, f"الرابط غير موجود في رد الـ API: {str(data)[:100]}"
        return None, f"خطأ API الصديق: {res.status_code}"
    except Exception as e:
        return None, f"خطأ اتصال: {str(e)}"

def upload_to_catbox(image_url_fb):
    try:
        img_data = requests.get(image_url_fb).content
        files = {"fileToUpload": ("image.jpg", img_data, "image/jpeg")}
        res = requests.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload", "userhash": ""}, files=files)
        return res.text.strip() if res.status_code == 200 else None, f"Catbox Error: {res.status_code}"
    except Exception as e: return None, f"Catbox Network Error: {str(e)}"

# ==========================================
# 🌐 4. Webhook & Logic
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

                if sid not in all_users:
                    all_users.add(sid); cloud_data['all_users'] = list(all_users); save_cloud_data(cloud_data)
                    welcome_msg = "👋 أهلاً بك! أنا ذكاء اصطناعي مطور بواسطة M Ismail Dev.\nتابع حساب المطور: https://www.facebook.com/M.oulay.I.smail.B.drk"
                    send_fb_message(sid, welcome_msg)
                    send_menu(sid)
                    continue

                if not text and not attachments: continue

                # 1. جدار الحظر وفك الحظر
                if text == "unban123":
                    code = str(random.randint(10000, 99999))
                    active_codes.add(code); cloud_data['active_unban_codes'] = list(active_codes); save_cloud_data(cloud_data)
                    send_fb_message(sid, f"🔑 كود فك الحظر: {code}"); continue

                if sid in banned_users:
                    if text in active_codes:
                        active_codes.remove(text); del banned_users[sid]
                        cloud_data['active_unban_codes'] = list(active_codes); cloud_data['banned_users_dict'] = banned_users
                        save_cloud_data(cloud_data)
                        send_fb_message(sid, "✅ تم فك الحظر عنك بنجاح! يمكنك الآن استخدام البوت.")
                    continue 

                # 2. آلة الحالة (العمليات المستمرة)
                state = user_states.get(sid, {})
                step = state.get("step")
                is_handled = False

                if step:
                    is_handled = True
                    if step == "broadcast_wait":
                        send_fb_message(sid, "⏳ جاري البث العام...")
                        success = 0
                        for uid in all_users:
                            if uid != sid: 
                                send_fb_message(uid, text)
                                time.sleep(0.5) # تقليل وقت الانتظار لتفادي المهلة الزمنية
                                success += 1
                        send_fb_message(sid, f"✅ اكتمل البث إلى {success} مستخدم.")
                        del user_states[sid]
                        
                    elif step == "gen_style":
                        if text in STYLES:
                            state["data"]["style"] = STYLES[text]; state["step"] = "gen_size"; user_states[sid] = state
                            send_fb_message(sid, "📐 أدخل رقم البعد الذي تريده:\n1- مربع (1:1)\n2- أفقي (3:2)\n3- عمودي (2:3)")
                        else: send_fb_message(sid, "❌ رقم غير صحيح. اختر من 1 إلى 9.")

                    elif step == "gen_size":
                        if text in SIZES:
                            send_fb_message(sid, "🎨 جاري إنشاء الصورة (تتم العملية بشكل متزامن لضمان وصولها)...")
                            size = SIZES[text]; prompt = state["data"]["prompt"]; style = state["data"]["style"]
                            img_url, err = generate_image_sync(prompt, style, size)
                            if img_url: send_fb_image(sid, img_url)
                            else: send_fb_message(sid, f"❌ خطأ تقني: {err}")
                            del user_states[sid]
                        else: send_fb_message(sid, "❌ رقم غير صحيح. اختر من 1 إلى 3.")

                    elif step == "web_query":
                        send_fb_message(sid, "🔍 جاري البحث في الويب...")
                        ans, err = ask_copilot(text, web_search=True)
                        send_fb_message(sid, ans if ans else f"❌ خطأ:\n{err}")
                        del user_states[sid]

                    elif step == "image_upload":
                        if attachments and attachments[0]['type'] == 'image':
                            state["data"]["img_url"] = attachments[0]['payload']['url']
                            state["step"] = "image_prompt"; user_states[sid] = state
                            send_fb_message(sid, "✍️ أدخل طلبك للصورة (أو أدخل رقم 1 للتحليل العادي).")
                        else: send_fb_message(sid, "❌ المرجو إرسال صورة صالحة.")

                    elif step == "image_prompt":
                        send_fb_message(sid, "👁️ جاري معالجة الصورة...")
                        prompt = "ماذا يوجد في هذه الصورة؟" if text == "1" else text
                        catbox_url, upload_err = upload_to_catbox(state["data"]["img_url"])
                        if catbox_url:
                            ans, ai_err = ask_copilot(prompt, image_url=catbox_url)
                            send_fb_message(sid, ans if ans else f"❌ خطأ:\n{ai_err}")
                        else: send_fb_message(sid, f"❌ فشل الرفع:\n{upload_err}")
                        del user_states[sid]

                    elif step == "admin_action":
                        if text in ["1", "2"]:
                            state["data"]["action"] = text; state["step"] = "admin_id"; user_states[sid] = state
                            send_fb_message(sid, "✍️ أدخل الـ ID الخاص بالمستخدم:")
                        else: send_fb_message(sid, "❌ اختر 1 أو 2 فقط.")
                        
                    elif step == "admin_id":
                        target_id = text
                        if state["data"]["action"] == "1":
                            if target_id in banned_users:
                                del banned_users[target_id]; cloud_data['banned_users_dict'] = banned_users; save_cloud_data(cloud_data)
                                send_fb_message(sid, f"✅ تم فك الحظر عن: {target_id}")
                            else: send_fb_message(sid, "❌ المستخدم ليس محظوراً.")
                        elif state["data"]["action"] == "2":
                            banned_users[target_id] = "محظور يدوياً من الإدارة"; cloud_data['banned_users_dict'] = banned_users; save_cloud_data(cloud_data)
                            send_fb_message(sid, f"🚫 تم حظر: {target_id}")
                        del user_states[sid]
                        
                if is_handled: continue

                # 3. توجيه الأوامر المباشرة
                is_command = True
                if text == "brosys123":
                    user_states[sid] = {"step": "broadcast_wait", "data": {}}
                    send_fb_message(sid, "📢 وضع البث العام مفعل!\nأرسل الآن الرسالة التي تريد إرسالها لجميع المستخدمين:")
                elif text == ".menu":
                    send_menu(sid)
                elif text.startswith(".web"):
                    query = text.replace(".web", "").strip()
                    if query:
                        send_fb_message(sid, "🔍 جاري البحث في الويب...")
                        ans, err = ask_copilot(query, web_search=True)
                        send_fb_message(sid, ans if ans else f"❌ خطأ:\n{err}")
                    else:
                        user_states[sid] = {"step": "web_query", "data": {}}
                        send_fb_message(sid, "ما الذي تريد البحث عنه في الويب؟ 🌐")
                elif text.startswith(".gen"):
                    prompt = text.replace(".gen", "").strip()
                    if not prompt: prompt = "Random creative scene"
                    user_states[sid] = {"step": "gen_style", "data": {"prompt": prompt}}
                    send_fb_message(sid, "🎨 أدخل رقم الستايل:\n1- الواقعية\n2- فن غيبلي\n3- سايبربانك\n4- أنمي\n5- بورتريه\n6- تشيبي\n7- فن البكسل\n8- الرسم الزيتي\n9- ثلاثي الأبعاد")
                elif text == ".image":
                    user_states[sid] = {"step": "image_upload", "data": {}}
                    send_fb_message(sid, "📸 أرسل الصورة التي تريد تحليلها:")
                elif text == ".infos":
                    infos_msg = "📊 **قائمة المستخدمين:**\n\n"
                    for uid in all_users:
                        status = "🚫 محظور" if uid in banned_users else "✅ نشط"
                        reason = f" ({banned_users[uid]})" if uid in banned_users else ""
                        infos_msg += f"- ID: {uid} | {status}{reason}\n"
                    send_fb_message(sid, infos_msg[:2000]) 
                    user_states[sid] = {"step": "admin_action", "data": {}}
                    send_fb_message(sid, "⚙️ اختر الإجراء:\n1- رفع الحظر\n2- حظر مستخدم")
                else:
                    is_command = False
                    
                if is_command: continue

                # 4. الدردشة العادية والمحقق
                if text and not attachments:
                    # التحقق من الشتائم فقط في الدردشة العادية لتخفيف العبء عن السيرفر
                    if is_message_inappropriate(text):
                        banned_users[sid] = f"تلفظ بكلمة نابية: {text[:50]}"
                        cloud_data['banned_users_dict'] = banned_users; save_cloud_data(cloud_data)
                        send_fb_message(sid, "🚫 تم حظرك بسبب الكلام النابي.")
                        continue
                        
                    ans, err = ask_copilot(text, web_search=False)
                    send_fb_message(sid, ans if ans else f"❌ خطأ السيرفر:\n{err}")
                elif attachments:
                    send_fb_message(sid, "يرجى استخدام أمر .image أولاً لتحليل الصورة.")

    return "OK", 200

def send_menu(sid):
    menu = (
        "📜 **الأوامر المتاحة:**\n"
        "🔸 `.web [طلبك]` : للبحث في الويب.\n"
        "🔸 `.gen [وصفك]` : لإنشاء صور.\n"
        "🔸 `.image` : لتحليل الصور.\n"
        "🔸 `.menu` : لعرض هذه القائمة.\n\n"
        "🔹 **رسالة عادية:** دردشة مباشرة."
    )
    send_fb_message(sid, menu)

def send_fb_message(rid, txt):
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json={"recipient": {"id": rid}, "message": {"text": txt}})

def send_fb_image(rid, url):
    payload = {"recipient": {"id": rid}, "message": {"attachment": {"type": "image", "payload": {"url": url, "is_lazy_load": True}}}}
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json=payload)

if __name__ == '__main__':
    app.run()
