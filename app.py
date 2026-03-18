import os
import time
import random
import requests
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# ⚙️ 1. Configuration & Global States
# ==========================================
PAGE_ACCESS_TOKEN = "EAAg9vun0ll4BQ6kUjTMs3qKk2CmjsfbaW5CQd9GWtbxKHWQk8ZAU1j3jWNsR7DME9gNMpl773NffjPyvmCaVT3WCdhanc2qZBhyPdDKozHrGDrkxQJHNI4Wq8mV5i9Kc13ISBNHf4ZBdY071PnSpf2c4KHOJGUyx9RZCazZBsXDvewxrHb8dHA7wYA44s9fWZBltTtsAZDZD"
VERIFY_TOKEN = "ismail dev"
FB_API_URL = "https://graph.facebook.com/v19.0/me/messages"

JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY")
JSONBIN_BIN_ID = os.environ.get("JSONBIN_BIN_ID")
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}" if JSONBIN_BIN_ID else ""

TEXT_API = "https://obito-mr-apis-2.vercel.app/api/ai/copilot"
IMAGE_GEN_API = "https://obito-mr-apis.vercel.app/api/ai/deepImg"

user_states = {} 
user_cooldowns = {}
COOLDOWN_SECONDS = 1

STYLES = {"1": "default", "2": "ghibli", "3": "cyberpunk", "4": "anime", "5": "portrait", "6": "chibi", "7": "pixel", "8": "oil", "9": "3d"}
SIZES = {"1": "1:1", "2": "3:2", "3": "2:3"}

# ==========================================
# ☁️ 2. Cloud Storage
# ==========================================
def load_cloud_data():
    default_data = {"banned_users_dict": {}, "active_unban_codes": [], "all_users": []}
    if not JSONBIN_URL: return default_data
    try:
        res = requests.get(JSONBIN_URL, headers={"X-Master-Key": JSONBIN_API_KEY})
        if res.status_code == 200:
            data = res.json()['record']
            if "all_users" not in data: data["all_users"] = []
            if "banned_users_dict" not in data: data["banned_users_dict"] = {}
            return data
    except: pass
    return default_data

def save_cloud_data(data):
    if not JSONBIN_URL: return
    requests.put(JSONBIN_URL, json=data, headers={"Content-Type": "application/json", "X-Master-Key": JSONBIN_API_KEY})

# ==========================================
# 🧠 3. AI & Image Engines
# ==========================================
# ==========================================
# 🛑 2. Detective Engine (نسخة الذكاء المنطقي)
# ==========================================
# ==========================================
# 🛑 2. Detective Engine (نسخة النينجا السريعة)
# ==========================================
def is_message_inappropriate(text):
    """محقق الأخلاق المطور ليكون سريعاً ولا يعطل الأوامر"""
    clean_text = text.strip()
    
    # 🚀 1. فلاتر صاروخية لتجاوز الـ API كلياً (توفر 15 ثانية!)
    if clean_text.startswith("."): return False
    if len(clean_text) <= 2: return False # يتجاوز الأرقام والردود القصيرة جداً مثل "1", "2"
    if clean_text.isdigit(): return False # يتجاوز أي أرقام
    
    # ⚡ 2. تعليمات قصيرة جداً لتقليل وقت التفكير لدى Copilot
    instruction = f"أجب بـ YES فقط إذا كان هذا النص سب أو قذف صريح، وأجب بـ NO إذا كان كلام عادي أو مصطلح تقني. النص: '{clean_text}'"
    
    try:
        # مهلة 8 ثوانٍ كحد أقصى للمحقق لكي لا يتسبب في قتل السيرفر
        res = requests.get(TEXT_API, params={"text": instruction}, timeout=8)
        if res.status_code == 200:
            answer = res.json().get("answer", "").upper()
            if "YES" in answer and len(answer) < 6: 
                return True
    except: 
        pass # في حالة تأخر السيرفر، نسمح بمرور الرسالة لكي لا يتعطل البوت
    return False

