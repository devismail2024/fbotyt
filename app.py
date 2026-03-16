import os
import time
import requests
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# ⚙️ 1. الإعدادات (Vercel Env Variables)
# ==========================================
PAGE_ACCESS_TOKEN = "EAAg9vun0ll4BQ6kUjTMs3qKk2CmjsfbaW5CQd9GWtbxKHWQk8ZAU1j3jWNsR7DME9gNMpl773NffjPyvmCaVT3WCdhanc2qZBhyPdDKozHrGDrkxQJHNI4Wq8mV5i9Kc13ISBNHf4ZBdY071PnSpf2c4KHOJGUyx9RZCazZBsXDvewxrHb8dHA7wYA44s9fWZBltTtsAZDZD"
VERIFY_TOKEN = "ismail dev"
FB_API_URL = "https://graph.facebook.com/v19.0/me/messages"

# مفتاح Groq (يُجلب من إعدادات فيرسيل)
GROQ_API_KEY = os.environ.get("GROQ_API_KE")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ذاكرة مؤقتة ونظام الحماية
user_histories = {}
user_cooldowns = {}
COOLDOWN_SECONDS = 30
MAX_HISTORY = 10

# ==========================================
# 🧠 2. دوال الذكاء الاصطناعي (Groq)
# ==========================================

def ask_groq(sender_id, content_payload):
    """إرسال الطلب لـ Groq باستخدام Requests فقط"""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # تهيئة الذاكرة
    if sender_id not in user_histories:
        user_histories[sender_id] = [
            {"role": "system", "content": "أنت مساعد ذكي ومرح، تم تطيرك بواسطة مطور مستقل مشهور إسمه إسماعيل المعروف على مواقع التواصل بM Ismail dev ولست تابعا لأي شركة مشهورة, أنت تحت تطير وإدارة وتدريب كامل من طرف إسماعيل كليا"}
        ]
    
    # إضافة الرسالة الجديدة للذاكرة
    user_histories[sender_id].append({"role": "user", "content": content_payload})

    payload = {
        "model": "llama-3.2-11b-vision-preview", # موديل الرؤية القوي
        "messages": user_histories[sender_id],
        "max_tokens": 500
    }

    try:
        response = requests.post(GROQ_URL, json=payload, headers=headers)
        response.raise_for_status()
        res_data = response.json()
        
        ai_text = res_data['choices'][0]['message']['content']
        
        # حفظ الرد في الذاكرة
        user_histories[sender_id].append({"role": "assistant", "content": ai_text})
        
        # تنظيف الذاكرة
        if len(user_histories[sender_id]) > MAX_HISTORY:
            user_histories[sender_id] = [user_histories[sender_id][0]] + user_histories[sender_id][-MAX_HISTORY:]
            
        return ai_text
    except Exception as e:
        print(f"Groq Error: {e}")
        return "internal serverr eroooooor"

# ==========================================
# 🌐 3. مسارات الويب والتواصل مع فيسبوك
# ==========================================

@app.route('/webhook', methods=['GET'])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Verification failed", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data.get('object') == 'page':
        for entry in data['entry']:
            for event in entry.get('messaging', []):
                sender_id = event['sender']['id']
                if 'message' in event:
                    msg = event['message']
                    
                    # 🛡️ Rate Limit
                    now = time.time()
                    if now - user_cooldowns.get(sender_id, 0) < COOLDOWN_SECONDS:
                        send_fb_message(sender_id, "wait...")
                        continue
                    user_cooldowns[sender_id] = now

                    # معالجة النصوص
                    if 'text' in msg:
                        response = ask_groq(sender_id, msg['text'])
                        send_fb_message(sender_id, response)
                    
                    # معالجة الصور (Vision)
                    elif 'attachments' in msg:
                        for att in msg['attachments']:
                            if att['type'] == 'image':
                                img_url = att['payload']['url']
                                send_fb_message(sender_id, "جاري تحليل الصورة...")
                                # في Groq، نرسل رابط الصورة مباشرة داخل الـ Payload
                                content = [
                                    {"type": "text", "text": "ماذا تلاحظ في الصورة"},
                                    {"type": "image_url", "image_url": {"url": img_url}}
                                ]
                                response = ask_groq(sender_id, content)
                                send_fb_message(sender_id, response)
                                break
    return "OK", 200

def send_fb_message(recipient_id, text):
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json=payload)

if __name__ == '__main__':
    app.run()
