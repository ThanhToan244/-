import asyncio
import json
import hashlib
import urllib.parse
import base64
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import requests
import urllib3

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import MajoRLogin_pb2 as mLpB
    import MajorLoginRes_pb2 as mLrPb
except ImportError:
    print("Lỗi: thiếu file protobuf.")
    exit()

# ========== MÃ HÓA ==========
AeSkEy = b'Yg&tc%DEuh6%Zc^8'
AeSiV  = b'6oyZDr22E3ychjM%'

def enc(d):
    return AES.new(AeSkEy, AES.MODE_CBC, AeSiV).encrypt(pad(d, 16))

def dec(d):
    return unpad(AES.new(AeSkEy, AES.MODE_CBC, AeSiV).decrypt(d), 16)

PLATFORM_MAP = {
    1: "Garena", 3: "Facebook", 4: "Guest", 5: "VK",
    6: "Huawei", 7: "Apple", 8: "Google", 10: "GameCenter / Line",
    11: "X (Twitter)", 13: "Apple ID", 28: "Line", 35: "TikTok"
}

def convert_seconds(s):
    d, h = divmod(s, 86400)
    h, m = divmod(h, 3600)
    m, s = divmod(m, 60)
    return f"{d} Day {h} Hour {m} Min {s} Sec"

# ----- THÔNG TIN PLAYER & BIND -----
def get_player_info(access_token):
    try:
        player_url = f"https://api-otrss.garena.com/support/callback/?access_token={access_token}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
        p_res = requests.get(player_url, headers=headers, timeout=15, allow_redirects=True)
        parsed_url = urllib.parse.urlparse(p_res.url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        uid = query_params.get("account_id", ["Unknown"])[0]
        nickname = query_params.get("nickname", ["Unknown"])[0]
        region = query_params.get("region", ["Unknown"])[0]
        return {"uid": uid, "nickname": nickname, "region": region}
    except:
        return None

def get_bind_info_text(access_token):
    player = get_player_info(access_token)
    output = ""
    if player:
        output += f"👤 Player Information\n"
        output += f"   • UID      : {player['uid']}\n"
        output += f"   • Nickname : {player['nickname']}\n"
        output += f"   • Region   : {player['region']}\n\n"
    else:
        output += "⚠️ Không thể lấy thông tin player.\n\n"

    url = "https://100067.connect.garena.com/game/account_security/bind:get_bind_info"
    payload = {'app_id': "100067", 'access_token': access_token}
    headers = {'User-Agent': "GarenaMSDK/4.0.19P9(Redmi Note 5 ;Android 9;en;US;)"}
    try:
        response = requests.get(url, params=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            email = data.get("email", "")
            email_to_be = data.get("email_to_be", "")
            countdown = data.get("request_exec_countdown", 0)
            result_code = data.get("result", -1)

            output += "🔐 Bind Information\n"
            output += f"   • Current Email  : {email if email else 'None'}\n"
            output += f"   • Pending Email  : {email_to_be if email_to_be else 'None'}\n"
            if email_to_be:
                output += f"   • Countdown      : {convert_seconds(countdown)}\n"
            if result_code == 0:
                output += "   • Result         : ✅ SUCCESS\n"
            else:
                output += f"   • Result         : ❌ FAILED (Code: {result_code})\n"

            summary = ""
            if email == "" and email_to_be != "":
                summary = f"Pending email confirmation: {email_to_be} - Confirms in: {convert_seconds(countdown)}"
            elif email != "" and email_to_be == "":
                summary = f"Email confirmed: {email}"
            elif email == "" and email_to_be == "":
                summary = "No recovery email set"
            if summary:
                output += f"\n📌 Summary: {summary}\n"
        else:
            output += f"❌ API Error (Status {response.status_code})\n"
    except Exception as e:
        output += f"❌ Lỗi: {str(e)}\n"
    return output
    # ----- CÁC HÀM GỌI API -----
def send_otp(access_token, email):
    url = "https://100067.connect.garena.com/game/account_security/bind:send_otp"
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"email": email, "locale": "en_PK", "region": "PK", "app_id": "100067", "access_token": access_token}
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=10)
        return resp.json() if resp.status_code == 200 else {"result": -1, "error": resp.text}
    except:
        return {"result": -1, "error": "Request failed"}

def verify_otp(access_token, email, otp):
    url = "https://100067.connect.garena.com/game/account_security/bind:verify_otp"
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"app_id": "100067", "access_token": access_token, "email": email, "code": otp, "otp": otp, "type": "1"}
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=10)
        return resp.json() if resp.status_code == 200 else {"result": -1, "error": resp.text}
    except:
        return {"result": -1, "error": "Request failed"}

def verify_identity_otp(access_token, email, otp):
    url = "https://100067.connect.garena.com/game/account_security/bind:verify_identity"
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"email": email, "app_id": "100067", "access_token": access_token, "otp": otp}
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=10)
        return resp.json() if resp.status_code == 200 else {"result": -1, "error": resp.text}
    except:
        return {"result": -1, "error": "Request failed"}

