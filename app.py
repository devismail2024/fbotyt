import os
import time
import requests
from flask import Flask, request
from google import genai
from google.genai import types

app = Flask(__name__)

PAGE_ACCESS_TOKEN = "EAAg9vun0ll4BQ6kUjTMs3qKk2CmjsfbaW5CQd9GWtbxKHWQk8ZAU1j3jWNsR7DME9gNMpl773NffjPyvmCaVT3WCdhanc2qZBhyPdDKozHrGDrkxQJHNI4Wq8mV5i9Kc13ISBNHf4ZBdY071PnSpf2c4KHOJGUyx9RZCazZBsXDvewxrHb8dHA7wYA44s9fWZBltTtsAZDZD"
VERIFY_TOKEN = "ismail dev"
FB_API_URL = "https://graph.facebook.com/v19.0/me/messages"

keys_from_vercel = os.environ.get("GEMINI_KEYS", "")
API_KEYS = [key.strip() for key in keys_from_vercel.split(",") if key.strip()]

# إذا نسينا وضع المفاتيح في Vercel، الكود لن ينهار بل سيعطينا تحذيراً
if not API_KEYS:
    print("⚠️ تحذير: لم يتم العثور على مفاتيح Gemini في إعدادات Vercel!")
    
current_key_index = 0  

user_cooldowns = {}  
user_histories = {}  
COOLDOWN_SECONDS = 30
MAX_HISTORY_LENGTH = 10 

def log_system_error(where, error_details):
    print("="*50)
    print(f"❌ [ERROR IN: {where}]")
    print(f"⚠️ DETAILS: {error_details}")
    print("="*50)

def get_gemini_client():
    global current_key_index
    return genai.Client(api_key=API_KEYS[current_key_index])

def switch_to_next_key():
    global current_key_index
    old_index = current_key_index
    current_key_index = (current_key_index + 1) % len(API_KEYS)
    print(f"🔄 [KEY ROTATION] Key {old_index + 1} died. Switched to Key {current_key_index + 1}")

def send_text_message(recipient_id, text):
    try:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
        response = requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json=payload, headers=headers)
        response.raise_for_status()
    except Exception as e:
        log_system_error("Facebook Message Send", str(e))

def ask_gemini_text(sender_id, user_text):
    max_attempts = len(API_KEYS)

    if sender_id not in user_histories:
        user_histories[sender_id] = []
    
    user_histories[sender_id].append(
        types.Content(role="user", parts=[types.Part.from_text(text=user_text)])
    )

    for attempt in range(max_attempts):
        try:
            client = get_gemini_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_histories[sender_id],
                config=types.GenerateContentConfig(
                    system_instruction="أنت مساعد ذكي ومرح، أجب بالدارجة المغربية باختصار."
                )
            )

            user_histories[sender_id].append(
                types.Content(role="model", parts=[types.Part.from_text(text=response.text)])
            )
            if len(user_histories[sender_id]) > MAX_HISTORY_LENGTH:
                user_histories[sender_id] = user_histories[sender_id][-MAX_HISTORY_LENGTH:]
            
            return response.text

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                if attempt == max_attempts - 1:
                    log_system_error("ALL KEYS DEAD", "api credits expired")
                    user_histories[sender_id].pop()
                    return "error in api keys now"
                switch_to_next_key()
                continue
            else:
                log_system_error("Gemini Text Generation", error_msg)
                
                # أضفنا هذا السطر لحماية إضافية قبل عمل pop
                if sender_id in user_histories and len(user_histories[sender_id]) > 0:
                    user_histories[sender_id].pop()
                
                # الخدعة: إرسال الخطأ الحقيقي مباشرة لك في ماسنجر!
                return f"شوف أ عشيري، هذا هو الخطأ لي واقع في Vercel:\n\n{error_msg}"
def analyze_image_with_gemini(sender_id, image_url):
    max_attempts = len(API_KEYS)
    
    if sender_id not in user_histories:
        user_histories[sender_id] = []

    try:
        image_response = requests.get(image_url)
        image_response.raise_for_status() 
        image_bytes = image_response.content
        prompt = "ماذا تلاحظ في الصورة بإختصار تام"
        
        user_histories[sender_id].append(
            types.Content(
                role="user", 
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                    types.Part.from_text(text=prompt)
                ]
            )
        )
    except Exception as e:
        log_system_error("Image Download", str(e))
        return "خطأ في التحميل جرب مرة أخرى"

    for attempt in range(max_attempts):
        try:
            client = get_gemini_client()
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_histories[sender_id],
                config=types.GenerateContentConfig(
                    system_instruction="أنت مساعد ذكي، أجب بالدارجة المغربية باختصار."
                )
            )

            user_histories[sender_id].append(
                types.Content(role="model", parts=[types.Part.from_text(text=response.text)])
            )
            if len(user_histories[sender_id]) > MAX_HISTORY_LENGTH:
                user_histories[sender_id] = user_histories[sender_id][-MAX_HISTORY_LENGTH:]
                
            return response.text

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                if attempt == max_attempts - 1:
                    user_histories[sender_id].pop()
                    return "هناك ضغط على السيرفر حاليا جرب مرة أخرى لاحقا"
                switch_to_next_key()
                continue
            else:
                log_system_error("Gemini Image Vision", error_msg)
                user_histories[sender_id].pop()
                return "image not visible"

@app.route('/webhook', methods=['GET'])
def webhook_get():
    hub_mode = request.args.get("hub.mode")
    hub_challenge = request.args.get("hub.challenge")
    hub_verify_token = request.args.get("hub.verify_token")
    if hub_mode == "subscribe" and hub_challenge and hub_verify_token == VERIFY_TOKEN:
        return hub_challenge, 200
    return "Vercel AI Bot (Elite Edition) is Live!", 200

@app.route('/webhook', methods=['POST'])
def webhook_post():
    try:
        data = request.get_json()
        if data.get('object') == 'page':
            for entry in data['entry']:
                for messaging_event in entry.get('messaging', []):
                    sender_id = messaging_event['sender']['id']
                    
                    if messaging_event.get('message'):
                        message = messaging_event['message']
                        
                    
                        current_time = time.time()
                        last_request_time = user_cooldowns.get(sender_id, 0)
                        elapsed_time = current_time - last_request_time
                        
                        if elapsed_time < COOLDOWN_SECONDS:
                            remaining_time = int(COOLDOWN_SECONDS - elapsed_time)
                            warning_msg = f"pls wait for{remaining_time} secs"
                            send_text_message(sender_id, warning_msg)
                            continue  
                            
                        user_cooldowns[sender_id] = current_time

                        if 'text' in message:
                            user_input = message['text']
                            ai_response = ask_gemini_text(sender_id, user_input)
                            send_text_message(sender_id, ai_response)
                            
                        elif 'attachments' in message:
                            for attachment in message['attachments']:
                                if attachment['type'] == 'image':
                                    img_url = attachment['payload']['url']
                                    send_text_message(sender_id, "جاري تحليل الضورة...")
                                    ai_response = analyze_image_with_gemini(sender_id, img_url)
                                    send_text_message(sender_id, ai_response)
                                    break
    except Exception as e:
        log_system_error("Webhook POST Parsing", str(e))
        
    return "EVENT_RECEIVED", 200

if __name__ == '__main__':
    app.run()
