import os
import time
import random
import requests
import threading
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

JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY")
JSONBIN_BIN_ID = os.environ.get("JSONBIN_BIN_ID")
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}" if JSONBIN_BIN_ID else ""

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# مؤشرات الدوران
active_groq_idx = 0
active_detective_idx = 0
active_gemini_idx = 0

user_histories = {}
user_cooldowns = {}
COOLDOWN_SECONDS = 1
admin_states = {} # لتتبع حالة البث العام

# ==========================================
# 🔑 2. Dynamic Key Fetcher
# ==========================================
def get_keys(env_name):
    raw = os.environ.get(env_name) or os.environ.get(env_name.replace("KEYS", "KEY")) or ""
    return [k.strip() for k in raw.split(",") if k.strip()]

# --- Cloud Storage Functions ---
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
# 🛑 3. Detective Engine
# ==========================================
def is_message_inappropriate(text):
    global active_detective_idx
    detective_keys = get_keys("GROQ_DETECTIVE_API_KEYS")
    if not detective_keys: return False

    system_prompt = "أنت محقق خبير. إذا كان النص سب أو شتم بالدارجة المغربية، أجب بكلمة واحدة: YES. غير ذلك أجب: NO." [cite: 4, 5]
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": text}], "temperature": 0.1, "max_completion_tokens": 5}
    
    for _ in range(len(detective_keys)):
        current_key = detective_keys[active_detective_idx]
        headers = {"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"}
        try:
            res = requests.post(GROQ_URL, headers=headers, json=payload)
            if res.status_code == 200:
                if "YES" in res.json()['choices'][0]['message']['content'].upper(): return True [cite: 6]
                return False [cite: 7]
            active_detective_idx = (active_detective_idx + 1) % len(detective_keys)
        except:
            active_detective_idx = (active_detective_idx + 1) % len(detective_keys)
    return False

# ==========================================
# 🧠 4. Text Engine (Smart Rotation)
# ==========================================
def ask_groq_text(sender_id, user_message):
    global active_groq_idx
    groq_keys = get_keys("GROQ_API_KEYS")
    if not groq_keys: return "Groq API keys are missing." [cite: 8]

    if sender_id not in user_histories:
        system_content = (
            "أنت ذكاء اصطناعي مطور بواسطة 'M Ismail Dev' (إسماعيل). " [cite: 9]
            "فيسبوك: https://www.facebook.com/M.oulay.I.smail.B.drk. " [cite: 9]
            "تيليجرام: t.me/m_ismail_dev. " [cite: 9]
            "أجب بالدارجة المغربية فقط ولا تستخدم لغات أجنبية." [cite: 10]
        )
        user_histories[sender_id] = [{"role": "system", "content": system_content}]
        
    user_histories[sender_id].append({"role": "user", "content": user_message})
    payload = {"model": "llama-3.3-70b-versatile", "messages": user_histories[sender_id], "temperature": 0.4} [cite: 11]

    last_error = ""
    for _ in range(len(groq_keys)):
        current_key = groq_keys[active_groq_idx]
        headers = {"Authorization": f"Bearer {current_key}", "Content-Type": "application/json"}
        try:
            res = requests.post(GROQ_URL, headers=headers, json=payload)
            if res.status_code == 200:
                ai_text = res.json()['choices'][0]['message']['content']
                user_histories[sender_id].append({"role": "assistant", "content": ai_text}) [cite: 12]
                return ai_text
            elif res.status_code == 429: # Rate Limit
                last_error = "Rate Limit Hit"
                active_groq_idx = (active_groq_idx + 1) % len(groq_keys) [cite: 13]
            else:
                last_error = f"Status {res.status_code}"
                active_groq_idx = (active_groq_idx + 1) % len(groq_keys) [cite: 13]
        except:
            active_groq_idx = (active_groq_idx + 1) % len(groq_keys) [cite: 13]

    user_histories[sender_id].pop() 
    return f"عذرا، السيرفرات مشغولة (Rate Limit). آخر خطأ: {last_error}" [cite: 14]