def verify_identity_sec(access_token, email, sec_code):
    url = "https://100067.connect.garena.com/game/account_security/bind:verify_identity"
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    hashed = hashlib.sha256(sec_code.encode('utf-8')).hexdigest()
    data = {"email": email, "app_id": "100067", "access_token": access_token, "secondary_password": hashed}
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=10)
        return resp.json() if resp.status_code == 200 else {"result": -1, "error": resp.text}
    except:
        return {"result": -1, "error": "Request failed"}

def create_bind_request(access_token, email, verifier_token, security_code):
    url = "https://100067.connect.garena.com/game/account_security/bind:create_bind_request"
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"email": email, "app_id": "100067", "access_token": access_token, "verifier_token": verifier_token, "secondary_password": security_code}
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=10)
        return resp.json() if resp.status_code == 200 else {"result": -1, "error": resp.text}
    except:
        return {"result": -1, "error": "Request failed"}

def create_unbind_request(access_token, identity_token):
    url = "https://100067.connect.garena.com/game/account_security/bind:create_unbind_request"
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"app_id": "100067", "access_token": access_token, "identity_token": identity_token}
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=10)
        return resp.json() if resp.status_code == 200 else {"result": -1, "error": resp.text}
    except:
        return {"result": -1, "error": "Request failed"}

def create_rebind_request(access_token, identity_token, new_email, verifier_token):
    url = "https://100067.connect.garena.com/game/account_security/bind:create_rebind_request"
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"identity_token": identity_token, "email": new_email, "app_id": "100067", "verifier_token": verifier_token, "access_token": access_token}
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=10)
        return resp.json() if resp.status_code == 200 else {"result": -1, "error": resp.text}
    except:
        return {"result": -1, "error": "Request failed"}

def cancel_bind_request(access_token):
    url = "https://100067.connect.garena.com/game/account_security/bind:cancel_request"
    headers = {"User-Agent": "GarenaMSDK/4.0.30", "Content-Type": "application/x-www-form-urlencoded"}
    data = {"app_id": "100067", "access_token": access_token}
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=10)
        return resp.json() if resp.status_code == 200 else {"result": -1, "error": resp.text}
    except:
        return {"result": -1, "error": "Request failed"}

def get_current_email(access_token):
    try:
        url = "https://100067.connect.garena.com/game/account_security/bind:get_bind_info"
        payload = {'app_id': "100067", 'access_token': access_token}
        headers = {'User-Agent': "GarenaMSDK/4.0.30"}
        r = requests.get(url, params=payload, headers=headers, timeout=10)
        return r.json().get("email", "") if r.status_code == 200 else ""
    except:
        return ""

def get_platform_binds(access_token):
    url = "https://100067.connect.garena.com/bind/app/platform/info/get"
    params = {"access_token": access_token}
    headers = {"User-Agent": "GarenaMSDK/4.0.19P9(Redmi Note 5 ;Android 9;en;US;)"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            bounded = data.get("bounded_accounts", [])
            available = data.get("available_platforms", [])
            return bounded, available
        else:
            return None, None
    except:
        return None, None
        # ----- LỊCH SỬ ĐĂNG NHẬP -----
def get_login_history(jwt_token):
    output = ""
    try:
        payload_b64 = jwt_token.split('.')[1]
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload_b64).decode('utf-8'))
        name = urllib.parse.unquote(decoded.get("nickname", "Unknown"))
        uid = decoded.get("account_id", "Unknown")
        region = decoded.get("lock_region", "Unknown")
        p_id = decoded.get("external_type", 0)
        platform = PLATFORM_MAP.get(p_id, f"Unknown ({p_id})")
        output += f"👤 Account: {name} ({uid})\n"
        output += f"   Region: {region}\n"
        output += f"   Platform: {platform}\n\n"
    except:
        output += "⚠️ Không thể giải mã JWT.\n\n"

    headers = {
        "Expect": "100-continue",
        "Authorization": f"Bearer {jwt_token}",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB52",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; G011A Build/PI)",
        "Host": "client.ind.freefiremobile.com",
        "Connection": "close"
    }
    try:
        r = requests.post("https://client.ind.freefiremobile.com/GetLoginHistory", headers=headers, data=enc(b""), timeout=15, verify=False)
        if r.status_code != 200:
            return output + "❌ Lỗi khi lấy lịch sử (HTTP {})\n".format(r.status_code)
        try:
            d = dec(r.content)
        except:
            d = r.content
        records = parse_history_protobuf(d)
        if not records:
            output += "📭 Không có lịch sử đăng nhập.\n"
        else:
            for i, rec in enumerate(records, 1):
                ts_raw = rec.get('ts', 0)
                try:
                    date_str = datetime.fromtimestamp(ts_raw).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    date_str = "Invalid Format"
                dev = rec.get('dev', 'Unknown Device')
                arch = rec.get('arch', 'Unknown Architecture')
                ram = rec.get('ram', 0)
                output += f"🔹 Record #{i}\n"
                output += f"   Timestamp : {ts_raw}\n"
                output += f"   Last Login: {date_str}\n"
                output += f"   Device    : {dev}\n"
                output += f"   Arch      : {arch}\n"
                output += f"   RAM       : {ram} MB\n\n"
    except Exception as e:
        output += f"❌ Lỗi kết nối: {str(e)}\n"
    return output