def ask_copilot(user_message, image_url=None, web_search=False):
    # 👈 تم تعديل شخصية الذكاء ليعترف بأنك من قمت بدمجه وبرمجته في فيسبوك
    system = "أنت ذكاء اصطناعي تم إستخدام الapi الخاص بك لبرمجة بوت فيسبوك ميسنجر من طرف المبرمج المشهور M Ismail Dev, أجب دائما باختصار دون كثرت الكلام وبأسلوب مرح "
    if not web_search: system += " لا تبحث في الويب."
    try:
        res = requests.get(TEXT_API, params={"text": f"{system} {user_message}", "imageUrl": image_url}, timeout=30)
        return res.json().get("answer", "عذرا، وقع خطأ."), None
    except Exception as e: return None, str(e)

def generate_image_sync(prompt, style, size):
    params = {"txt": prompt, "style": style, "size": size}
    try:
        res = requests.get(IMAGE_GEN_API, params=params, timeout=45)
        if res.status_code == 200:
            raw_url = res.json().get("data", {}).get("image_url")
            if raw_url:
                final_url, _ = upload_to_catbox(raw_url)
                return final_url if final_url else raw_url, None
        return None, f"API Error: {res.status_code}"
    except Exception as e: return None, str(e)

def upload_to_catbox(image_url):
    try:
        img_data = requests.get(image_url).content
        res = requests.post("https://catbox.moe/user/api.php", 
                            data={"reqtype": "fileupload", "userhash": ""}, 
                            files={"fileToUpload": ("image.jpg", img_data, "image/jpeg")})
        return res.text.strip(), None
    except Exception as e: return None, str(e)