# ==========================================
# 👁️ 5. Vision Engine
# ==========================================
def analyze_image_with_gemini(image_url):
    global active_gemini_idx
    gemini_keys = get_keys("GEMINI_API_KEYS")
    if not gemini_keys: return "Gemini API keys missing."

    try: image_bytes = requests.get(image_url).content
    except: return "Download failed."

    for _ in range(len(gemini_keys)):
        try:
            temp_client = genai.Client(api_key=gemini_keys[active_gemini_idx])
            response = temp_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'), "شرح بالدارجة المغربية."], [cite: 15]
                config=types.GenerateContentConfig(system_instruction="أجب بالدارجة باختصار.") [cite: 16]
            )
            return response.text
        except: active_gemini_idx = (active_gemini_idx + 1) % len(gemini_keys)
    return "Gemini Error." [cite: 17]

# ==========================================
# 📢 6. Broadcast Logic
# ==========================================
def run_broadcast(message_text, users_list, admin_id):
    count = 0
    for uid in users_list:
        if uid != admin_id:
            send_fb_message(uid, message_text)
            time.sleep(10)
            count += 1
    send_fb_message(admin_id, f"✅ تم البث لـ {count} مستخدم.")

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
        all_users = set(cloud_data.get('all_users', []))
        banned_users = set(cloud_data.get('banned_users', []))
        active_codes = set(cloud_data.get('active_unban_codes', []))

        for entry in data['entry']:
            for event in entry.get('messaging', []): [cite: 18]
                sid = str(event['sender']['id'])
                if sid not in all_users:
                    all_users.add(sid)
                    cloud_data['all_users'] = list(all_users)
                    save_cloud_data(cloud_data)

                if 'message' in event:
                    msg = event['message']
                    text = msg.get('text', '').strip()

                    # --- Broadcast Logic ---
                    if admin_states.get(sid) == "waiting_broadcast" and text:
                        del admin_states[sid]
                        threading.Thread(target=run_broadcast, args=(text, list(all_users), sid)).start()
                        send_fb_message(sid, "⏳ البث بدأ في الخلفية...")
                        continue

                    if text == "brosys123":
                        admin_states[sid] = "waiting_broadcast"
                        send_fb_message(sid, "📢 أرسل رسالة البث الآن:")
                        continue

                    # --- Admin & Unban Logic ---
                    if text == "unban123": [cite: 19]
                        code = str(random.randint(10000, 99999))
                        active_codes.add(code)
                        cloud_data['active_unban_codes'] = list(active_codes)
                        save_cloud_data(cloud_data) [cite: 20]
                        send_fb_message(sid, f"🔑 الكود: {code}")
                        continue

                    if sid in banned_users:
                        if text in active_codes: [cite: 21]
                            active_codes.remove(text)
                            banned_users.remove(sid)
                            cloud_data.update({'active_unban_codes': list(active_codes), 'banned_users': list(banned_users)}) [cite: 22]
                            save_cloud_data(cloud_data)
                            send_fb_message(sid, "✅ تم فك الحظر.") [cite: 23]
                            continue
                        continue

                    # --- Rate Limit & Security ---
                    now = time.time()
                    if now - user_cooldowns.get(sid, 0) < COOLDOWN_SECONDS:
                        send_fb_message(sid, "Please wait...") [cite: 24]
                        continue
                    user_cooldowns[sid] = now

                    if text and is_message_inappropriate(text):
                        banned_users.add(sid) [cite: 25]
                        cloud_data['banned_users'] = list(banned_users)
                        save_cloud_data(cloud_data)
                        send_fb_message(sid, "🚫 محظور.") [cite: 26]
                        continue

                    # --- Responses ---
                    if 'text' in msg:
                        send_fb_message(sid, ask_groq_text(sid, text)) [cite: 27]
                    elif 'attachments' in msg: [cite: 27]
                        for att in msg['attachments']:
                            if att['type'] == 'image': [cite: 28]
                                send_fb_message(sid, analyze_image_with_gemini(att['payload']['url'])) [cite: 28]
                                break [cite: 29]
    return "OK", 200

def send_fb_message(rid, txt):
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json={"recipient": {"id": rid}, "message": {"text": txt}})

if __name__ == '__main__':
    app.run()