def read_varint(data, offset):
    res = 0; shift = 0
    while True:
        if offset >= len(data): break
        b = data[offset]; offset += 1
        res |= (b & 0x7f) << shift
        if not (b & 0x80): break
        shift += 7
    return res, offset

def parse_record(data):
    rec = {}; offset = 0
    while offset < len(data):
        tag, offset = read_varint(data, offset)
        wt, f = tag & 7, tag >> 3
        if wt == 0:
            val, offset = read_varint(data, offset)
            if f == 1: rec['ts'] = val
            elif f == 2: rec['ram'] = val
        elif wt == 2:
            length, offset = read_varint(data, offset)
            val = data[offset:offset+length]; offset += length
            if f == 3: rec['dev'] = val.decode(errors='ignore')
            elif f == 4: rec['arch'] = val.decode(errors='ignore')
        else: break
    return rec

def parse_history_protobuf(data):
    records = []; offset = 0
    while offset < len(data):
        tag, offset = read_varint(data, offset)
        wt, f = tag & 7, tag >> 3
        if wt == 0: val, offset = read_varint(data, offset)
        elif wt == 2:
            length, offset = read_varint(data, offset)
            val = data[offset:offset+length]; offset += length
            if f == 1: records.append(parse_record(val))
        else: break
    return records

# ----- TẠO MAJORLOGIN ĐỂ LẤY JWT -----
def build_majorlogin(tok, open_id, p_type):
    m = mLpB.MajorLogin()
    m.event_time = str(datetime.now())[:-7]
    m.game_name = "free fire"
    m.platform_id = p_type
    m.client_version = "1.120.1"
    m.system_software = "Android OS 9 / API-28"
    m.system_hardware = "Handheld"
    m.telecom_operator = "Verizon"
    m.network_type = "WIFI"
    m.screen_width = 1920
    m.screen_height = 1080
    m.screen_dpi = "280"
    m.processor_details = "ARM64 FP ASIMD AES VMH | 2865 | 4"
    m.memory = 3003
    m.gpu_renderer = "Adreno (TM) 640"
    m.gpu_version = "OpenGL ES 3.1 v1.46"
    m.unique_device_id = "Google|34a7dcdf-a7d5-4cb6-8d7e-3b0e448a0c57"
    m.client_ip = "223.191.51.89"
    m.language = "en"
    m.open_id = open_id
    m.open_id_type = str(p_type)
    m.device_type = "Handheld"
    m.access_token = tok
    m.platform_sdk_id = 1
    m.client_using_version = "7428b253defc164018c604a1ebbfebdf"
    m.login_by = 3
    m.channel_type = 3
    m.cpu_type = 2
    m.cpu_architecture = "64"
    m.client_version_code = "2019118695"
    m.login_open_id_type = p_type
    m.origin_platform_type = str(p_type)
    m.primary_platform_type = str(p_type)
    return enc(m.SerializeToString())

def get_jwt_from_access_token(access_token):
    open_id = None
    try:
        r = requests.get(f"https://100067.connect.garena.com/oauth/token/inspect?token={access_token}", headers={"User-Agent": "Mozilla/5.0"}, timeout=5).json()
        open_id = r.get("open_id")
    except:
        pass
    if not open_id:
        try:
            uid_headers = {"access-token": access_token, "user-agent": "Mozilla/5.0"}
            uid_res = requests.get("https://prod-api.reward.ff.garena.com/redemption/api/auth/inspect_token/", headers=uid_headers, verify=False, timeout=5).json()
            uid = uid_res.get("uid")
            if uid:
                openid_res = requests.post("https://topup.pk/api/auth/player_id_login", json={"app_id": 100067, "login_id": str(uid)}, verify=False, timeout=5).json()
                open_id = openid_res.get("open_id")
        except:
            pass
    if not open_id:
        return None

    platforms = [8, 3, 4, 6]
    for p_type in platforms:
        pl = build_majorlogin(access_token, open_id, p_type)
        try:
            headers = {
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-S908E Build/TP1A.220624.014)",
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip",
                "Content-Type": "application/octet-stream",
                "Expect": "100-continue",
                "X-GA": "v1 1",
                "X-Unity-Version": "2018.4.11f1",
                "ReleaseVersion": "OB52"
            }
            x = requests.post("https://loginbp.ggpolarbear.com/MajorLogin", headers=headers, data=pl, timeout=10, verify=False)
            if x.status_code == 200:
                res = mLrPb.MajorLoginRes()
                try:
                    res.ParseFromString(dec(x.content))
                except:
                    res.ParseFromString(x.content)
                if res.token:
                    return res.token
        except:
            continue
    return None
