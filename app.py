import os
import time
import random
import requests
import threading
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# ⚙️ 1. Configuration & Cloud Storage
# ==========================================
PAGE_ACCESS_TOKEN = "EAAg9vun0ll4BQ6kUjTMs3qKk2CmjsfbaW5CQd9GWtbxKHWQk8ZAU1j3jWNsR7DME9gNMpl773NffjPyvmCaVT3WCdhanc2qZBhyPdDKozHrGDrkxQJHNI4Wq8mV5i9Kc13ISBNHf4ZBdY071PnSpf2c4KHOJGUyx9RZCazZBsXDvewxrHb8dHA7wYA44s9fWZBltTtsAZDZD"
VERIFY_TOKEN = "ismail dev"
FB_API_URL = "https://graph.facebook.com/v19.0/me/messages"

# JSONBin Config
JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY")
JSONBIN_BIN_ID = os.environ.get("JSONBIN_BIN_ID")
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}" if JSONBIN_BIN_ID else ""

# Obito APIs
TEXT_API = "https://obito-mr-apis-2.vercel.app/api/ai/copilot"
IMAGE_GEN_API = "https://obito-mr-apis.vercel.app/api/ai/deepImg"

user_cooldowns = {}
COOLDOWN_SECONDS = 1
admin_states = {}

# --- دالات الخزنة السحابية ---
def load_cloud_data():
    if not JSONBIN_URL or not JSONBIN_API_KEY: 
        return {"banned_users": [], "active_unban_codes": [], "all_users": []}
    headers = {"X-Master-Key": JSONBIN_API_KEY}
    try:
        response = requests.get(JSONBIN_URL, headers=headers)
        if response.status_code == 200: 
            record = response.json()['record']
            if "all_users" not in record: record["all_users"] = []
            return record
    except: pass
    return {"banned_users": [], "active_unban_codes": [], "all_users": []}

def save_cloud_data(data):
    if not JSONBIN_URL or not JSONBIN_API_KEY: return
    headers = {"Content-Type": "application/json", "X-Master-Key": JSONBIN_API_KEY}
    try: requests.put(JSONBIN_URL, json=data, headers=headers)
    except: pass

# ==========================================
# 🛑 2. Detective Engine (Copilot API)
# ==========================================
def is_message_inappropriate(text):
    """محقق الأخلاق باستخدام Copilot"""
    prompt = f"أنت محقق خبير. أجب بكلمة واحدة فقط: YES أو NO. هل يحتوي هذا النص على سب أو شتم بأي لغة (خصوصا الدارجة المغربية)؟ النص هو: '{text}'"
    try:
        res = requests.get(TEXT_API, params={"text": prompt}, timeout=15)
        if res.status_code == 200:
            answer = res.json().get("answer", "").upper()
            if "YES" in answer:
                return True
    except Exception as e:
        print(f"Detective Error: {e}")
    return False

# ==========================================
# 🧠 3. AI Engines (Text, Vision, Image Gen)
# ==========================================
def ask_copilot(user_message, image_url=None):
    """المحرك الذكي للنصوص وتحليل الصور"""
    # دمج الشخصية في السؤال مباشرة
    system_prompt = (
        "أنت ذكاء اصطناعي مطور بواسطة 'M Ismail Dev' (إسماعيل). "
        "فيسبوك: https://www.facebook.com/M.oulay.I.smail.B.drk . "
        "تيليجرام: t.me/m_ismail_dev . "
        "أجب بالدارجة المغربية أو العربية فقط. لا تستخدم لغات أجنبية. "
        f"طلب المستخدم: {user_message}"
    )
    
    params = {"text": system_prompt}
    if image_url:
        params["imageUrl"] = image_url
        
    try:
        res = requests.get(TEXT_API, params=params, timeout=30)
        if res.status_code == 200:
            return res.json().get("answer", "عذرا، ماقدرتش نجاوب دابا.")
    except:
        return "السيرفر تقيل شوية، عاود جرب."
    return "حدث خطأ في الاتصال بالذكاء الاصطناعي."

def generate_image(prompt, style="default"):
    """محرك رسم الصور"""
    params = {"txt": prompt, "style": style, "size": "1:1"}
    try:
        res = requests.get(IMAGE_GEN_API, params=params, timeout=60)
        if res.status_code == 200:
            return res.json().get("data", {}).get("image_url")
    except: return None
    return None

def upload_to_catbox(image_url_fb):
    """وسيط رفع الصور لـ Catbox"""
    try:
        img_data = requests.get(image_url_fb).content
        files = {"fileToUpload": ("image.jpg", img_data, "image/jpeg")}
        data = {"reqtype": "fileupload", "userhash": ""}
        res = requests.post("https://catbox.moe/user/api.php", data=data, files=files)
        return res.text.strip() if res.status_code == 200 else None
    except: return None

