import os
import time
import random
import requests
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# ⚙️ 1. Configuration & Global States
# ==========================================
PAGE_ACCESS_TOKEN = "EAAg9vun0ll4BRHDCZCuLWuZBGJ4wupUj5O4x8nZAaI51XCnXZCETTazN7JXVrZA7HJhHWxjNSkg8lvZAw2NswmibEShdeshrZByzkYcZAczM41XR4ZA2O9ib5DjUtqvOTKZBrkL2JBcDrvRVYCMMTz0wVgSxn4Dm6kQxnR88BiqCr9J2CeMV4370APs3ikoBZA3nVGMrA9kEAZDZD"
VERIFY_TOKEN = "ismail dev"
FB_API_URL = "https://graph.facebook.com/v19.0/me/messages"

ADMIN_ID = "25630836599928130" 

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
    default_data = {"banned_users_dict": {}, "active_unban_codes": [], "all_users": [], "users_profiles": {}}
    if not JSONBIN_URL: return default_data
    try:
        res = requests.get(JSONBIN_URL, headers={"X-Master-Key": JSONBIN_API_KEY})
        if res.status_code == 200:
            data = res.json()['record']
            if "all_users" not in data: data["all_users"] = []
            if "banned_users_dict" not in data: data["banned_users_dict"] = {}
            if "users_profiles" not in data: data["users_profiles"] = {}
            return data
    except: pass
    return default_data

