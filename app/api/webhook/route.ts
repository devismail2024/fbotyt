import { NextResponse } from 'next/server';
import axios from 'axios';
import * as admin from 'firebase-admin';

// ==========================================
// ⚙️ 1. Configuration & Global States
// ==========================================
const PAGE_ACCESS_TOKEN = "EAAg9vun0ll4BRHDCZCuLWuZBGJ4wupUj5O4x8nZAaI51XCnXZCETTazN7JXVrZA7HJhHWxjNSkg8lvZAw2NswmibEShdeshrZByzkYcZAczM41XR4ZA2O9ib5DjUtqvOTKZBrkL2JBcDrvRVYCMMTz0wVgSxn4Dm6kQxnR88BiqCr9J2CeMV4370APs3ikoBZA3nVGMrA9kEAZDZD";
const VERIFY_TOKEN = "ismail dev";
const FB_API_URL = "https://graph.facebook.com/v19.0/me/messages";

const TEXT_API = "https://obito-mr-apis-2.vercel.app/api/ai/copilot";
const IMAGE_GEN_API = "https://obito-mr-apis.vercel.app/api/ai/deepImg";

const STYLES: Record<string, string> = { "1": "default", "2": "ghibli", "3": "cyberpunk", "4": "anime", "5": "portrait", "6": "chibi", "7": "pixel", "8": "oil", "9": "3d" };
const SIZES: Record<string, string> = { "1": "1:1", "2": "3:2", "3": "2:3" };

// ==========================================
// 🔥 2. Firebase Initialization
// ==========================================
if (!admin.apps.length) {
    try {
        const firebaseCredsJson = process.env.FIREBASE_CREDENTIALS;
        if (firebaseCredsJson) {
            const credDict = JSON.parse(firebaseCredsJson);
            admin.initializeApp({
                credential: admin.credential.cert(credDict),
                databaseURL: process.env.FIREBASE_DB_URL || 'https://your-project-id.firebaseio.com/'
            });
            console.log("Firebase initialized successfully in Next.js!");
        }
    } catch (e) {
        console.error("Failed to initialize Firebase:", e);
    }
}

const db = admin.database();

// ==========================================
// 🧠 3. API Engines & Detective Engine
// ==========================================
async function askCopilot(userMessage: string, imageUrl?: string, webSearch = false) {
    try {
        const res = await axios.get(TEXT_API, {
            params: { text: userMessage, imageUrl: imageUrl },
            timeout: 30000
        });
        return res.data?.answer || "عذرا، وقع خطأ.";
    } catch (e: any) {
        console.error("Copilot Error:", e.message);
        return "❌ عذرا، حدث خطأ في الاتصال بالذكاء الاصطناعي.";
    }
}

async function generateImageSync(prompt: string, style: string, size: string) {
    try {
        const res = await axios.get(IMAGE_GEN_API, {
            params: { txt: prompt, style: style, size: size },
            timeout: 45000
        });
        if (res.status === 200 && res.data?.data?.image_url) {
            return res.data.data.image_url; 
        }
        return null;
    } catch (e: any) {
        console.error("Image Gen Error:", e.message);
        return null;
    }
}

// 🛑 عودة المحقق الصارم (الـ Detective Engine)
async function isMessageInappropriate(text: string): Promise<boolean> {
    const cleanText = text.toLowerCase().trim();
    const techKeywords = ["menu", "info", "gen", "web", "image", "status", "ping", "myid"];
    
    if (cleanText.startsWith(".") || techKeywords.includes(cleanText) || cleanText.length <= 2 || !isNaN(Number(cleanText))) {
        return false;
    }
    
    const instruction = `أجب بـ YES فقط إذا كان هذا النص سب أو قذف صريح، وأجب بـ NO إذا كان كلام عادي أو مصطلح تقني. النص: '${cleanText}'`;
    try {
        const res = await axios.get(TEXT_API, { params: { text: instruction }, timeout: 8000 });
        if (res.status === 200) {
            const answer = (res.data?.answer || "").toUpperCase();
            if (answer.includes("YES") && answer.length < 6) return true;
        }
    } catch (e) {
        // في حال فشل الاتصال، نفترض أن النص سليم حتى لا نوقف البوت
    }
    return false;
}

