import requests
from flask import Flask, request

app = Flask(__name__)

# --- الإعدادات (تأكد من صحتها) ---
PAGE_ACCESS_TOKEN = "EAAMU3XVe0ToBQwLOoFbirUZAlfhCNnPzebwF3aGiZC2LS7ZBOECZCNT9MG7au6csHzgBdkTnZA3pCreux1d5hK85PRZAbeeIonwtSdMF1cySHSEsMGYfbSrMlZB0ZASVWZCwEQlsC3NwYm3bJ5xxXirslnN3c5QAtln7RbYrT50oODCEqAuId6XrVqrwW2U88iJkku0oE2QZDZD"
VERIFY_TOKEN = "ismail dev"
REMOVEBG_API_KEY = "yKF8LxC4xLHECF4rvjhVWEgg"
IMGBB_API_KEY = 'اختياري_لرفع_الصور' # يمكنك الحصول عليه مجانا من imgbb.com

def send_text(recipient_id, text):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    requests.post(url, json=payload)

def send_image_url(recipient_id, image_url):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {"url": image_url, "is_reusable": True}
            }
        }
    }
    requests.post(url, json=payload)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Verification failed"

    if request.method == 'POST':
        data = request.get_json()
        if data.get('object') == 'page':
            for entry in data['entry']:
                for messaging_event in entry.get('messaging', []):
                    sender_id = messaging_event['sender']['id']
                    
                    if messaging_event.get('message'):
                        message = messaging_event['message']
                        
                        # التحقق من وجود صورة
                        if 'attachments' in message:
                            for attachment in message['attachments']:
                                if attachment['type'] == 'image':
                                    img_url = attachment['payload']['url']
                                    send_text(sender_id, "جاري حذف الخلفية... انتظر قليلاً ⏳")
                                    
                                    # معالجة الصورة عبر Remove.bg
                                    process_and_respond(sender_id, img_url)
                        
                        elif 'text' in message:
                            send_text(sender_id, "أهلاً بك! أرسل لي أي صورة وسأقوم بحذف خلفيتها فوراً.")
                            
        return "ok", 200

def process_and_respond(sender_id, img_url):
    # إرسال لـ Remove.bg
    response = requests.post(
        "https://api.remove.bg/v1.0/removebg",
        data={"image_url": img_url, "size": "auto"},
        headers={"X-Api-Key": REMOVEBG_API_KEY},
    )
    
    if response.status_code == 200:
        # ملاحظة: لكي يرسل فيسبوك الصورة، يجب أن تكون مرفوعة على رابط.
        # يمكنك إرسالها كـ Binary ولكن الطريقة الأسهل هي رفعها مؤقتاً.
        # للتجربة السريعة: سأعلمك كيف ترسلها كـ ملف مرفق مباشرة.
        files = {
            'message': (None, '{"attachment":{"type":"image", "payload":{}}}'),
            'filedata': ('no_bg.png', response.content, 'image/png'),
            'recipient': (None, f'{{"id":"{sender_id}"}}')
        }
        requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", files=files)
    else:
        send_text(sender_id, "عذراً، حدث خطأ أثناء معالجة الصورة. تأكد من جودتها أو رصيد الـ API.")

if __name__ == '__main__':
    app.run()