# ==========================================
# 📢 4. Background Task (البث العام)
# ==========================================
def run_broadcast(message_text, users_list, admin_id):
    success_count = 0
    for uid in users_list:
        if uid != admin_id: 
            send_fb_message(uid, message_text)
            time.sleep(10) 
            success_count += 1
    send_fb_message(admin_id, f"✅ اكتمل البث العام! تم إرسال الرسالة بنجاح إلى {success_count} مستخدم.")

# ==========================================
# 🌐 5. Webhook Logic
# ==========================================
@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Failed", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data.get('object') == 'page':
        cloud_data = load_cloud_data()
        banned_users = set(cloud_data.get('banned_users', []))
        active_unban_codes = set(cloud_data.get('active_unban_codes', []))
        all_users = set(cloud_data.get('all_users', []))

        for entry in data['entry']:
            for event in entry.get('messaging', []):
                sender_id = str(event['sender']['id'])
                
                if sender_id not in all_users:
                    all_users.add(sender_id)
                    cloud_data['all_users'] = list(all_users)
                    save_cloud_data(cloud_data)

                if 'message' in event:
                    msg = event['message']
                    user_text = msg.get('text', '').strip()

                    # --- 1. التحقق من حالة البث ---
                    if admin_states.get(sender_id) == "waiting_for_broadcast" and user_text:
                        del admin_states[sender_id]
                        users_to_broadcast = list(all_users)
                        threading.Thread(target=run_broadcast, args=(user_text, users_to_broadcast, sender_id)).start()
                        send_fb_message(sender_id, "⏳ جاري الآن البث في الخلفية... سيتم الإرسال بفاصل 10 ثوانٍ.")
                        continue

                    # --- 2. أوامر الإدارة ---
                    if user_text == "brosys123":
                        admin_states[sender_id] = "waiting_for_broadcast"
                        send_fb_message(sender_id, "📢 وضع البث العام مفعل!\nأرسل الآن الرسالة:")
                        continue

                    if user_text == "unban123":
                        new_code = str(random.randint(10000, 99999))
                        active_unban_codes.add(new_code)
                        cloud_data['active_unban_codes'] = list(active_unban_codes)
                        save_cloud_data(cloud_data) 
                        send_fb_message(sender_id, f"🔑 كود فك الحظر: {new_code}")
                        continue

                    # --- 3. جدار الحظر ---
                    if sender_id in banned_users:
                        if user_text in active_unban_codes:
                            active_unban_codes.remove(user_text)
                            banned_users.remove(sender_id)
                            cloud_data['active_unban_codes'] = list(active_unban_codes)
                            cloud_data['banned_users'] = list(banned_users)
                            save_cloud_data(cloud_data) 
                            send_fb_message(sender_id, "✅ تم فك الحظر عنك بنجاح!")
                            continue
                        continue 

                    now = time.time()
                    if now - user_cooldowns.get(sender_id, 0) < COOLDOWN_SECONDS:
                        send_fb_message(sender_id, "Please wait...")
                        continue
                    user_cooldowns[sender_id] = now

                    # --- 4. المحقق الخفي ---
                    if user_text and is_message_inappropriate(user_text):
                        banned_users.add(sender_id)
                        cloud_data['banned_users'] = list(banned_users)
                        save_cloud_data(cloud_data) 
                        send_fb_message(sender_id, "🚫 تم حظرك بسبب الكلام النابي.")
                        continue

                    # --- 5. أوامر رسم الصور ---
                    if user_text.lower().startswith("ارسم لي ") or user_text.lower().startswith("draw "):
                        prompt = user_text.split(" ", 2)[-1]
                        send_fb_message(sender_id, "🎨 جاري الرسم... استنى شوية.")
                        img_url = generate_image(prompt)
                        if img_url:
                            send_fb_image(sender_id, img_url)
                        else:
                            send_fb_message(sender_id, "❌ فشل الرسم. جرب مرة أخرى.")
                        continue

                    # --- 6. الرد الذكي للذكاء الاصطناعي (نص أو تحليل صورة) ---
                    if 'text' in msg:
                        result = ask_copilot(user_text)
                        send_fb_message(sender_id, result)
                    elif 'attachments' in msg:
                        for att in msg['attachments']:
                            if att['type'] == 'image':
                                send_fb_message(sender_id, "👁️ جاري تحليل الصورة...")
                                catbox_url = upload_to_catbox(att['payload']['url'])
                                if catbox_url:
                                    result = ask_copilot("شنو كاين فهاد التصويرة؟", image_url=catbox_url)
                                    send_fb_message(sender_id, result)
                                else:
                                    send_fb_message(sender_id, "❌ فشل رفع الصورة لتحليلها.")
                                break
    return "OK", 200

def send_fb_message(recipient_id, text):
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json={"recipient": {"id": recipient_id}, "message": {"text": text}})

def send_fb_image(recipient_id, image_url):
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {"url": image_url, "is_lazy_load": True}
            }
        }
    }
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json=payload)

if __name__ == '__main__':
    app.run()
