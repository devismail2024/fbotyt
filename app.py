import os
import time
import random
import requests
import json
import base64
import firebase_admin
from firebase_admin import credentials, db
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# ⚙️ 1. Configuration & Global States
# ==========================================
PAGE_ACCESS_TOKEN = "EAAg9vun0ll4BRHDCZCuLWuZBGJ4wupUj5O4x8nZAaI51XCnXZCETTazN7JXVrZA7HJhHWxjNSkg8lvZAw2NswmibEShdeshrZByzkYcZAczM41XR4ZA2O9ib5DjUtqvOTKZBrkL2JBcDrvRVYCMMTz0wVgSxn4Dm6kQxnR88BiqCr9J2CeMV4370APs3ikoBZA3nVGMrA9kEAZDZD"
VERIFY_TOKEN = "ismail dev"
FB_API_URL = "https://graph.facebook.com/v19.0/me/messages"

ADMIN_ID = "25630836599928130" 

TEXT_API = "https://obito-mr-apis-2.vercel.app/api/ai/copilot"
IMAGE_GEN_API = "https://obito-mr-apis.vercel.app/api/ai/deepImg"

STYLES = {"1": "default", "2": "ghibli", "3": "cyberpunk", "4": "anime", "5": "portrait", "6": "chibi", "7": "pixel", "8": "oil", "9": "3d"}
SIZES = {"1": "1:1", "2": "3:2", "3": "2:3"}

# ==========================================
# 🔥 2. Firebase Cloud Storage
# ==========================================
firebase_creds_json = os.environ.get('FIREBASE_CREDENTIALS')

if firebase_creds_json and not firebase_admin._apps:
    try:
        cred_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {
            'databaseURL': os.environ.get('FIREBASE_DB_URL', 'https://your-project-id.firebaseio.com/') 
        })
    except Exception as e:
        print(f"Failed to initialize Firebase: {e}")

def load_cloud_data():
    default_data = {"banned_users_dict": {}, "active_unban_codes": [], "all_users": [], "users_profiles": {}}
    if not firebase_admin._apps: return default_data
    try:
        ref = db.reference('maghrib_ai_bot_data') 
        data = ref.get()
        if data:
            if "all_users" not in data: data["all_users"] = []
            if "banned_users_dict" not in data: data["banned_users_dict"] = {}
            if "users_profiles" not in data: data["users_profiles"] = {}
            if "active_unban_codes" not in data: data["active_unban_codes"] = []
            return data
    except Exception as e: pass
    return default_data

def save_cloud_data(data):
    if not firebase_admin._apps: return
    try:
        ref = db.reference('maghrib_ai_bot_data')
        ref.set(data)
    except Exception as e: pass

# ==========================================
# 🛑 3. Detective Engine
# ==========================================
def is_message_inappropriate(text):
    clean_text = text.lower().strip()
    tech_keywords = ["menu", "info", "gen", "web", "image", "status", "ping", "myid"]
    if clean_text.startswith("."): return False
    if clean_text in tech_keywords: return False 
    if len(clean_text) <= 2 or clean_text.isdigit(): return False 
    
    instruction = f"أجب بـ YES فقط إذا كان هذا النص سب أو قذف صريح، وأجب بـ NO إذا كان كلام عادي أو مصطلح تقني. النص: '{clean_text}'"
    try:
        res = requests.get(TEXT_API, params={"text": instruction}, timeout=8)
        if res.status_code == 200:
            answer = res.json().get("answer", "").upper()
            if "YES" in answer and len(answer) < 6: 
                return True
    except: pass 
    return False

# ==========================================
# 🧠 4. AI & Image Engines
# ==========================================
def image_to_base64(image_url):
    """تحميل الصورة من فيسبوك وتحويلها إلى Base64"""
    try:
        response = requests.get(image_url, timeout=5)
        if response.status_code == 200:
            encoded_string = base64.b64encode(response.content).decode('utf-8')
            # إضافة الترويسة القياسية للـ base64
            return f"data:image/jpeg;base64,{encoded_string}"
        return None
    except Exception:
        return None