# ==========================================
# 🌐 4. Main Router
# ==========================================
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return request.args.get("hub.challenge", "Failed"), 200 if request.args.get("hub.verify_token") == VERIFY_TOKEN else 403

    data = request.get_json()
    if data.get('object') == 'page':
        cloud_data = load_cloud_data()
        all_users = set(cloud_data.get('all_users', []))
        banned_users = cloud_data.get('banned_users_dict', {})
        active_codes = set(cloud_data.get('active_unban_codes', []))

        for entry in data['entry']:
            for event in entry.get('messaging', []):
                sid = str(event['sender']['id'])
                msg = event.get('message', {})
                text = msg.get('text', '').strip()
                attachments = msg.get('attachments', [])

                if sid not in all_users:
                    all_users.add(sid); cloud_data['all_users'] = list(all_users); save_cloud_data(cloud_data)
                    send_fb_message(sid, "👋 أهلاً بك! أنا بوت M Ismail Dev.\nتابعني: https://www.facebook.com/M.oulay.I.smail.B.drk")
                    send_menu(sid); continue

                if text == "unban123":
                    code = str(random.randint(10000, 99999))
                    active_codes.add(code); cloud_data['active_unban_codes'] = list(active_codes); save_cloud_data(cloud_data)
                    send_fb_message(sid, f"🔑 كود فك الحظر: {code}"); continue

                if sid in banned_users:
                    if text in active_codes:
                        active_codes.remove(text); del banned_users[sid]
                        cloud_data['active_unban_codes'] = list(active_codes); cloud_data['banned_users_dict'] = banned_users
                        save_cloud_data(cloud_data); send_fb_message(sid, "✅ تم فك الحظر بنجاح!")
                    continue

                state = user_states.get(sid, {})
                step = state.get("step")

                if step:
                    if step == "broadcast_wait":
                        for uid in all_users:
                            if uid != sid: send_fb_message(uid, text); time.sleep(0.3)
                        send_fb_message(sid, "✅ تم البث."); del user_states[sid]
                        
                    elif step == "gen_style":
                        if text in STYLES:
                            state.update({"step": "gen_size", "data": {**state["data"], "style": STYLES[text]}})
                            user_states[sid] = state
                            # 👈 رسالة الأبعاد منظمة
                            size_msg = "📐 **أدخل رقم البعد الذي تريده:**\n\n1- مربع (1:1)\n2- أفقي (3:2)\n3- عمودي (2:3)"
                            send_fb_message(sid, size_msg)
                        else: send_fb_message(sid, "❌ الرجاء اختيار رقم صحيح من 1 إلى 9.")
                        
                    elif step == "gen_size":
                        if text in SIZES:
                            send_fb_message(sid, "🎨 جاري الإنشاء... (قد يستغرق الأمر دقيقة)")
                            
                            # 🛡️ الدرع الواقي: حفظ البيانات وتغيير الحالة فوراً لمنع تكرار فيسبوك
                            prompt = state["data"]["prompt"]
                            style = state["data"]["style"]
                            size = SIZES[text]
                            user_states[sid] = {"step": "locked_processing"} # إغلاق الحالة
                            
                            url, err = generate_image_sync(prompt, style, size)
                            if url: send_fb_image(sid, url)
                            else: send_fb_message(sid, f"❌ خطأ: {err}")
                            
                            # تنظيف الحالة فقط إذا كانت لا تزال مغلقة
                            if user_states.get(sid, {}).get("step") == "locked_processing":
                                del user_states[sid]
                        else: send_fb_message(sid, "❌ الرجاء اختيار رقم صحيح من 1 إلى 3.")
                        
                    elif step == "web_query":
                        send_fb_message(sid, "🔍 جاري البحث في الويب...")
                        user_states[sid] = {"step": "locked_processing"} # إغلاق الحالة
                        
                        ans, err = ask_copilot(text, web_search=True)
                        send_fb_message(sid, ans if ans else f"❌ {err}")
                        
                        if user_states.get(sid, {}).get("step") == "locked_processing":
                            del user_states[sid]
                        
                    elif step == "image_upload":
                        if attachments:
                            state.update({"step": "image_prompt", "data": {"url": attachments[0]['payload']['url']}})
                            user_states[sid] = state; send_fb_message(sid, "✍️ أدخل طلبك للصورة (أو أرسل رقم 1 للتحليل العادي)")
                            
                    elif step == "image_prompt":
                        send_fb_message(sid, "👁️ جاري المعالجة...")
                        p = "تحليل الصورة" if text == "1" else text
                        img_url = state["data"]["url"]
                        user_states[sid] = {"step": "locked_processing"} # إغلاق الحالة
                        
                        cat, _ = upload_to_catbox(img_url)
                        ans, _ = ask_copilot(p, image_url=cat)
                        send_fb_message(sid, ans)
                        
                        if user_states.get(sid, {}).get("step") == "locked_processing":
                            del user_states[sid]

                    # 🛡️ تجاهل أي رسائل تأتي والمستخدم في حالة معالجة طويلة
                    elif step == "locked_processing":
                        continue
                        
                    elif step == "admin_action":
                        if text == "3": # فك الحظر عن الجميع
                            banned_users.clear(); cloud_data['banned_users_dict'] = banned_users; save_cloud_data(cloud_data)
                            send_fb_message(sid, "✅ تم فك الحظر عن جميع المستخدمين."); del user_states[sid]
                        elif text == "4": # حظر الجميع
                            for u in all_users: 
                                if u != sid: banned_users[u] = "حظر جماعي"
                            cloud_data['banned_users_dict'] = banned_users; save_cloud_data(cloud_data)
                            send_fb_message(sid, "🚫 تم حظر جميع المستخدمين."); del user_states[sid]
                        elif text in ["1", "2"]:
                            state.update({"step": "admin_target", "data": {**state["data"], "act": text}})
                            user_states[sid] = state
                            send_fb_message(sid, "✍️ أدخل **رقم المستخدم** من اللائحة أعلاه (مثال: 1, 2, 3...):")
                        else:
                            send_fb_message(sid, "❌ اختر رقماً صحيحاً من 1 إلى 4.")
                            
                    elif step == "admin_target":
                        target_id = state["data"]["map"].get(text)
                        if not target_id:
                            send_fb_message(sid, "❌ رقم غير موجود في اللائحة. تم إلغاء الأمر."); del user_states[sid]; continue
                            
                        if state["data"]["act"] == "1":
                            if target_id in banned_users:
                                del banned_users[target_id]; cloud_data['banned_users_dict'] = banned_users; save_cloud_data(cloud_data)
                                send_fb_message(sid, f"✅ تم فك الحظر عن المستخدم رقم {text}.")
                            else: send_fb_message(sid, "❌ هذا المستخدم ليس محظوراً.")
                        elif state["data"]["act"] == "2":
                            if target_id == sid: send_fb_message(sid, "❌ لا يمكنك حظر نفسك يا مدير!")
                            else:
                                banned_users[target_id] = "حظر يدوي"
                                cloud_data['banned_users_dict'] = banned_users; save_cloud_data(cloud_data)
                                send_fb_message(sid, f"🚫 تم حظر المستخدم رقم {text}.")
                        del user_states[sid]
                    continue

                if text == "brosys123": user_states[sid] = {"step": "broadcast_wait"}; send_fb_message(sid, "📢 رسالة البث؟")
                elif text == ".menu": send_menu(sid)
                elif text.startswith(".web"):
                    q = text.replace(".web", "").strip()
                    if q: 
                        ans, _ = ask_copilot(q, web_search=True); send_fb_message(sid, ans)
                    else: user_states[sid] = {"step": "web_query"}; send_fb_message(sid, "ماذا تريد أن تبحث عنه؟")
                elif text.startswith(".gen"):
                    p = text.replace(".gen", "").strip() or "صورة إبداعية عشوائية"
                    user_states[sid] = {"step": "gen_style", "data": {"prompt": p}}
                    # 👈 رسالة الستايلات منظمة ومفصلة
                    style_msg = "🎨 **أدخل رقم الستايل الذي تريده:**\n\n1- الواقعية (Default)\n2- فن غيبلي (Ghibli)\n3- سايبربانك (Cyberpunk)\n4- أنمي (Anime)\n5- بورتريه (Portrait)\n6- تشيبي (Chibi)\n7- فن البكسل (Pixel)\n8- الرسم الزيتي (Oil)\n9- ثلاثي الأبعاد (3D)"
                    send_fb_message(sid, style_msg)
                elif text == ".image": user_states[sid] = {"step": "image_upload"}; send_fb_message(sid, "📸 أرسل الصورة التي تريد تحليلها:")
                
                # 👈 أمر الإدارة الجديد .infos22 مع الترقيم الذكي
                elif text == ".infos22":
                    mapping = {}
                    infos_msg = "📊 **قائمة المستخدمين:**\n\n"
                    for i, uid in enumerate(all_users, 1):
                        mapping[str(i)] = uid
                        status = "🚫 محظور (مخالفة)" if uid in banned_users else "✅ نشط" # تم إخفاء الكلمة النابية
                        infos_msg += f"{i}- ID: {uid} | {status}\n"
                        
                    send_fb_message(sid, infos_msg[:2000]) 
                    user_states[sid] = {"step": "admin_action", "data": {"map": mapping}}
                    admin_menu = "⚙️ **اختر الإجراء:**\n\n1- رفع الحظر عن مستخدم معين\n2- حظر مستخدم معين\n3- رفع الحظر عن الجميع\n4- حظر الجميع دفعة واحدة"
                    send_fb_message(sid, admin_menu)
                
                elif text:
                    # 👈 تم تعديل تخزين سبب الحظر لكي لا يظهر في اللائحة، بل يُخزن داخلياً فقط لحمايتك
                    if is_message_inappropriate(text):
                        banned_users[sid] = "استخدام كلام نابي" 
                        cloud_data['banned_users_dict'] = banned_users
                        save_cloud_data(cloud_data); send_fb_message(sid, "🚫 تم حظرك بسبب الكلام النابي."); continue
                    ans, _ = ask_copilot(text); send_fb_message(sid, ans)

    return "OK", 200

def send_menu(sid):
    # 👈 تم تنظيم قائمة المساعدة لتصبح احترافية ومفهومة
    menu = (
        "📜 **دليل استخدام البوت:**\n\n"
        "🌐 `.web` : للبحث في الويب (مثال: `.web أخبار اليوم` أو اكتب الأمر وحده وسأسألك).\n\n"
        "🎨 `.gen` : لإنشاء صور بالذكاء الاصطناعي (مثال: `.gen قطة تلعب` وسأطلب منك اختيار الستايل والبعد).\n\n"
        "📸 `.image` : أرسل هذا الأمر وسأطلب منك الصورة لتحليلها أو استخراج النص منها.\n\n"
        "ℹ️ `.menu` : لعرض هذه القائمة مرة أخرى.\n\n"
        "💬 **بدون أوامر:** أي رسالة عادية ترسلها سأرد عليها كدردشة طبيعية."
    )
    send_fb_message(sid, menu)

def send_fb_message(rid, txt):
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json={"recipient": {"id": rid}, "message": {"text": txt}})

def send_fb_image(rid, url):
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json={"recipient": {"id": rid}, "message": {"attachment": {"type": "image", "payload": {"url": url}}}})

if __name__ == '__main__':
    app.run()