// ==========================================
// 💬 4. Facebook Helpers
// ==========================================
async function sendFbMessage(rid: string, txt: string) {
    try {
        await axios.post(`${FB_API_URL}?access_token=${PAGE_ACCESS_TOKEN}`, {
            recipient: { id: rid },
            message: { text: txt }
        });
    } catch (e) {
        console.error("FB Send Error");
    }
}

async function sendFbImage(rid: string, url: string) {
    try {
        await axios.post(`${FB_API_URL}?access_token=${PAGE_ACCESS_TOKEN}`, {
            recipient: { id: rid },
            message: { attachment: { type: "image", payload: { url: url } } }
        });
    } catch (e) {
        console.error("FB Image Send Error");
    }
}

function sendMenu(sid: string) {
    const menu = "📜 **دليل استخدام البوت:**\n\n🌐 `.web` : للبحث في الويب.\n🎨 `.gen` : لإنشاء صور.\n📸 `.image` : لتحليل الصور.\n🆔 `.myid` : لمعرفة معرفك ورصيدك.\n🏓 `.ping` : لاختبار السيرفر.\nℹ️ `.menu` : لعرض هذه القائمة.";
    sendFbMessage(sid, menu);
}

// ==========================================
// 🌐 5. Next.js Route Handlers
// ==========================================
export async function GET(req: Request) {
    const { searchParams } = new URL(req.url);
    const mode = searchParams.get("hub.mode");
    const token = searchParams.get("hub.verify_token");
    const challenge = searchParams.get("hub.challenge");

    if (mode === "subscribe" && token === VERIFY_TOKEN) {
        return new NextResponse(challenge, { status: 200 });
    }
    return new NextResponse("Forbidden", { status: 403 });
}

