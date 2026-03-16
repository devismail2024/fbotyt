import os
import time
import base64
import requests
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# ⚙️ 1. Configuration (Vercel Env Variables)
# ==========================================
PAGE_ACCESS_TOKEN = "EAAg9vun0ll4BQ6kUjTMs3qKk2CmjsfbaW5CQd9GWtbxKHWQk8ZAU1j3jWNsR7DME9gNMpl773NffjPyvmCaVT3WCdhanc2qZBhyPdDKozHrGDrkxQJHNI4Wq8mV5i9Kc13ISBNHf4ZBdY071PnSpf2c4KHOJGUyx9RZCazZBsXDvewxrHb8dHA7wYA44s9fWZBltTtsAZDZD"
VERIFY_TOKEN = "ismail dev"
FB_API_URL = "https://graph.facebook.com/v19.0/me/messages"

# OpenRouter API Setup (أضف هذا في Vercel بدلا من Groq)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

user_histories = {}
user_cooldowns = {}
COOLDOWN_SECONDS = 30

# ==========================================
# 🧠 2. AI Engine (OpenRouter)
# ==========================================

def ask_ai(sender_id, user_message, is_image=False):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://your-vercel-app-url.vercel.app", # يفضل وضعه
        "X-Title": "Messenger Bot"
    }
    
    # Text routing
    if not is_image:
        if sender_id not in user_histories:
            user_histories[sender_id] = [{"role": "system", "content": "أنت مساعد ذكي ومرح، أجب بالدارجة المغربية باختصار."}]
            
        user_histories[sender_id].append({"role": "user", "content": user_message})
        
        payload = {
            "model": "google/gemini-2.5-flash:free", # موديل سريع، مجاني، ويدعم النصوص بكفاءة
            "messages": user_histories[sender_id]
        }
        
        try:
            response = requests.post(API_URL, headers=headers, json=payload)
            if response.status_code != 200:
                user_histories[sender_id].pop()
                print(f"❌ Text API Error: {response.text}")
                return "API provider error."
            
            ai_text = response.json()['choices'][0]['message']['content']
            user_histories[sender_id].append({"role": "assistant", "content": ai_text})
            
            if len(user_histories[sender_id]) > 6:
                user_histories[sender_id] = [user_histories[sender_id][0]] + user_histories[sender_id][-6:]
            return ai_text
            
        except Exception as e:
            print(f"⚠️ Text Exception: {str(e)}")
            if sender_id in user_histories: user_histories[sender_id].pop()
            return "An error occurred."

    # Image routing (معزول لضمان النجاح)
    else:
        try:
            image_response = requests.get(user_message)
            image_response.raise_for_status()
            base64_image = base64.b64encode(image_response.content).decode('utf-8')
            image_data_url = f"data:image/jpeg;base64,{base64_image}"
            
            vision_messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "شنو كاين فهاد التصويرة؟ شرح ليا بالدارجة المغربية باختصار."},
                        {"type": "image_url", "image_url": {"url": image_data_url}}
                    ]
                }
            ]
            
            payload = {
                # استخدمنا موديل Qwen للرؤية لأنه مجاني، سريع، ولا يواجه مشاكل 400
                "model": "qwen/qwen-2-vl-7b-instruct:free", 
                "messages": vision_messages
            }
            
            response = requests.post(API_URL, headers=headers, json=payload)
            
            if response.status_code != 200:
                print(f"❌ Vision Error: {response.text}")
                return "Vision API error."
            
            ai_text = response.json()['choices'][0]['message']['content']
            return ai_text
            
        except Exception as e:
            print(f"⚠️ Vision Exception: {str(e)}")
            return "Failed to process the image."

# ==========================================
# 🌐 3. Webhook Routes
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
                    
                    # Rate Limit
                    now = time.time()
                    if now - user_cooldowns.get(sender_id, 0) < COOLDOWN_SECONDS:
                        send_fb_message(sender_id, "Please wait...")
                        continue
                    user_cooldowns[sender_id] = now

                    if 'text' in msg:
                        result = ask_ai(sender_id, msg['text'], is_image=False)
                        send_fb_message(sender_id, result)
                    
                    elif 'attachments' in msg:
                        for att in msg['attachments']:
                            if att['type'] == 'image':
                                send_fb_message(sender_id, "Processing image...")
                                result = ask_ai(sender_id, att['payload']['url'], is_image=True)
                                send_fb_message(sender_id, result)
                                break
    return "OK", 200

def send_fb_message(recipient_id, text):
    requests.post(
        f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}",
        json={"recipient": {"id": recipient_id}, "message": {"text": text}}
    )

if __name__ == '__main__':
    app.run(port=5000, debug=True)
