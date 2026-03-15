import os
import requests
from flask import Flask, request
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# --- الإعدادات الثابتة الخاصة بك ---
PAGE_ACCESS_TOKEN = "EAAg9vun0ll4BQ6kUjTMs3qKk2CmjsfbaW5CQd9GWtbxKHWQk8ZAU1j3jWNsR7DME9gNMpl773NffjPyvmCaVT3WCdhanc2qZBhyPdDKozHrGDrkxQJHNI4Wq8mV5i9Kc13ISBNHf4ZBdY071PnSpf2c4KHOJGUyx9RZCazZBsXDvewxrHb8dHA7wYA44s9fWZBltTtsAZDZD"
VERIFY_TOKEN = "ismail dev"
FB_API_URL = "https://graph.facebook.com/v19.0/me/messages"

cloudinary.config( 
  cloud_name = "doft8g1ar", 
  api_key = "395867115937299", 
  api_secret = "LL9sxMO5NTOy2JHvCYLaYtHpm44",
  secure = True
)

user_images = {}

@app.route('/webhook', methods=['GET'])
def webhook_get():
    hub_mode = request.args.get("hub.mode")
    hub_challenge = request.args.get("hub.challenge")
    hub_verify_token = request.args.get("hub.verify_token")
    if hub_mode == "subscribe" and hub_challenge:
        if hub_verify_token == VERIFY_TOKEN:
            return hub_challenge, 200
        else:
            return "Verification failed", 403
    return "Bot is Running", 200

@app.route('/webhook', methods=['POST'])
def webhook_post():
    data = request.get_json()
    if data.get('object') == 'page':
        for entry in data['entry']:
            for messaging_event in entry.get('messaging', []):
                sender_id = messaging_event['sender']['id']
                
                if messaging_event.get('message'):
                    message = messaging_event['message']
                    
                    if 'attachments' in message:
                        for attachment in message['attachments']:
                            if attachment['type'] == 'image':
                                img_url = attachment['payload']['url']
                                user_images[sender_id] = img_url
                                
                                menu_text = (
                                    "وصلات بنجااح\n"
                                    "سيفت رقم\n\n"
                                    "1 - أنميي 🎌\n"
                                    "2 - زيتونية 🖼️\n"
                                    "3 - زجااجي\n\n" # غيرنا هذا لضمان العمل
                                    "شيفت رقم 123"
                                )
                                send_text_message(sender_id, menu_text)
                                break

                    elif 'text' in message:
                        user_text = message['text'].strip()
                        saved_url = user_images.get(sender_id)
                        
                        if user_text in ["1", "2", "3"] and saved_url:
                            # هذه هي الأسماء البرمجية الصحيحة لـ Cloudinary API
                            effects = {
                                "1": "cartoonify",
                                "2": "art:al_dente", # ستايل فني يشبه الزيتي وقوي جداً
                                "3": "art:audrey"    # ستايل كلاسيكي مميز
                            }
                            selected_effect = effects[user_text]
                            
                            send_text_message(sender_id, f"appling... {user_text}... ⏳")
                            process_image(sender_id, saved_url, selected_effect)
                        elif saved_url:
                            send_text_message(sender_id, "سيفت رقم تاع ستيل 123")
                        else:
                            send_text_message(sender_id, "مالك على هاد دخلة. سيفت صورة ")
                        
    return "EVENT_RECEIVED", 200

def process_image(recipient_id, user_img_url, effect_name):
    try:
        # ملاحظة: بعض التأثيرات تحتاج أن نحدد النوع كـ 'art'
        upload_result = cloudinary.uploader.upload(
            user_img_url,
            transformation=[{'effect': effect_name}]
        )
        final_url = upload_result.get('secure_url')
        if final_url:
            send_image_message(recipient_id, final_url)
        else:
            send_text_message(recipient_id, "فشل المعالجة")
    except Exception as e:
        print(f"Error: {e}")
        send_text_message(recipient_id, "جرب ستيل أخر هذا ماخدامش")

def send_text_message(recipient_id, text):
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json=payload, headers=headers)

def send_image_message(recipient_id, image_url):
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"attachment": {"type": "image", "payload": {"url": image_url, "is_reusable": True}}}
    }
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json=payload)

if __name__ == '__main__':
    app.run()
