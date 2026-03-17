import os
import time
import requests
from flask import Flask, request
from google import genai
from google.genai import types

app = Flask(__name__)

# ==========================================
# ⚙️ 1. Configuration (Vercel Env Variables)
# ==========================================
PAGE_ACCESS_TOKEN = "EAAg9vun0ll4BQ6kUjTMs3qKk2CmjsfbaW5CQd9GWtbxKHWQk8ZAU1j3jWNsR7DME9gNMpl773NffjPyvmCaVT3WCdhanc2qZBhyPdDKozHrGDrkxQJHNI4Wq8mV5i9Kc13ISBNHf4ZBdY071PnSpf2c4KHOJGUyx9RZCazZBsXDvewxrHb8dHA7wYA44s9fWZBltTtsAZDZD"
VERIFY_TOKEN = "ismail dev"
FB_API_URL = "https://graph.facebook.com/v19.0/me/messages"

# مفاتيح الـ API من Vercel
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# تهيئة عميل Gemini للصور
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

user_histories = {}
user_cooldowns = {}
COOLDOWN_SECONDS = 30

# ==========================================
# 🧠 2. Text Engine (OpenRouter)
# ==========================================
def ask_ai_text(sender_id, user_message):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://your-vercel-app-url.vercel.app", 
        "X-Title": "Messenger Bot" [cite: 2]
    }
    
    if sender_id not in user_histories:
        user_histories[sender_id] = [{"role": "system", "content": "أنت مساعد ذكي ومرح، أجب بالدارجة المغربية باختصار."}]
        
    user_histories[sender_id].append({"role": "user", "content": user_message})
    
    payload = {
        "model": "google/gemini-2.5-flash:free", [cite: 3]
        "messages": user_histories[sender_id]
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code != 200:
            user_histories[sender_id].pop() [cite: 4]
            print(f"❌ Text API Error: {response.text}")
            return "API provider error."
        
        ai_text = response.json()['choices'][0]['message']['content'] [cite: 5]
        user_histories[sender_id].append({"role": "assistant", "content": ai_text})
        
        if len(user_histories[sender_id]) > 6:
            user_histories[sender_id] = [user_histories[sender_id][0]] + user_histories[sender_id][-6:]
        return ai_text
        
    except Exception as e: [cite: 6]
        print(f"⚠️ Text Exception: {str(e)}")
        if sender_id in user_histories: user_histories[sender_id].pop()
        return "An error occurred."

# ==========================================
# 👁️ 3. Vision Engine (Direct Gemini API)
# ==========================================
def analyze_image_with_gemini(image_url):
    if not gemini_client:
        return "Gemini API key is not configured in Vercel."
        
    try:
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        image_bytes = image_response.content
        
        prompt = "شنو كاين فهاد التصويرة؟ شرح ليا بالدارجة المغربية باختصار."
        
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                prompt
            ],
            config=types.GenerateContentConfig(
                system_instruction="أنت مساعد ذكي، أجب بالدارجة المغربية باختصار."
            )
        )
        return response.text
    except Exception as e:
        print(f"⚠️ Gemini Vision Error: {e}")
        return "Failed to process the image."

# ==========================================
# 🌐 4. Webhook Routes
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
                if 'message' in event: [cite: 14]
                    msg = event['message']
                    
                    # Rate Limit
                    now = time.time()
                    if now - user_cooldowns.get(sender_id, 0) < COOLDOWN_SECONDS: [cite: 15]
                        send_fb_message(sender_id, "Please wait...")
                        continue
                    user_cooldowns[sender_id] = now

                    # التوجيه الذكي (Routing)
                    if 'text' in msg: [cite: 16]
                        result = ask_ai_text(sender_id, msg['text'])
                        send_fb_message(sender_id, result)
                    
                    elif 'attachments' in msg: [cite: 17]
                        for att in msg['attachments']:
                            if att['type'] == 'image':
                                send_fb_message(sender_id, "Processing image...") [cite: 18]
                                result = analyze_image_with_gemini(att['payload']['url'])
                                send_fb_message(sender_id, result)
                                break [cite: 19]
    return "OK", 200

def send_fb_message(recipient_id, text):
    requests.post(
        f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}",
        json={"recipient": {"id": recipient_id}, "message": {"text": text}}
    )

if __name__ == '__main__':
    app.run(port=5000, debug=True)
