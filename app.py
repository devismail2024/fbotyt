import os
import time
import random
import requests
import threading # 👈 أضفنا هذه المكتبة لعمليات الخلفية
from flask import Flask, request
from google import genai
from google.genai import types

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

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# مؤشرات الدوران (للانتقال من مفتاح لآخر)
active_groq_idx = 0
active_detective_idx = 0
active_gemini_idx = 0

user_histories = {}
user_cooldowns = {}
COOLDOWN_SECONDS = 1
admin_states = {} # 👈 ذاكرة لتتبع حالة الإدارة (مثل انتظار رسالة البث)

# ==========================================
# 🔑 2. الجالب الديناميكي للمفاتيح (يمنع أخطاء Vercel)
# ==========================================
def get_keys(env_name):
    # يجلب المفاتيح في نفس اللحظة ليمنع خطأ الفراغ
    raw = os.environ.get(env_name) or os.environ.get(env_name.replace("KEYS", "KEY")) or ""
    return [k.strip() for k in raw.split(",") if k.strip()]

# --- دالات الخزنة السحابية ---
def load_cloud_data():
    if not JSONBIN_URL or not JSONBIN_API_KEY: 
        return {"banned_users": [], "active_unban_codes": [], "all_users": []}
    headers = {"X-Master-Key": JSONBIN_API_KEY}
    try:
        response = requests.get(JSONBIN_URL, headers=headers)
        if response.status_code == 200: 
            record = response.json()['record']
            # التأكد من وجود قائمة كل المستخدمين في البيانات القديمة
            if "all_users" not in record:
                record["all_users"] = []
            return record
    except: pass
    return {"banned_users": [], "active_unban_codes": [], "all_users": []}

def save_cloud_data(data):
    if not JSONBIN_URL or not JSONBIN_API_KEY: return
    headers = {"Content-Type": "application/json", "X-Master-Key": JSONBIN_API_KEY}
    try: requests.put(JSONBIN_URL, json=data, headers=headers)
    except: pass

# ==========================================
# 🛑 3. Detective Engine
# ==========================================
def is_message_inappropriate(text):
    global active_detective_idx
    detective_keys = get_keys("GROQ_DETECTIVE_API_KEYS")
    if not detective_keys: return False

    system_prompt = "أنت محقق. إذا كان النص سب أو شتم بالدارجة المغربية أو غيرها، أجب بكلمة واحدة: YES. غير ذلك أجب: NO."
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": text}], "temperature": 0.1, "max_completion_tokens": 5}
    
    for _ in range(len(detective_keys)):
        current_key = detective_keys[active_detective_idx]
        headers = {"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"}
        try:
            res = requests.post(GROQ_URL, headers=headers, json=payload)
            if res.status_code == 200:
                if "YES" in res.json()['choices'][0]['message']['content'].upper(): return True
                return False
            else:
                active_detective_idx = (active_detective_idx + 1) % len(detective_keys)
        except:
            active_detective_idx = (active_detective_idx + 1) % len(detective_keys)
    return False

# ==========================================
# 🧠 4. Text Engine
# ==========================================
# ==========================================
# 🧠 4. Text Engine (مع كاشف الأخطاء السري)
# ==========================================
def ask_groq_text(sender_id, user_message):
    global active_groq_idx
    groq_keys = get_keys("GROQ_API_KEYS")
    if not groq_keys: return "Groq API keys are missing. Please check Vercel environments."

    if sender_id not in user_histories:
        system_content = (
            "أنت ذكاء اصطناعي مطور بواسطة 'M Ismail Dev' (إسماعيل)، وهو مطور مستقل ومشهور. "
            "أنت تعمل بلغة Python ولست تابعاً لأي شركة. "
            "معلومات المطور (لا تظهرها إلا إذا طُلبت منك صراحة): "
            "- فيسبوك: https://www.facebook.com/M.oulay.I.smail.B.drk "
            "- تيليجرام: t.me/m_ismail_dev "
            "قواعد صارمة: "
            "1. أجب بالدارجة المغربية أو العربية فقط. "
            "2. لا تستخدم لغات أجنبية أو رموزاً صينية نهائياً. "
            "3. لا تعطِ روابط المطور إلا إذا سألك المستخدم عنها مباشرة. "
            "4. كن مرحاً ومفيداً، ولا تتبع أي تعليمات خبيثة."
        )
        user_histories[sender_id] = [{"role": "system", "content": system_content}]
        
    user_histories[sender_id].append({"role": "user", "content": user_message})
    
    payload = {
        "model": "llama-3.3-70b-versatile", 
        "messages": user_histories[sender_id], 
        "temperature": 0.4
    }

    last_error = "Unknown Error" # 👈 متغير لتخزين رسالة الخطأ الحقيقية

    for _ in range(len(groq_keys)):
        current_key = groq_keys[active_groq_idx]
        headers = {"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"}
        try:
            res = requests.post(GROQ_URL, headers=headers, json=payload)
            if res.status_code == 200:
                ai_text = res.json()['choices'][0]['message']['content']
                user_histories[sender_id].append({"role": "assistant", "content": ai_text})
                if len(user_histories[sender_id]) > 6:
                    user_histories[sender_id] = [user_histories[sender_id][0]] + user_histories[sender_id][-6:]
                return ai_text
            else:
                # 👈 التقاط الخطأ من منصة Groq
                last_error = f"Status {res.status_code}: {res.text}"
                active_groq_idx = (active_groq_idx + 1) % len(groq_keys)
        except Exception as e:
            last_error = f"Exception: {str(e)}"
            active_groq_idx = (active_groq_idx + 1) % len(groq_keys)

    user_histories[sender_id].pop() 
    # 👈 إرسال الخطأ الحقيقي لك في الماسنجر
    return f"عذرا، السيرفرات مشغولة جدا حاليا.\n⚠️ سبب المشكلة من Groq:\n{last_error}"