# ========== BOT TELEGRAM ==========
TOKEN, EMAIL, OTP, SEC_CODE, NEW_EMAIL, OTP_NEW = range(6)

ACTION_CHECK = 'check'
ACTION_BIND = 'bind'
ACTION_UNBIND = 'unbind'
ACTION_CHANGE = 'change'
ACTION_CANCEL = 'cancel'
ACTION_HISTORY = 'history'
ACTION_BOUND = 'bound'

# ID nhóm bắt buộc (sửa lại cho đúng)
REQUIRED_GROUP_ID = -1004367092558  # ← ID nhóm của bạn (có dấu -)
GROUP_LINK = "https://t.me/+eoDrvoD7QElkYmQ1"
BOT_USERNAME = "Checkmailttoanbot"

async def is_user_in_group(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(REQUIRED_GROUP_ID, user_id)
        return member.status not in ['left', 'kicked']
    except:
        return False

def cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data='cancel_operation')]])

def not_member_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Vào nhóm @ttoanmod", url=GROUP_LINK)],
        [InlineKeyboardButton("🔄 Reload", callback_data='reload_menu')]
    ])

def only_private_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Nhắn riêng với bot", url=f"https://t.me/{BOT_USERNAME}")]
    ])

# ========== CÁC HÀNH ĐỘNG ==========
async def reload_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except:
        pass
    user_id = query.from_user.id
    chat_type = query.message.chat.type

    if chat_type != 'private':
        await query.message.reply_text(
            "🤖 Bot chỉ hoạt động trong tin nhắn riêng.\nVui lòng nhắn tin riêng với tôi để sử dụng.",
            reply_markup=only_private_keyboard()
        )
        return ConversationHandler.END

    if not await is_user_in_group(user_id, context):
        await query.message.reply_text(
            f"⚠️ Bạn cần tham gia nhóm {GROUP_LINK} để sử dụng bot.\n"
            "Vui lòng vào nhóm và nhấn 'Reload' sau khi đã tham gia.",
            reply_markup=not_member_keyboard()
        )
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("1️⃣ Check Bind Info", callback_data='check')],
        [InlineKeyboardButton("2️⃣ Bind Email", callback_data='bind')],
        [InlineKeyboardButton("3️⃣ Unbind Email", callback_data='unbind')],
        [InlineKeyboardButton("4️⃣ Change Bind Email", callback_data='change')],
        [InlineKeyboardButton("5️⃣ Cancel Bind Request", callback_data='cancel')],
        [InlineKeyboardButton("6️⃣ Get Login History", callback_data='history')],
        [InlineKeyboardButton("7️⃣ Check Bound Accounts", callback_data='bound')],
        [InlineKeyboardButton("🌐 Open Web App", url='http://t.me/Checkmailttoanbot/accesstoken')],
        [InlineKeyboardButton("🔄 Reload", callback_data='reload_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        "BIND TOOL - BOT by ttoan\nTiktok :@ttoanmod\nChọn chức năng",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.message.chat.type

    if chat_type != 'private':
        await update.message.reply_text(
            "🤖 Bot chỉ hoạt động trong tin nhắn riêng.\nVui lòng nhắn tin riêng với tôi để sử dụng.\n\n"
            "Đảm bảo bạn đã tham gia nhóm @ttoanmod trước khi sử dụng.",
            reply_markup=only_private_keyboard()
        )
        return

    if not await is_user_in_group(user_id, context):
        await update.message.reply_text(
            f"⚠️ Bạn cần tham gia nhóm {GROUP_LINK} để sử dụng bot.\n"
            "Vui lòng vào nhóm và nhấn 'Reload' sau khi đã tham gia.",
            reply_markup=not_member_keyboard()
        )
        return

    keyboard = [
        [InlineKeyboardButton("1️⃣ Check Bind Info", callback_data='check')],
        [InlineKeyboardButton("2️⃣ Bind Email", callback_data='bind')],
        [InlineKeyboardButton("3️⃣ Unbind Email", callback_data='unbind')],
        [InlineKeyboardButton("4️⃣ Change Bind Email", callback_data='change')],
        [InlineKeyboardButton("5️⃣ Cancel Bind Request", callback_data='cancel')],
        [InlineKeyboardButton("6️⃣ Get Login History", callback_data='history')],
        [InlineKeyboardButton("7️⃣ Check Bound Accounts", callback_data='bound')],
        [InlineKeyboardButton("🌐 Open Web App", url='http://t.me/Checkmailttoanbot/accesstoken')],
        [InlineKeyboardButton("🔄 Reload", callback_data='reload_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "BIND TOOL - BOT by ttoan\nTiktok :@ttoanmod\nChọn chức năng",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == 'cancel_operation':
        await query.message.edit_text("❌ Đã hủy thao tác.")
        return await reload_menu(update, context)

    if action == 'reload_menu':
        return await reload_menu(update, context)

    try:
        await query.message.delete()
    except:
        pass

    user_id = query.from_user.id
    chat_type = query.message.chat.type
    if chat_type != 'private':
        await query.message.reply_text(
            "🤖 Bot chỉ hoạt động trong tin nhắn riêng.",
            reply_markup=only_private_keyboard()
        )
        return ConversationHandler.END
    if not await is_user_in_group(user_id, context):
        await query.message.reply_text(
            f"⚠️ Bạn cần tham gia nhóm {GROUP_LINK} để sử dụng bot.",
            reply_markup=not_member_keyboard()
        )
        return ConversationHandler.END

    context.user_data['action'] = action
    context.user_data['data'] = {}

    if action in [ACTION_CHECK, ACTION_BIND, ACTION_UNBIND, ACTION_CHANGE, ACTION_CANCEL, ACTION_BOUND]:
        await query.message.reply_text("📌 Vui lòng nhập Access Token:", reply_markup=cancel_keyboard())
        return TOKEN
    elif action == ACTION_HISTORY:
        await query.message.reply_text("📌 Vui lòng nhập Access Token (sẽ tự chuyển sang JWT):", reply_markup=cancel_keyboard())
        return TOKEN
    else:
        await query.message.reply_text("❌ Chức năng không hợp lệ.")
        return ConversationHandler.END

async def handle_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    if chat_type != 'private' or not await is_user_in_group(user_id, context):
        await update.message.reply_text("⚠️ Bạn không có quyền sử dụng bot.", reply_markup=not_member_keyboard())
        return ConversationHandler.END

    if update.callback_query and update.callback_query.data == 'cancel_operation':
        query = update.callback_query
        await query.answer()
        await query.message.edit_text("❌ Đã hủy thao tác.")
        return await reload_menu(update, context)

    token = update.message.text.strip()
    context.user_data['data']['token'] = token
    action = context.user_data['action']

    try:
        await update.message.delete()
    except:
        pass

    if action == ACTION_CHECK:
        result = get_bind_info_text(token)
        await update.message.reply_text(f"📋 Kết quả Check Bind Info:\n\n{result}")
        return await show_menu(update, context)
    elif action == ACTION_BIND:
        cur_email = get_current_email(token)
        if cur_email:
            await update.message.reply_text(f"⚠️ Tài khoản đã có email: {cur_email}. Vui lòng nhập Email muốn bind:", reply_markup=cancel_keyboard())
        else:
            await update.message.reply_text("📧 Vui lòng nhập Email muốn bind:", reply_markup=cancel_keyboard())
        return EMAIL
    elif action == ACTION_UNBIND:
        cur_email = get_current_email(token)
        if not cur_email:
            await update.message.reply_text("❌ Tài khoản chưa có email để unbind.")
            return await show_menu(update, context)
        keyboard = [
            [InlineKeyboardButton("🔹 OTP", callback_data='unbind_otp')],
            [InlineKeyboardButton("🔹 Security Code", callback_data='unbind_sec')],
            [InlineKeyboardButton("❌ Cancel", callback_data='cancel_operation')]
        ]
        await update.message.reply_text("Chọn phương thức xác thực:", reply_markup=InlineKeyboardMarkup(keyboard))
        return OTP
    elif action == ACTION_CHANGE:
        cur_email = get_current_email(token)
        if not cur_email:
            await update.message.reply_text("❌ Tài khoản chưa có email để đổi.")
            return await show_menu(update, context)
        keyboard = [
            [InlineKeyboardButton("🔹 OTP", callback_data='change_otp')],
            [InlineKeyboardButton("🔹 Security Code", callback_data='change_sec')],
            [InlineKeyboardButton("❌ Cancel", callback_data='cancel_operation')]
        ]
        await update.message.reply_text("Chọn phương thức xác thực:", reply_markup=InlineKeyboardMarkup(keyboard))
        return OTP
    elif action == ACTION_CANCEL:
        result = cancel_bind_request(token)
        if result.get('result') == 0:
            await update.message.reply_text("✅ Hủy yêu cầu bind thành công.")
        else:
            await update.message.reply_text(f"❌ Hủy thất bại: {result.get('error', 'Unknown error')}")
        return await show_menu(update, context)
    elif action == ACTION_HISTORY:
        await update.message.reply_text("⏳ Đang chuyển Access Token sang JWT...")
        jwt = get_jwt_from_access_token(token)
        if not jwt:
            await update.message.reply_text("❌ Không thể lấy JWT. Token không hợp lệ.")
            return await show_menu(update, context)
        history_text = get_login_history(jwt)
        await update.message.reply_text(f"📜 Lịch sử đăng nhập:\n\n{history_text}")
        return await show_menu(update, context)
    elif action == ACTION_BOUND:
        bounded, available = get_platform_binds(token)
        if bounded is None:
            await update.message.reply_text("❌ Lỗi lấy thông tin liên kết.")
        else:
            text = "🔗 Các nền tảng đã liên kết:\n"
            if bounded:
                for p in bounded:
                    text += f"• {PLATFORM_MAP.get(p, p)}\n"
            else:
                text += "Không có\n"
            text += "\n📌 Nền tảng có thể liên kết:\n"
            if available:
                for p in available:
                    text += f"• {PLATFORM_MAP.get(p, p)}\n"
            else:
                text += "Không có\n"
            await update.message.reply_text(text)
        return await show_menu(update, context)
    else:
        await update.message.reply_text("❌ Lỗi không xác định.")
        return ConversationHandler.END

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    if chat_type != 'private' or not await is_user_in_group(user_id, context):
        await update.message.reply_text("⚠️ Bạn không có quyền sử dụng bot.", reply_markup=not_member_keyboard())
        return ConversationHandler.END

    if update.callback_query and update.callback_query.data == 'cancel_operation':
        query = update.callback_query
        await query.answer()
        await query.message.edit_text("❌ Đã hủy thao tác.")
        return await reload_menu(update, context)

    email = update.message.text.strip()
    try:
        await update.message.delete()
    except:
        pass
    context.user_data['data']['email'] = email
    token = context.user_data['data']['token']

    await update.message.reply_text(f"⏳ Đang gửi OTP đến {email}...")
    resp = send_otp(token, email)
    if resp.get('result') == 0:
        await update.message.reply_text("✅ OTP đã được gửi. Vui lòng nhập mã OTP:", reply_markup=cancel_keyboard())
        return OTP
    else:
        await update.message.reply_text(f"❌ Gửi OTP thất bại: {resp.get('error', 'Unknown')}")
        return await show_menu(update, context)

async def handle_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    if chat_type != 'private' or not await is_user_in_group(user_id, context):
        await update.message.reply_text("⚠️ Bạn không có quyền sử dụng bot.", reply_markup=not_member_keyboard())
        return ConversationHandler.END

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == 'cancel_operation':
            await query.message.edit_text("❌ Đã hủy thao tác.")
            return await reload_menu(update, context)
        elif data.startswith('unbind_'):
            context.user_data['unbind_method'] = data.split('_')[1]
            if data == 'unbind_otp':
                await query.message.reply_text("📧 Nhập mã OTP từ email hiện tại:", reply_markup=cancel_keyboard())
                return OTP
            else:
                await query.message.reply_text("🔑 Nhập mã bảo mật 6 chữ số:", reply_markup=cancel_keyboard())
                return SEC_CODE
        elif data.startswith('change_'):
            context.user_data['change_method'] = data.split('_')[1]
            if data == 'change_otp':
                await query.message.reply_text("📧 Nhập mã OTP từ email hiện tại:", reply_markup=cancel_keyboard())
                return OTP
            else:
                await query.message.reply_text("🔑 Nhập mã bảo mật 6 chữ số:", reply_markup=cancel_keyboard())
                return SEC_CODE
        else:
            return OTP

    otp = update.message.text.strip()
    try:
        await update.message.delete()
    except:
        pass
    context.user_data['data']['otp'] = otp
    action = context.user_data['action']
    token = context.user_data['data']['token']

    if action == ACTION_BIND:
        email = context.user_data['data']['email']
        resp = verify_otp(token, email, otp)
        if resp.get('result') == 0:
            verifier = resp.get('verifier_token')
            if verifier:
                context.user_data['data']['verifier_token'] = verifier
                await update.message.reply_text("✅ Xác thực OTP thành công. Nhập mã bảo mật 6 chữ số để hoàn tất:", reply_markup=cancel_keyboard())
                return SEC_CODE
            else:
                await update.message.reply_text("❌ Không lấy được verifier_token.")
                return await show_menu(update, context)
        else:
            await update.message.reply_text(f"❌ Verify OTP thất bại: {resp.get('error', 'Unknown')}")
            return await show_menu(update, context)
    elif action == ACTION_UNBIND:
        method = context.user_data.get('unbind_method')
        if method == 'otp':
            email = get_current_email(token)
            resp = verify_identity_otp(token, email, otp)
            if resp.get('result') == 0:
                identity = resp.get('identity_token')
                if identity:
                    context.user_data['data']['identity_token'] = identity
                    result = create_unbind_request(token, identity)
                    if result.get('result') == 0:
                        await update.message.reply_text("✅ Unbind thành công.")
                    else:
                        await update.message.reply_text(f"❌ Unbind thất bại: {result.get('error', 'Unknown')}")
                    return await show_menu(update, context)
                else:
                    await update.message.reply_text("❌ Không lấy được identity_token.")
                    return await show_menu(update, context)
            else:
                await update.message.reply_text(f"❌ Xác thực OTP thất bại: {resp.get('error', 'Unknown')}")
                return await show_menu(update, context)
    elif action == ACTION_CHANGE:
        method = context.user_data.get('change_method')
        if method == 'otp':
            email = get_current_email(token)
            resp = verify_identity_otp(token, email, otp)
            if resp.get('result') == 0:
                identity = resp.get('identity_token')
                if identity:
                    context.user_data['data']['identity_token'] = identity
                    await update.message.reply_text("✅ Xác thực OTP thành công. Nhập email mới:", reply_markup=cancel_keyboard())
                    return NEW_EMAIL
                else:
                    await update.message.reply_text("❌ Không lấy được identity_token.")
                    return await show_menu(update, context)
            else:
                await update.message.reply_text(f"❌ Xác thực OTP thất bại: {resp.get('error', 'Unknown')}")
                return await show_menu(update, context)
    else:
        await update.message.reply_text("❌ Lỗi: không xác định được action.")
        return ConversationHandler.END

async def handle_sec_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    if chat_type != 'private' or not await is_user_in_group(user_id, context):
        await update.message.reply_text("⚠️ Bạn không có quyền sử dụng bot.", reply_markup=not_member_keyboard())
        return ConversationHandler.END

    if update.callback_query and update.callback_query.data == 'cancel_operation':
        query = update.callback_query
        await query.answer()
        await query.message.edit_text("❌ Đã hủy thao tác.")
        return await reload_menu(update, context)

    sec = update.message.text.strip()
    try:
        await update.message.delete()
    except:
        pass
    context.user_data['data']['sec_code'] = sec
    action = context.user_data['action']
    token = context.user_data['data']['token']

    if action == ACTION_BIND:
        verifier = context.user_data['data'].get('verifier_token')
        if not verifier:
            await update.message.reply_text("❌ Thiếu verifier_token.")
            return await show_menu(update, context)
        email = context.user_data['data']['email']
        result = create_bind_request(token, email, verifier, sec)
        if result.get('result') == 0:
            await update.message.reply_text("✅ Bind email thành công!")
        else:
            await update.message.reply_text(f"❌ Bind thất bại: {result.get('error', 'Unknown')}")
        return await show_menu(update, context)
    elif action == ACTION_UNBIND:
        method = context.user_data.get('unbind_method')
        if method == 'sec':
            email = get_current_email(token)
            resp = verify_identity_sec(token, email, sec)
            if resp.get('result') == 0:
                identity = resp.get('identity_token')
                if identity:
                    result = create_unbind_request(token, identity)
                    if result.get('result') == 0:
                        await update.message.reply_text("✅ Unbind thành công.")
                    else:
                        await update.message.reply_text(f"❌ Unbind thất bại: {result.get('error', 'Unknown')}")
                else:
                    await update.message.reply_text("❌ Không lấy được identity_token.")
            else:
                await update.message.reply_text(f"❌ Xác thực mã bảo mật thất bại: {resp.get('error', 'Unknown')}")
            return await show_menu(update, context)
    elif action == ACTION_CHANGE:
        method = context.user_data.get('change_method')
        if method == 'sec':
            email = get_current_email(token)
            resp = verify_identity_sec(token, email, sec)
            if resp.get('result') == 0:
                identity = resp.get('identity_token')
                if identity:
                    context.user_data['data']['identity_token'] = identity
                    await update.message.reply_text("✅ Xác thực thành công. Nhập email mới:", reply_markup=cancel_keyboard())
                    return NEW_EMAIL
                else:
                    await update.message.reply_text("❌ Không lấy được identity_token.")
                    return await show_menu(update, context)
            else:
                await update.message.reply_text(f"❌ Xác thực mã bảo mật thất bại: {resp.get('error', 'Unknown')}")
                return await show_menu(update, context)
    else:
        await update.message.reply_text("❌ Lỗi: action không hợp lệ.")
        return ConversationHandler.END

async def handle_new_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    if chat_type != 'private' or not await is_user_in_group(user_id, context):
        await update.message.reply_text("⚠️ Bạn không có quyền sử dụng bot.", reply_markup=not_member_keyboard())
        return ConversationHandler.END

    if update.callback_query and update.callback_query.data == 'cancel_operation':
        query = update.callback_query
        await query.answer()
        await query.message.edit_text("❌ Đã hủy thao tác.")
        return await reload_menu(update, context)

    new_email = update.message.text.strip()
    try:
        await update.message.delete()
    except:
        pass
    context.user_data['data']['new_email'] = new_email
    token = context.user_data['data']['token']

    await update.message.reply_text(f"⏳ Đang gửi OTP đến {new_email}...")
    resp = send_otp(token, new_email)
    if resp.get('result') == 0:
        await update.message.reply_text("✅ OTP đã gửi. Nhập mã OTP từ email mới:", reply_markup=cancel_keyboard())
        return OTP_NEW
    else:
        await update.message.reply_text(f"❌ Gửi OTP thất bại: {resp.get('error', 'Unknown')}")
        return await show_menu(update, context)

async def handle_otp_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    if chat_type != 'private' or not await is_user_in_group(user_id, context):
        await update.message.reply_text("⚠️ Bạn không có quyền sử dụng bot.", reply_markup=not_member_keyboard())
        return ConversationHandler.END

    if update.callback_query and update.callback_query.data == 'cancel_operation':
        query = update.callback_query
        await query.answer()
        await query.message.edit_text("❌ Đã hủy thao tác.")
        return await reload_menu(update, context)

    otp = update.message.text.strip()
    try:
        await update.message.delete()
    except:
        pass
    token = context.user_data['data']['token']
    new_email = context.user_data['data']['new_email']
    identity = context.user_data['data']['identity_token']

    resp = verify_otp(token, new_email, otp)
    if resp.get('result') == 0:
        verifier = resp.get('verifier_token')
        if verifier:
            result = create_rebind_request(token, identity, new_email, verifier)
            if result.get('result') == 0:
                await update.message.reply_text("✅ Đổi email thành công!")
            else:
                await update.message.reply_text(f"❌ Đổi email thất bại: {result.get('error', 'Unknown')}")
        else:
            await update.message.reply_text("❌ Không lấy được verifier_token.")
    else:
        await update.message.reply_text(f"❌ Verify OTP mới thất bại: {resp.get('error', 'Unknown')}")
    return await show_menu(update, context)

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("1️⃣ Check Bind Info", callback_data='check')],
        [InlineKeyboardButton("2️⃣ Bind Email", callback_data='bind')],
        [InlineKeyboardButton("3️⃣ Unbind Email", callback_data='unbind')],
        [InlineKeyboardButton("4️⃣ Change Bind Email", callback_data='change')],
        [InlineKeyboardButton("5️⃣ Cancel Bind Request", callback_data='cancel')],
        [InlineKeyboardButton("6️⃣ Get Login History", callback_data='history')],
        [InlineKeyboardButton("7️⃣ Check Bound Accounts", callback_data='bound')],
        [InlineKeyboardButton("🌐 Open Web App", url='http://t.me/Checkmailttoanbot/accesstoken')],
        [InlineKeyboardButton("🔄 Reload", callback_data='reload_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "BIND TOOL - BOT by ttoan\nTiktok :@ttoanmod\nChọn chức năng",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def show_menu_from_query(query: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("1️⃣ Check Bind Info", callback_data='check')],
        [InlineKeyboardButton("2️⃣ Bind Email", callback_data='bind')],
        [InlineKeyboardButton("3️⃣ Unbind Email", callback_data='unbind')],
        [InlineKeyboardButton("4️⃣ Change Bind Email", callback_data='change')],
        [InlineKeyboardButton("5️⃣ Cancel Bind Request", callback_data='cancel')],
        [InlineKeyboardButton("6️⃣ Get Login History", callback_data='history')],
        [InlineKeyboardButton("7️⃣ Check Bound Accounts", callback_data='bound')],
        [InlineKeyboardButton("🌐 Open Web App", url='http://t.me/Checkmailttoanbot/accesstoken')],
        [InlineKeyboardButton("🔄 Reload", callback_data='reload_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        "BIND TOOL - BOT by ttoan\nTiktok :@ttoanmod\nChọn chức năng",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Đã hủy thao tác.")
    return await show_menu(update, context)

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    text = f"🆔 Your ID: `{user.id}`\n"
    if chat.type == 'private':
        text += f"📌 Chat ID: `{chat.id}` (private)"
    else:
        text += f"📌 Group ID: `{chat.id}`\n"
        text += f"👥 Group title: {chat.title}"
    await update.message.reply_text(text, parse_mode='Markdown')

async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return  # Bỏ qua tin nhắn thường trong nhóm

# ========== MAIN ==========
def main():
    application = Application.builder().token("8312271055:AAH7GAWDmhWKPWxEMz16Y6fjjbCTC4a75B8").build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_callback, pattern='^(check|bind|unbind|change|cancel|history|bound|reload_menu)$')],
        states={
            TOKEN: [CallbackQueryHandler(menu_callback, pattern='^cancel_operation$'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token)],
            EMAIL: [CallbackQueryHandler(menu_callback, pattern='^cancel_operation$'),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)],
            OTP: [CallbackQueryHandler(handle_otp, pattern='^(unbind_otp|unbind_sec|change_otp|change_sec|cancel_operation)$'),
                  MessageHandler(filters.TEXT & ~filters.COMMAND, handle_otp)],
            SEC_CODE: [CallbackQueryHandler(menu_callback, pattern='^cancel_operation$'),
                       MessageHandler(filters.TEXT & ~filters.COMMAND, handle_sec_code)],
            NEW_EMAIL: [CallbackQueryHandler(menu_callback, pattern='^cancel_operation$'),
                        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_email)],
            OTP_NEW: [CallbackQueryHandler(menu_callback, pattern='^cancel_operation$'),
                      MessageHandler(filters.TEXT & ~filters.COMMAND, handle_otp_new)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUP, group_message_handler))
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == '__main__':
    main()