def save_cloud_data(data):
    if not JSONBIN_URL: return
    requests.put(JSONBIN_URL, json=data, headers={"Content-Type": "application/json", "X-Master-Key": JSONBIN_API_KEY})

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
def ask_copilot(user_message, image_url=None, web_search=False):
    system = ""
    if not web_search: system += ""
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

                # إضافة مستخدم جديد
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

                # ==========================================
                # 💸 نظام الرصيد والاشتراكات
                # ==========================================
                if sid not in profiles:
                    profiles[sid] = {"msgs": 20, "reset_time": time.time(), "sub_end": 0}
                    db_changed = True

                user_profile = profiles[sid]
                current_time = time.time()

                # إعادة العداد بعد 24 ساعة
                if current_time - user_profile["reset_time"] >= 86400:
                    user_profile["msgs"] = 20
                    user_profile["reset_time"] = current_time
                    db_changed = True

                is_admin = (sid == ADMIN_ID)
                is_subbed = (user_profile["sub_end"] > current_time)

                # صمام الأمان (منع الرسائل إذا انتهى الرصيد)
                if not is_admin and not is_subbed and text != ".myid" and not text.startswith(".subs123"):
                    if user_profile["msgs"] <= 0:
                        limit_msg = (
                            "🚫 **عفواً!** لقد وصلت إلى الحد اليومي المسموح به من الرسائل في التجربة المجانية للبوت.\n\n"
                            "⏳ يرجى العودة بعد 24 ساعة للحصول على رصيد رسائل جديد لتكملة محادثتنا.\n\n"
                            "👑 **تريد التحدث بدون حدود؟**\n"
                            "تواصل مع المطور مباشرة لترقية حسابك:\n"
                            "🔗 https://www.facebook.com/M.oulay.I.smail.B.drk\n\n"
                            "💎 **باقات الإشتراك المميزة (VIP):**\n"
                            "🪙 1 دولار / للأسبوع\n"
                            "💰 3 دولار / للشهر"
                        )
                        send_fb_message(sid, limit_msg)
                        continue # يمنع البوت من تنفيذ أي كود أسفل هذا السطر
                    else:
                        user_profile["msgs"] -= 1
                        db_changed = True

                # ==========================================
                # 🧠 معالجة الحالات والأوامر
                # ==========================================
                state = user_states.get(sid, {})
                step = state.get("step")

                if step:
                    if step == "broadcast_wait":
                        for uid in all_users:
                            if uid != sid: send_fb_message(uid, text); time.sleep(0.3)
                        send_fb_message(sid, "✅ تم البث.")
                        del user_states[sid]
                        
                    elif step == "admin_subs_id":
                        target_id = text.strip()
                        state.update({"step": "admin_subs_type", "data": {"target_id": target_id}})
                        user_states[sid] = state
                        send_fb_message(sid, "أدخل نوع الاشتراك الذي تريد تطبيقه للمستخدم :\n1- باقة أسبوعية\n2- باقة شهرية")
                        
                    elif step == "admin_subs_type":
                        target_id = state["data"]["target_id"]
                        if target_id not in profiles:
                            profiles[target_id] = {"msgs": 20, "reset_time": time.time(), "sub_end": 0}
                            
                        if text == "1":
                            profiles[target_id]["sub_end"] = time.time() + (7 * 86400) # 7 أيام بالثواني
                            pack_name = "الباقة الأسبوعية"
                        elif text == "2":
                            profiles[target_id]["sub_end"] = time.time() + (30 * 86400) # 30 يوم بالثواني
                            pack_name = "الباقة الشهرية"
                        else:
                            send_fb_message(sid, "❌ خيار غير صحيح. تم الإلغاء.")
                            del user_states[sid]
                            continue
                            
                        db_changed = True
                        send_fb_message(sid, f"✅ تم تفعيل {pack_name} للمستخدم {target_id} بنجاح.")
                        send_fb_message(target_id, f"🎉 **مبارك!**\nتم تفعيل {pack_name} (VIP) في حسابك بنجاح.\nيمكنك الآن استخدام البوت بدون أي حدود! 🚀")
                        del user_states[sid]

                    elif step == "gen_style":
                        if text in STYLES:
                            state.update({"step": "gen_size", "data": {**state["data"], "style": STYLES[text]}})
                            user_states[sid] = state
                            send_fb_message(sid, "📐 **أدخل رقم البعد الذي تريده:**\n\n1- مربع (1:1)\n2- أفقي (3:2)\n3- عمودي (2:3)")
                        else: send_fb_message(sid, "❌ الرجاء اختيار رقم صحيح من 1 إلى 9.")
                        
                    elif step == "gen_size":
                        if text in SIZES:
                            send_fb_message(sid, "🎨 جاري الإنشاء... (قد يستغرق الأمر دقيقة)")
                            url, err = generate_image_sync(state["data"]["prompt"], state["data"]["style"], SIZES[text])
                            if url: send_fb_image(sid, url)
                            else: send_fb_message(sid, f"❌ خطأ: {err}")
                            del user_states[sid]
                        else: send_fb_message(sid, "❌ الرجاء اختيار رقم صحيح من 1 إلى 3.")
                        
                    elif step == "web_query":
                        send_fb_message(sid, "🔍 جاري البحث في الويب...")
                        ans, err = ask_copilot(text, web_search=True)
                        send_fb_message(sid, ans if ans else f"❌ {err}")
                        del user_states[sid]
                        
                    # تم تعطيل خطوات رفع وتحليل الصورة
                    # elif step == "image_upload": ...
                    # elif step == "image_prompt": ...

                    elif step == "locked_processing":
                        continue
                        
                    elif step == "admin_action":
                        if text == "3": 
                            banned_users.clear()
                            cloud_data['banned_users_dict'] = banned_users
                            db_changed = True
                            send_fb_message(sid, "✅ تم فك الحظر عن جميع المستخدمين.")
                            del user_states[sid]
                        elif text == "4": 
                            for u in all_users: 
                                if u != sid: banned_users[u] = "حظر جماعي"
                            cloud_data['banned_users_dict'] = banned_users
                            db_changed = True
                            send_fb_message(sid, "🚫 تم حظر جميع المستخدمين.")
                            del user_states[sid]
                        elif text in ["1", "2"]:
                            state.update({"step": "admin_target", "data": {**state["data"], "act": text}})
                            user_states[sid] = state
                            send_fb_message(sid, "✍️ أدخل **رقم المستخدم** من اللائحة أعلاه (مثال: 1, 2, 3...):")
                        else:
                            send_fb_message(sid, "❌ اختر رقماً صحيحاً من 1 إلى 4.")
                            
                    elif step == "admin_target":
                        target_id = state["data"]["map"].get(text)
                        if not target_id:
                            send_fb_message(sid, "❌ رقم غير موجود في اللائحة. تم إلغاء الأمر.")
                            del user_states[sid]; continue
                            
                        if state["data"]["act"] == "1":
                            if target_id in banned_users:
                                del banned_users[target_id]
                                cloud_data['banned_users_dict'] = banned_users
                                db_changed = True
                                send_fb_message(sid, f"✅ تم فك الحظر عن المستخدم رقم {text}.")
                            else: send_fb_message(sid, "❌ هذا المستخدم ليس محظوراً.")
                        elif state["data"]["act"] == "2":
                            if target_id == sid: send_fb_message(sid, "❌ لا يمكنك حظر نفسك يا مدير!")
                            else:
                                banned_users[target_id] = "حظر يدوي"
                                cloud_data['banned_users_dict'] = banned_users
                                db_changed = True
                                send_fb_message(sid, f"🚫 تم حظر المستخدم رقم {text}.")
                        del user_states[sid]
                    continue

                # ==========================================
                # 🛠️ توجيه الأوامر المباشرة
                # ==========================================
                if text == "brosys123": 
                    user_states[sid] = {"step": "broadcast_wait"}; send_fb_message(sid, "📢 رسالة البث؟")
                
                elif text == ".subs123":
                    if is_admin:
                        user_states[sid] = {"step": "admin_subs_id"}
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
                    status_msg = f"📊 **تقرير حالة النظام:**\n\n👥 إجمالي المستخدمين: {total}\n✅ النشطين: {total - banned}\n🚫 المحظورين: {banned}\n\n⚡ **حالة الخوادم:**\n🟢 خادم النظام (Vercel): مستقر\n🟢 خادم الذكاء الاصطناعي: متصل"
                    send_fb_message(sid, status_msg)

                elif text.startswith(".web"):
                    q = text.replace(".web", "").strip()
                    if q: 
                        ans, _ = ask_copilot(q, web_search=True)
                        send_fb_message(sid, ans)
                    else: 
                        user_states[sid] = {"step": "web_query"}
                        send_fb_message(sid, "ماذا تريد أن تبحث عنه؟")
                        
                elif text.startswith(".gen"):
                    p = text.replace(".gen", "").strip() or "صورة إبداعية عشوائية"
                    user_states[sid] = {"step": "gen_style", "data": {"prompt": p}}
                    send_fb_message(sid, "🎨 **أدخل رقم الستايل الذي تريده:**\n\n1- الواقعية (Default)\n2- فن غيبلي (Ghibli)\n3- سايبربانك (Cyberpunk)\n4- أنمي (Anime)\n5- بورتريه (Portrait)\n6- تشيبي (Chibi)\n7- فن البكسل (Pixel)\n8- الرسم الزيتي (Oil)\n9- ثلاثي الأبعاد (3D)")
                    
                # 🛑 الرسالة التنبيهية عند استخدام أمر .image
                elif text == ".image": 
                    maintenance_msg = "🛠️ **عذراً! ميزة تحليل الصور قيد التحديث والإصلاح حالياً.**\n\nنحن نعمل على تطويرها لتصبح أسرع وأكثر دقة. يرجى المحاولة لاحقاً، شكراً لتفهمكم! 🙏"
                    send_fb_message(sid, maintenance_msg)
                
                elif text == ".infos22":
                    mapping = {}
                    infos_msg = "📊 **قائمة المستخدمين:**\n\n"
                    for i, uid in enumerate(all_users, 1):
                        mapping[str(i)] = uid
                        status = "🚫 محظور" if uid in banned_users else "✅ نشط" 
                        infos_msg += f"{i}- ID: {uid} | {status}\n"
                    send_fb_message(sid, infos_msg[:2000]) 
                    user_states[sid] = {"step": "admin_action", "data": {"map": mapping}}
                    send_fb_message(sid, "⚙️ **اختر الإجراء:**\n\n1- رفع الحظر\n2- حظر\n3- رفع الحظر عن الجميع\n4- حظر الجميع")
                
                # منع إرسال الأوامر الوهمية (التي تبدأ بنقطة) للذكاء الاصطناعي
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