def ask_copilot(user_message, image_url=None, web_search=False):
    params = {"text": user_message}
    
    # تحويل الصورة إلى Base64 قبل الإرسال
    if image_url:
        base64_image = image_to_base64(image_url)
        if base64_image:
            params["imageBase64"] = base64_image
            
    try:
        res = requests.get(TEXT_API, params=params, timeout=15)
        return res.json().get("answer", "عذرا، وقع خطأ."), None
    except Exception as e: return None, str(e)

def generate_image_sync(prompt, style, size):
    params = {"txt": prompt, "style": style, "size": size}
    try:
        res = requests.get(IMAGE_GEN_API, params=params, timeout=45)
        if res.status_code == 200:
            raw_url = res.json().get("data", {}).get("image_url")
            # إزالة Catbox لضمان السرعة، وإرسال الرابط مباشرة
            if raw_url:
                return raw_url, None
        return None, f"API Error: {res.status_code}"
    except Exception as e: return None, str(e)

# ==========================================
# 🌐 5. Main Router
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
        profiles = cloud_data.get('users_profiles', {})
        db_changed = False

        for entry in data['entry']:
            for event in entry.get('messaging', []):
                sid = str(event['sender']['id'])
                msg = event.get('message', {})
                text = msg.get('text', '').strip()
                attachments = msg.get('attachments', [])

                if not text and not attachments: continue

                if sid not in all_users:
                    all_users.add(sid)
                    cloud_data['all_users'] = list(all_users)
                    db_changed = True
                    send_fb_message(sid, "👋 أهلاً بك! أنا بوت M Ismail Dev.\nتابعني: https://www.facebook.com/M.oulay.I.smail.B.drk")
                    send_menu(sid)
                    continue

                if text == "unban123":
                    code = str(random.randint(10000, 99999))
                    active_codes.add(code)
                    cloud_data['active_unban_codes'] = list(active_codes)
                    save_cloud_data(cloud_data)
                    send_fb_message(sid, f"🔑 كود فك الحظر: {code}")
                    continue

                if sid in banned_users:
                    if text in active_codes:
                        active_codes.remove(text)
                        del banned_users[sid]
                        cloud_data['active_unban_codes'] = list(active_codes)
                        cloud_data['banned_users_dict'] = banned_users
                        save_cloud_data(cloud_data)
                        send_fb_message(sid, "✅ تم فك الحظر بنجاح!")
                    continue

                if sid not in profiles:
                    profiles[sid] = {"msgs": 20, "reset_time": time.time(), "sub_end": 0, "state": {}}
                    db_changed = True

                user_profile = profiles[sid]
                # التأكد من وجود مفتاح الذاكرة في البروفايل
                if "state" not in user_profile:
                    user_profile["state"] = {}
                    db_changed = True

                current_time = time.time()
                if current_time - user_profile["reset_time"] >= 86400:
                    user_profile["msgs"] = 20
                    user_profile["reset_time"] = current_time
                    db_changed = True

                is_admin = (sid == ADMIN_ID)
                is_subbed = (user_profile["sub_end"] > current_time)

                if not is_admin and not is_subbed and text != ".myid" and not text.startswith(".subs123"):
                    if user_profile["msgs"] <= 0:
                        limit_msg = (
                            "🚫 **عفواً!** لقد وصلت إلى الحد اليومي المسموح به من الرسائل في التجربة المجانية للبوت.\n\n"
                            "⏳ يرجى العودة بعد 24 ساعة للحصول على رصيد رسائل جديد لتكملة محادثتنا."
                        )
                        send_fb_message(sid, limit_msg)
                        continue 
                    else:
                        user_profile["msgs"] -= 1
                        db_changed = True

                # قراءة الذاكرة من فايربيز بدلاً من السيرفر المؤقت
                state = user_profile["state"]
                step = state.get("step")

                if step:
                    if step == "broadcast_wait":
                        for uid in all_users:
                            if uid != sid: send_fb_message(uid, text); time.sleep(0.3)
                        send_fb_message(sid, "✅ تم البث.")
                        user_profile["state"] = {}; db_changed = True
                        
                    elif step == "admin_subs_id":
                        target_id = text.strip()
                        state.update({"step": "admin_subs_type", "data": {"target_id": target_id}})
                        user_profile["state"] = state; db_changed = True
                        send_fb_message(sid, "أدخل نوع الاشتراك الذي تريد تطبيقه للمستخدم :\n1- باقة أسبوعية\n2- باقة شهرية")
                        
                    elif step == "admin_subs_type":
                        target_id = state["data"]["target_id"]
                        if target_id not in profiles:
                            profiles[target_id] = {"msgs": 20, "reset_time": time.time(), "sub_end": 0, "state": {}}
                            
                        if text == "1":
                            profiles[target_id]["sub_end"] = time.time() + (7 * 86400)
                            pack_name = "الباقة الأسبوعية"
                        elif text == "2":
                            profiles[target_id]["sub_end"] = time.time() + (30 * 86400)
                            pack_name = "الباقة الشهرية"
                        else:
                            send_fb_message(sid, "❌ خيار غير صحيح. تم الإلغاء.")
                            user_profile["state"] = {}; db_changed = True
                            continue
                            
                        user_profile["state"] = {}; db_changed = True
                        send_fb_message(sid, f"✅ تم تفعيل {pack_name} للمستخدم {target_id} بنجاح.")
                        send_fb_message(target_id, f"🎉 **مبارك!**\nتم تفعيل {pack_name} (VIP) في حسابك بنجاح.\nيمكنك الآن استخدام البوت بدون أي حدود! 🚀")

                    elif step == "gen_style":
                        if text in STYLES:
                            state.update({"step": "gen_size", "data": {**state["data"], "style": STYLES[text]}})
                            user_profile["state"] = state; db_changed = True
                            send_fb_message(sid, "📐 **أدخل رقم البعد الذي تريده:**\n\n1- مربع (1:1)\n2- أفقي (3:2)\n3- عمودي (2:3)")
                        else: send_fb_message(sid, "❌ الرجاء اختيار رقم صحيح من 1 إلى 9.")
                        
                    elif step == "gen_size":
                        if text in SIZES:
                            send_fb_message(sid, "🎨 جاري الإنشاء... (قد يستغرق الأمر دقيقة)")
                            url, err = generate_image_sync(state["data"]["prompt"], state["data"]["style"], SIZES[text])
                            if url: send_fb_image(sid, url)
                            else: send_fb_message(sid, f"❌ خطأ: {err}")
                            user_profile["state"] = {}; db_changed = True
                        else: send_fb_message(sid, "❌ الرجاء اختيار رقم صحيح من 1 إلى 3.")
                        
                    elif step == "web_query":
                        send_fb_message(sid, "🔍 جاري البحث في الويب...")
                        ans, err = ask_copilot(text, web_search=True)
                        send_fb_message(sid, ans if ans else f"❌ {err}")
                        user_profile["state"] = {}; db_changed = True
                        
                    elif step == "image_upload":
                        if attachments:
                            url = attachments['payload']['url']
                            state.update({"step": "image_prompt", "data": {"url": url}})
                            user_profile["state"] = state; db_changed = True
                            send_fb_message(sid, "✍️ أدخل طلبك للصورة (أو أرسل رقم 1 للتحليل العادي)")
                            
                    elif step == "image_prompt":
                        send_fb_message(sid, "👁️ جاري تحليل الصورة...")
                        p = "حلل هذه الصورة بالتفصيل" if text == "1" or not text else text
                        # تمرير رابط فيسبوك المباشر لتقوم الدالة بتحويله لـ Base64
                        ans, _ = ask_copilot(p, image_url=state["data"]["url"])
                        send_fb_message(sid, ans if ans else "❌ عذرا، حدث خطأ في تحليل الصورة.")
                        user_profile["state"] = {}; db_changed = True

                    elif step == "admin_action":
                        if text == "3": 
                            banned_users.clear()
                            cloud_data['banned_users_dict'] = banned_users
                            user_profile["state"] = {}; db_changed = True
                            send_fb_message(sid, "✅ تم فك الحظر عن جميع المستخدمين.")
                        elif text == "4": 
                            for u in all_users: 
                                if u != sid: banned_users[u] = "حظر جماعي"
                            cloud_data['banned_users_dict'] = banned_users
                            user_profile["state"] = {}; db_changed = True
                            send_fb_message(sid, "🚫 تم حظر جميع المستخدمين.")
                        elif text in ["1", "2"]:
                            state.update({"step": "admin_target", "data": {**state["data"], "act": text}})
                            user_profile["state"] = state; db_changed = True
                            send_fb_message(sid, "✍️ أدخل **رقم المستخدم** من اللائحة أعلاه (مثال: 1, 2, 3...):")
                        else:
                            send_fb_message(sid, "❌ اختر رقماً صحيحاً من 1 إلى 4.")
                            
                    elif step == "admin_target":
                        target_id = state["data"]["map"].get(text)
                        if not target_id:
                            send_fb_message(sid, "❌ رقم غير موجود في اللائحة. تم إلغاء الأمر.")
                            user_profile["state"] = {}; db_changed = True; continue
                            
                        if state["data"]["act"] == "1":
                            if target_id in banned_users:
                                del banned_users[target_id]
                                cloud_data['banned_users_dict'] = banned_users
                                send_fb_message(sid, f"✅ تم فك الحظر عن المستخدم رقم {text}.")
                            else: send_fb_message(sid, "❌ هذا المستخدم ليس محظوراً.")
                        elif state["data"]["act"] == "2":
                            if target_id == sid: send_fb_message(sid, "❌ لا يمكنك حظر نفسك يا مدير!")
                            else:
                                banned_users[target_id] = "حظر يدوي"
                                cloud_data['banned_users_dict'] = banned_users
                                send_fb_message(sid, f"🚫 تم حظر المستخدم رقم {text}.")
                        user_profile["state"] = {}; db_changed = True
                    continue

                if text == "brosys123": 
                    user_profile["state"] = {"step": "broadcast_wait"}; db_changed = True
                    send_fb_message(sid, "📢 رسالة البث؟")
                
                elif text == ".subs123":
                    if is_admin:
                        user_profile["state"] = {"step": "admin_subs_id"}; db_changed = True
                        send_fb_message(sid, "أدخل الID الخاص بالمستخدم :")
                    else:
                        send_fb_message(sid, "❌ أمر غير معروف. استخدم .menu لرؤية الأوامر المتاحة.")

                elif text == ".menu": 
                    send_menu(sid)
                
                elif text == ".myid":
                    sub_status = "\n👑 باقتك الحالية: VIP نشطة" if is_subbed else f"\n💬 رسائلك المتبقية اليوم: {user_profile['msgs']}"
                    if is_admin: sub_status = "\n👑 أنت المدير: صلاحيات غير محدودة"
                    send_fb_message(sid, f"🆔 معرفك الخاص (ID) هو:\n{sid}{sub_status}")

                elif text == ".ping":
                    send_fb_message(sid, "🏓 Pong!\n✅ البوت يعمل والسيرفرات تستجيب بكفاءة عالية.")

                elif text == ".status":
                    total = len(all_users)
                    banned = len(banned_users)
                    status_msg = f"📊 **تقرير حالة النظام:**\n\n👥 إجمالي المستخدمين: {total}\n✅ النشطين: {total - banned}\n🚫 المحظورين: {banned}\n\n⚡ **حالة الخوادم:**\n🟢 خادم النظام (Vercel): مستقر\n🟢 خادم الذكاء الاصطناعي: متصل\n🟢 قاعدة البيانات (Firebase): متصل"
                    send_fb_message(sid, status_msg)

                elif text.startswith(".web"):
                    q = text.replace(".web", "").strip()
                    if q: 
                        ans, _ = ask_copilot(q, web_search=True)
                        send_fb_message(sid, ans)
                    else: 
                        user_profile["state"] = {"step": "web_query"}; db_changed = True
                        send_fb_message(sid, "ماذا تريد أن تبحث عنه؟")
                        
                elif text.startswith(".gen"):
                    p = text.replace(".gen", "").strip() or "صورة إبداعية عشوائية"
                    user_profile["state"] = {"step": "gen_style", "data": {"prompt": p}}; db_changed = True
                    send_fb_message(sid, "🎨 **أدخل رقم الستايل الذي تريده:**\n\n1- الواقعية (Default)\n2- فن غيبلي (Ghibli)\n3- سايبربانك (Cyberpunk)\n4- أنمي (Anime)\n5- بورتريه (Portrait)\n6- تشيبي (Chibi)\n7- فن البكسل (Pixel)\n8- الرسم الزيتي (Oil)\n9- ثلاثي الأبعاد (3D)")
                    
                elif text == ".image": 
                    user_profile["state"] = {"step": "image_upload"}; db_changed = True
                    send_fb_message(sid, "📸 أرسل الصورة التي تريد تحليلها:")
                
                elif text == ".infos22":
                    mapping = {}
                    infos_msg = "📊 **قائمة المستخدمين:**\n\n"
                    for i, uid in enumerate(all_users, 1):
                        mapping[str(i)] = uid
                        status = "🚫 محظور" if uid in banned_users else "✅ نشط" 
                        infos_msg += f"{i}- ID: {uid} | {status}\n"
                    send_fb_message(sid, infos_msg[:2000]) 
                    user_profile["state"] = {"step": "admin_action", "data": {"map": mapping}}; db_changed = True
                    send_fb_message(sid, "⚙️ **اختر الإجراء:**\n\n1- رفع الحظر\n2- حظر\n3- رفع الحظر عن الجميع\n4- حظر الجميع")
                
                elif text.startswith("."):
                    send_fb_message(sid, "❌ أمر غير معروف. استخدم .menu لرؤية الأوامر المتاحة.")

                elif text:
                    if is_message_inappropriate(text):
                        banned_users[sid] = "استخدام كلام نابي" 
                        cloud_data['banned_users_dict'] = banned_users
                        db_changed = True
                        send_fb_message(sid, "🚫 تم حظرك بسبب الكلام النابي.")
                        continue
                    
                    ans, _ = ask_copilot(text)
                    send_fb_message(sid, ans)

        if db_changed:
            cloud_data['all_users'] = list(all_users)
            cloud_data['banned_users_dict'] = banned_users
            cloud_data['active_unban_codes'] = list(active_codes)
            cloud_data['users_profiles'] = profiles
            save_cloud_data(cloud_data)

    return "OK", 200

def send_menu(sid):
    menu = "📜 **دليل استخدام البوت:**\n\n🌐 `.web` : للبحث في الويب.\n🎨 `.gen` : لإنشاء صور.\n📸 `.image` : لتحليل الصور.\n🆔 `.myid` : لمعرفة معرفك ورصيدك.\n🏓 `.ping` : لاختبار السيرفر.\n📊 `.status` : لعرض إحصائيات النظام.\nℹ️ `.menu` : لعرض هذه القائمة."
    send_fb_message(sid, menu)

def send_fb_message(rid, txt):
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json={"recipient": {"id": rid}, "message": {"text": txt}})

def send_fb_image(rid, url):
    requests.post(f"{FB_API_URL}?access_token={PAGE_ACCESS_TOKEN}", json={"recipient": {"id": rid}, "message": {"attachment": {"type": "image", "payload": {"url": url}}}})

if __name__ == '__main__':
    app.run()