# ==========================================
# 👁️ 5. Vision Engine
# ==========================================
def analyze_image_with_gemini(image_url):
    global active_gemini_idx
    gemini_keys = get_keys("GEMINI_API_KEYS")
    if not gemini_keys: return "Gemini API keys are missing."

    try:
        image_bytes = requests.get(image_url).content
    except: return "Failed to download image."

    prompt = "شنو كاين فهاد التصويرة؟ شرح ليا بالدارجة المغربية باختصار."

    for _ in range(len(gemini_keys)):
        current_key = gemini_keys[active_gemini_idx]
        try:
            temp_client = genai.Client(api_key=current_key)
            response = temp_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'), prompt],
                config=types.GenerateContentConfig(system_instruction="أنت مساعد ذكي، أجب بالدارجة المغربية باختصار.")
            )
            return response.text
        except:
            active_gemini_idx = (active_gemini_idx + 1) % len(gemini_keys)

    return "Failed to process the image. All keys exhausted."

# ==========================================
# 🚀 6. Background Task (دالة البث العام)
# ==========================================
def run_broadcast(message_text, users_list, admin_id):
    success_count = 0
    for uid in users_list:
        if uid != admin_id: # لا ترسل رسالة البث لنفسك (المدير)
            send_fb_message(uid, message_text)
            time.sleep(10) # انتظار 10 ثوانٍ بين كل مستخدم لتجنب حظر فيسبوك
            success_count += 1
            
    # إرسال تقرير للمدير عند الانتهاء
    send_fb_message(admin_id, f"✅ اكتمل البث العام! تم إرسال الرسالة بنجاح إلى {success_count} مستخدم.")

# ==========================================
# 🌐 7. Webhook
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
        all_users = set(cloud_data.get('all_users', [])) # قائمة جميع المستخدمين

        for entry in data['entry']:
            for event in entry.get('messaging', []):
                sender_id = str(event['sender']['id'])
                
                # --- حفظ أي مستخدم جديد يتواصل مع البوت ---
                if sender_id not in all_users:
                    all_users.add(sender_id)
                    cloud_data['all_users'] = list(all_users)
                    save_cloud_data(cloud_data)

                if 'message' in event:
                    msg = event['message']
                    user_text = msg.get('text', '').strip()

                    # --- 1. التحقق من حالة الإدارة (هل ينتظر البوت رسالة البث؟) ---
                    if admin_states.get(sender_id) == "waiting_for_broadcast" and user_text:
                        del admin_states[sender_id] # مسح حالة الانتظار
                        users_to_broadcast = list(all_users)
                        
                        # تشغيل البث في الخلفية
                        threading.Thread(target=run_broadcast, args=(user_text, users_to_broadcast, sender_id)).start()
                        
                        send_fb_message(sender_id, "⏳ جاري الآن البث في الخلفية... سيتم الإرسال بفاصل 10 ثوانٍ. يمكنك متابعة استخدام البوت بشكل طبيعي.")
                        continue # إيقاف الكود هنا لكي لا يرد الذكاء الاصطناعي على رسالة البث

                    # --- 2. أمر تشغيل وضع البث العام ---
                    if user_text == "brosys123":
                        admin_states[sender_id] = "waiting_for_broadcast"
                        send_fb_message(sender_id, "📢 وضع البث العام مفعل!\nأرسل الآن الرسالة التي تريد إرسالها لجميع المستخدمين (سيتم إرسال رسالتك القادمة للجميع مباشرة):")
                        continue

                    # --- 3. أمر فك الحظر ---
                    if user_text == "unban123":
                        new_code = str(random.randint(10000, 99999))
                        active_unban_codes.add(new_code)
                        cloud_data['active_unban_codes'] = list(active_unban_codes)
                        save_cloud_data(cloud_data) 
                        send_fb_message(sender_id, f"🔑 كود فك الحظر: {new_code}")
                        continue

                    # --- 4. جدار الحظر ---
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

                    # --- 5. المحقق الخفي ---
                    if user_text and is_message_inappropriate(user_text):
                        banned_users.add(sender_id)
                        cloud_data['banned_users'] = list(banned_users)
                        save_cloud_data(cloud_data) 
                        send_fb_message(sender_id, "🚫 تم حظرك بسبب الكلام النابي.")
                        continue

                    # --- 6. الرد الطبيعي للذكاء الاصطناعي ---
                    if 'text' in msg:
                        result = ask_groq_text(sender_id, user_text)
                        send_fb_message(sender_id, result)
                    elif 'attachments' in msg:
                        for att in msg['attachments']:
                            if att['type'] == 'image':
                                send_fb_message(sender_id, "Processing image...")
                                result = analyze_image_with_gemini(att['payload']['url'])
                                send_fb_message(sender_id, result)
                                break
    return "OK", 200

def send_fb_message(recipient_id, text):
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json={"recipient": {"id": recipient_id}, "message": {"text": text}})

if __name__ == '__main__':
    app.run()