export async function POST(req: Request) {
    try {
        const data = await req.json();

        if (data.object === 'page') {
            const ref = db.ref('maghrib_ai_bot_data');
            const snapshot = await ref.once('value');
            let cloudData = snapshot.val() || { all_users: [], banned_users_dict: {}, users_profiles: {} };

            let allUsers = new Set(cloudData.all_users || []);
            let bannedUsers = cloudData.banned_users_dict || {};
            let profiles = cloudData.users_profiles || {};
            let dbChanged = false;

            for (const entry of data.entry) {
                for (const event of entry.messaging || []) {
                    const sid = String(event.sender.id);
                    const msg = event.message || {};
                    const text = (msg.text || '').trim();
                    const attachments = msg.attachments || [];
                    const mid = msg.mid;

                    if (!text && attachments.length === 0) continue;

                    if (!allUsers.has(sid)) {
                        allUsers.add(sid);
                        cloudData.all_users = Array.from(allUsers);
                        dbChanged = true;
                        await sendFbMessage(sid, "👋 أهلاً بك! أنا بوت M Ismail Dev.\nتابعني: https://www.facebook.com/M.oulay.I.smail.B.drk");
                        sendMenu(sid);
                        continue;
                    }

                    if (bannedUsers[sid]) continue;

                    if (!profiles[sid]) {
                        profiles[sid] = { msgs: 20, reset_time: Date.now() / 1000, sub_end: 0, state: {}, last_mid: "" };
                        dbChanged = true;
                    }

                    const userProfile = profiles[sid];
                    if (!userProfile.state) { userProfile.state = {}; dbChanged = true; }
                    if (!userProfile.last_mid) { userProfile.last_mid = ""; dbChanged = true; }

                    if (mid && userProfile.last_mid === mid) continue;
                    if (mid) { userProfile.last_mid = mid; dbChanged = true; }

                    const currentTime = Date.now() / 1000;
                    if (currentTime - userProfile.reset_time >= 86400) {
                        userProfile.msgs = 20;
                        userProfile.reset_time = currentTime;
                        dbChanged = true;
                    }

                    const isSubbed = userProfile.sub_end > currentTime;

                    if (!isSubbed && text !== ".myid") {
                        if (userProfile.msgs <= 0) {
                            await sendFbMessage(sid, "🚫 **عفواً!** لقد وصلت إلى الحد اليومي.\n⏳ يرجى العودة غداً.\n🔗 لترقية الحساب: https://www.facebook.com/M.oulay.I.smail.B.drk");
                            continue;
                        } else {
                            userProfile.msgs -= 1;
                            dbChanged = true;
                        }
                    }

                    const state = userProfile.state || {};
                    const step = state.step;

                    if (step) {
                        if (step === "gen_style") {
                            if (STYLES[text]) {
                                userProfile.state = { step: "gen_size", data: { ...state.data, style: STYLES[text] } };
                                dbChanged = true;
                                await sendFbMessage(sid, "📐 **أدخل رقم البعد:**\n1- مربع (1:1)\n2- أفقي (3:2)\n3- عمودي (2:3)");
                            } else {
                                await sendFbMessage(sid, "❌ الرجاء اختيار رقم صحيح من 1 إلى 9.");
                            }
                            continue;
                        } 
                        else if (step === "gen_size") {
                            if (SIZES[text]) {
                                await sendFbMessage(sid, "🎨 جاري الإنشاء... (قد يستغرق الأمر دقيقة)");
                                const url = await generateImageSync(state.data.prompt, state.data.style, SIZES[text]);
                                if (url) await sendFbImage(sid, url);
                                else await sendFbMessage(sid, "❌ خطأ في توليد الصورة.");
                                userProfile.state = {}; dbChanged = true;
                            } else {
                                await sendFbMessage(sid, "❌ الرجاء اختيار رقم صحيح.");
                            }
                            continue;
                        }
                        else if (step === "web_query") {
                            await sendFbMessage(sid, "🔍 جاري البحث...");
                            const ans = await askCopilot(text, undefined, true);
                            await sendFbMessage(sid, ans);
                            userProfile.state = {}; dbChanged = true;
                            continue;
                        }
                    }

                    if (text === ".menu") {
                        sendMenu(sid);
                    } 
                    else if (text === ".myid") {
                        const subStatus = isSubbed ? "\n👑 باقتك: VIP نشطة" : `\n💬 رسائلك المتبقية: ${userProfile.msgs}`;
                        await sendFbMessage(sid, `🆔 معرفك (ID):\n${sid}${subStatus}`);
                    } 
                    else if (text === ".ping") {
                        await sendFbMessage(sid, "🏓 Pong!\n✅ البوت يعمل بكفاءة بـ Next.js.");
                    }
                    else if (text.startsWith(".web")) {
                        const q = text.replace(".web", "").trim();
                        if (q) {
                            const ans = await askCopilot(q, undefined, true);
                            await sendFbMessage(sid, ans);
                        } else {
                            userProfile.state = { step: "web_query" }; dbChanged = true;
                            await sendFbMessage(sid, "ماذا تريد أن تبحث عنه؟");
                        }
                    } 
                    else if (text.startsWith(".gen")) {
                        const p = text.replace(".gen", "").trim() || "صورة إبداعية عشوائية";
                        userProfile.state = { step: "gen_style", data: { prompt: p } }; dbChanged = true;
                        await sendFbMessage(sid, "🎨 **اختر الستايل:**\n1- واقعي\n2- غيبلي\n3- سايبربانك\n4- أنمي\n5- بورتريه\n6- تشيبي\n7- بكسل\n8- زيتي\n9- 3D");
                    } 
                    else if (text === ".image") {
                        await sendFbMessage(sid, "🛠️ **عذراً! ميزة تحليل الصور قيد الصيانة حالياً.** يرجى المحاولة لاحقاً.");
                    } 
                    else if (text.startsWith(".")) {
                        await sendFbMessage(sid, "❌ أمر غير معروف. استخدم .menu.");
                    } 
                    else {
                        // 🛑 تفعيل المحقق قبل الرد
                        const isBad = await isMessageInappropriate(text);
                        if (isBad) {
                            bannedUsers[sid] = "كلام نابي";
                            cloudData.banned_users_dict = bannedUsers;
                            dbChanged = true;
                            await sendFbMessage(sid, "🚫 تم حظرك بسبب الكلام النابي.");
                            continue;
                        }
                        const ans = await askCopilot(text);
                        await sendFbMessage(sid, ans);
                    }
                }
            }

            if (dbChanged) {
                cloudData.users_profiles = profiles;
                await ref.set(cloudData);
            }
        }
        return new NextResponse("OK", { status: 200 });
    } catch (error) {
        console.error("Webhook Error:", error);
        return new NextResponse("Error", { status: 500 });
    }
}
