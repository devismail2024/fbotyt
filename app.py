import os
import time
import random
import requests
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

# JSONBin Config (للحفظ الدائم)
JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY")
JSONBIN_BIN_ID = os.environ.get("JSONBIN_BIN_ID")
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

# مفاتيح AI
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_DETECTIVE_API_KEY = os.environ.get("GROQ_DETECTIVE_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

user_histories = {}
user_cooldowns = {}
COOLDOWN_SECONDS = 1

# --- دالات التعامل مع الخزنة السحابية ---
def load_cloud_data():
    headers = {"X-Master-Key": JSONBIN_API_KEY}
    try:
        response = requests.get(JSONBIN_URL, headers=headers)
        if response.status_code == 200:
            return response.json()['record']
    except: pass
    return {"banned_users": [], "active_unban_codes": []}

def save_cloud_data(data):
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": JSONBIN_API_KEY
    }
    try:
        requests.put(JSONBIN_URL, json=data, headers=headers)
    except: pass

# ==========================================
# 🛑 2. Detective & AI Engines
# ==========================================
def is_message_inappropriate(text):
    if not GROQ_DETECTIVE_API_KEY: return False
    headers = {"Authorization": f"Bearer {GROQ_DETECTIVE_API_KEY}", "Content-Type": "application/json"}
    system_prompt = "أنت محقق. إذا كان النص سب أو شتم بالدارجة المغربية أو غيرها، أجب بكلمة واحدة: YES. غير ذلك أجب: NO."
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": text}], "temperature": 0.1, "max_completion_tokens": 5}
    try:
        res = requests.post(GROQ_URL, headers=headers, json=payload)
        if "YES" in res.json()['choices'][0]['message']['content'].upper(): return True
    except: pass
    return False

def ask_groq_text(sender_id, user_message):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    if sender_id not in user_histories:
        user_histories[sender_id] = [{"role": "system", "content": "أنت ذكاء اصطناعي طورك M Ismail Dev. أجب بالدارجة المغربية."}]
    user_histories[sender_id].append({"role": "user", "content": user_message})
    payload = {"model": "llama-3.3-70b-versatile", "messages": user_histories[sender_id]}
    try:
        res = requests.post(GROQ_URL, headers=headers, json=payload)
        ai_text = res.json()['choices'][0]['message']['content']
        user_histories[sender_id].append({"role": "assistant", "content": ai_text})
        return ai_text
    except: return "An error occurred."

# ==========================================
# 🌐 3. Webhook & Logic
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
        # تحميل البيانات من السحاب في كل طلب لضمان المزامنة
        cloud_data = load_cloud_data()
        banned_users = set(cloud_data.get('banned_users', []))
        active_unban_codes = set(cloud_data.get('active_unban_codes', []))

        for entry in data['entry']:
            for event in entry.get('messaging', []):
                sender_id = str(event['sender']['id'])
                if 'message' in event:
                    msg = event['message']
                    user_text = msg.get('text', '').strip()

                    # أمر الإدارة لتوليد الكود
                    if user_text == "unban123":
                        new_code = str(random.randint(10000, 99999))
                        active_unban_codes.add(new_code)
                        cloud_data['active_unban_codes'] = list(active_unban_codes)
                        save_cloud_data(cloud_data) # حفظ في السحاب فوراً
                        send_fb_message(sender_id, f"🔑 كود فك الحظر: {new_code}")
                        continue

                    # فحص الحظر
                    if sender_id in banned_users:
                        if user_text in active_unban_codes:
                            active_unban_codes.remove(user_text)
                            banned_users.remove(sender_id)
                            cloud_data['active_unban_codes'] = list(active_unban_codes)
                            cloud_data['banned_users'] = list(banned_users)
                            save_cloud_data(cloud_data) # تحديث السحاب
                            send_fb_message(sender_id, "✅ تم فك الحظر عنك بنجاح!")
                            continue
                        continue # تجاهل المحظور

                    # المحقق الخفي
                    if user_text and is_message_inappropriate(user_text):
                        banned_users.add(sender_id)
                        cloud_data['banned_users'] = list(banned_users)
                        save_cloud_data(cloud_data) # تسجيل الحظر في السحاب
                        send_fb_message(sender_id, "🚫 تم حظرك بسبب الكلام النابي.")
                        continue

                    # الرد العادي
                    if 'text' in msg:
                        result = ask_groq_text(sender_id, user_text)
                        send_fb_message(sender_id, result)
                    elif 'attachments' in msg:
                        # (نفس دالة Gemini السابقة)
                        pass
    return "OK", 200

def send_fb_message(recipient_id, text):
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json={"recipient": {"id": recipient_id}, "message": {"text": text}})

if __name__ == '__main__':
    app.run()
