#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
库街区 (kurobbs) 鸣潮 账号登录器 — 纯浏览器交互（无终端输入）

设计：AI 后台起本地 HTTP 服务并自动打开浏览器，用户全程在网页里操作：
  1. 填手机号 → 点"获取验证码" → 弹出极验滑块 → 手动拖动
  2. 滑块通过 → 自动发短信 → 页面出现验证码输入框
  3. 填 6 位验证码 → 点"登录" → 自动登录 + 拉取角色数据 → 保存到 account.json

这样 AI 只需 `run_bash` 启动服务并阻塞等待（给足 timeout），无需终端交互，
解决了旧版 `input()` 在 AI 环境卡死的问题。

用法:
  python kuro_login.py login <手机号>   # 起服务，浏览器操作，阻塞直到完成/超时
  python kuro_login.py roles            # 列出已存账号的角色
  python kuro_login.py status           # 查看当前登录账号
  python kuro_login.py account          # 打印 account.json 原始内容
"""

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Windows GBK 兜底：强制 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------- 常量（来自 WutheringWavesTool / ApiConfig.java + BaseTask.java） ----------

BASE = "https://api.kurobbs.com"
URL_GET_SMS_CODE_H5 = BASE + "/user/getSmsCodeForH5"      # 发短信验证码（需极验 geeTestData）
URL_SDK_LOGIN = BASE + "/user/sdkLogin"                    # 验证码登录 → token
URL_ACCOUNT_SEEK_ROLE = BASE + "/gamer/role/list"         # 用 token 拿绑定的角色列表
URL_ROLE_ACCESS_TOKEN = BASE + "/aki/roleBox/requestToken" # 换 B-At access token
URL_ROLE_DATA = BASE + "/aki/roleBox/akiBox/roleData"     # 拿拥有角色详情（需 B-At + multipart）

PARAM_SERVER_ID = "76402e5b20be2c39f095a152090afddc"       # ApiConfig.PARAM_SERVER_ID
PARAM_GAME_ID = "3"                                        # ApiConfig.PARAM_GAME_ID

# 库街区 H5 发码 captchaId（来自原项目 geetest.html）
CAPTCHA_ID = "ec4aa4174277d822d73f2442a165a2cd"

# 发短信用 iPhone UA（SendSmsTask.java:39-42）
SMS_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) "
          "AppleWebKit/605.1.15 (KHTML, like Gecko) KuroGameBox/3.1.3")
SMS_VERSION = "3.1.3"

# 换 B-At / 查角色用 Android UA（BaseTask.java:414）
ANDROID_UA = ("Mozilla/5.0 (Linux; Android 9; 23116PN5BC Build/PQ3A.190605.02201427; wv) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/124.0.6367.82 "
              "Mobile Safari/537.36 Kuro/2.5.0 KuroGameBox/2.5.0")

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".kurobbs-wiki-cache")
ACCOUNT_FILE = os.path.join(CACHE_DIR, "account.json")

HOST = "127.0.0.1"
PORT = 8090

# 登录 token 有效期（秒）。库街区 sdkLogin token 无官方文档明确时长，
# 原项目 B-At 机制按 3600s 提前 300s 刷新；这里保守取 45 分钟，到期提示重登。
TOKEN_TTL_SECONDS = 45 * 60

# ---------- 登录状态（跨 HTTP 请求共享） ----------

LOGIN = {
    "phone": None,
    "gee_test": None,
    "done": False,
    "success": False,
    "message": "",
    "event": threading.Event(),
}


def reset_login():
    LOGIN["phone"] = None
    LOGIN["gee_test"] = None
    LOGIN["done"] = False
    LOGIN["success"] = False
    LOGIN["message"] = ""
    LOGIN["event"].clear()


# ---------- HTML 页面（单页多步：手机号 → 滑块 → 验证码 → 登录） ----------

LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>库街区登录</title>
<style>
  html,body{margin:0;padding:0;height:100%;font-family:"Microsoft YaHei",sans-serif;background:#f8fafc;}
  #status{padding:10px 14px;font-size:14px;color:#334;background:#fff;border-bottom:1px solid #dde3ea;}
  #status.ok{color:#067647;}
  #status.err{color:#b42318;}
  #box{padding:20px;max-width:420px;margin:0 auto;}
  .step{display:none;}
  .step.active{display:block;}
  label{display:block;margin:12px 0 6px;font-size:13px;color:#475467;}
  input{width:100%;padding:10px;font-size:15px;border:1px solid #d0d5dd;border-radius:8px;box-sizing:border-box;}
  button{width:100%;padding:12px;margin-top:14px;font-size:15px;border:none;border-radius:8px;background:#155eef;color:#fff;cursor:pointer;}
  button:disabled{background:#98a2b3;cursor:not-allowed;}
  .hint{font-size:12px;color:#98a2b3;margin-top:8px;line-height:1.6;}
  #geetest_slot{height:0;overflow:hidden;}
</style>
</head>
<body>
<div id="status">正在加载登录页…</div>
<div id="box">
  <!-- 步骤1：手机号 -->
  <div id="step_phone" class="step active">
    <label>输入库街区登录手机号</label>
    <input id="phone" type="tel" maxlength="11" placeholder="11 位大陆手机号"/>
    <button id="btn_getcode" onclick="getCode()">获取验证码</button>
    <div class="hint">点击后会自动弹出极验滑块，请拖动滑块完成验证，验证码将发送到你的手机</div>
  </div>
  <!-- 步骤2：验证码 -->
  <div id="step_code" class="step">
    <label>输入短信验证码</label>
    <input id="code" type="text" maxlength="6" placeholder="6 位验证码"/>
    <button id="btn_login" onclick="doLogin()">登录</button>
    <div class="hint" id="sms_hint">验证码已发送，请查收手机短信</div>
  </div>
  <!-- 步骤3：完成 -->
  <div id="step_done" class="step">
    <div id="done_msg" style="font-size:16px;color:#067647;padding:20px 0;text-align:center;"></div>
    <div class="hint">登录成功后可以关闭本页面，回到对话继续提问</div>
  </div>
  <div id="geetest_slot"></div>
</div>
<script>
var CAPTCHA_ID = "%CAPTCHA_ID%";
var captchaObj = null;
var phone = "";
function setStatus(text, cls){var el=document.getElementById("status");el.textContent=text;el.className=cls||"";}
function showStep(id){document.querySelectorAll(".step").forEach(function(s){s.classList.remove("active");});document.getElementById(id).classList.add("active");}
function httpPost(url, body, cb){
  var xhr=new XMLHttpRequest();
  xhr.open("POST", url, true);
  xhr.setRequestHeader("Content-Type","application/json");
  xhr.onload=function(){
    var j={};
    try{j=JSON.parse(xhr.responseText);}catch(e){}
    cb(j, xhr.status);
  };
  xhr.onerror=function(){cb({error:"网络错误"},0);};
  xhr.send(JSON.stringify(body||{}));
}

// 极验滑块初始化与成功回调
function initGeetest(){
  if(!window.initGeetest4){setStatus("极验脚本加载失败","err");return;}
  window.initGeetest4({captchaId:CAPTCHA_ID,product:"bind",language:"zho",protocol:"https://"},function(captcha){
    captchaObj=captcha;
    captcha.onReady(function(){captchaObj.showBox();})
      .onSuccess(function(){
        var result=captcha.getValidate();
        if(!result){setStatus("未拿到校验结果","err");return;}
        result.captcha_id=CAPTCHA_ID;
        setStatus("极验通过，正在发送验证码…","ok");
        // 把货台结果发给后端，后端发短信
        httpPost("/geetest_result", {gee_test: result, phone: phone}, function(j){
          if(j && j.ok){
            setStatus("验证码已发送","ok");
            showStep("step_code");
          }else{
            setStatus((j&&j.error)||"发送验证码失败","err");
          }
        });
      })
      .onError(function(){setStatus("极验出错，请重试","err");})
      .onClose(function(){});
  });
}

function getCode(){
  phone=document.getElementById("phone").value.trim();
  if(!/^1[3-9]\d{9}$/.test(phone)){setStatus("请输入正确的 11 位手机号","err");return;}
  setStatus("正在加载极验滑块…","");
  // 加载极验脚本
  if(!window.initGeetest4){
    var srcs=["https://static.geetest.com/v4/gt4.js","https://static.geevisit.com/v4/gt4.js"];
    var i=0,loaded=false;
    function loadNext(){
      if(loaded||i>=srcs.length){if(!loaded){setStatus("极验脚本加载失败","err");}return;}
      var s=document.createElement("script");s.src=srcs[i++];
      s.onload=function(){if(window.initGeetest4){loaded=true;initGeetest();}else loadNext();};
      s.onerror=loadNext;
      document.head.appendChild(s);
    }
    loadNext();
  }else{
    initGeetest();
  }
}

function doLogin(){
  var code=document.getElementById("code").value.trim();
  if(!/^\d{6}$/.test(code)){setStatus("请输入 6 位验证码","err");return;}
  setStatus("正在登录并拉取角色…","");
  httpPost("/login", {phone: phone, code: code}, function(j){
    if(j && j.ok){
      setStatus("登录成功","ok");
      showStep("step_done");
      document.getElementById("done_msg").textContent="✅ 登录成功！已保存你的角色数据";
    }else{
      setStatus((j&&j.error)||"登录失败,请重试","err");
    }
  });
}
</script>
</body>
</html>
"""


# ---------- 配置 / 存储 ----------


def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def load_account():
    if os.path.exists(ACCOUNT_FILE):
        try:
            with open(ACCOUNT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_account(account):
    ensure_cache_dir()
    with open(ACCOUNT_FILE, "w", encoding="utf-8") as f:
        json.dump(account, f, ensure_ascii=False, indent=2)


# ---------- HTTP 工具 ----------


def http_post_form(url, form, headers=None, timeout=20):
    payload = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded;charset=UTF-8")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        status = e.code
    except Exception as e:
        return 0, {"_error": str(e)}
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, {"raw": raw[:500]}


def http_post_body(url, body_bytes, content_type, headers=None, timeout=20):
    req = urllib.request.Request(url, data=body_bytes, method="POST")
    req.add_header("Content-Type", content_type)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        status = e.code
    except Exception as e:
        return 0, {"_error": str(e)}
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, {"raw": raw[:500]}


# ---------- multipart 构造 ----------


def build_multipart(parts):
    import random
    boundary = "".join(random.choice("0123456789") for _ in range(30))
    chunks = []
    for name, value in parts:
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)
    return "multipart/form-data; boundary=" + boundary, body


def random_dev_code():
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(chars[b % len(chars)] for b in os.urandom(32))


def random_did():
    return uuid.uuid4().hex.replace("-", "")


def get_public_ip():
    for svc in ("https://event.kurobbs.com/event/ip",
                "https://api.ipify.org/?format=json",
                "https://httpbin.org/ip"):
        try:
            with urllib.request.urlopen(svc, timeout=5) as resp:
                raw = resp.read().decode("utf-8", errors="replace").strip()
                m = re.search(r"\d+\.\d+\.\d+\.\d+", raw)
                if m:
                    return m.group(0)
        except Exception:
            continue
    return "127.127.127.127"


def get_dev_code():
    ip = get_public_ip()
    return f"{ip}, Mozilla/5.0 (Linux; Android 9; 23116PN5BC Build/PQ3A.190605.02201427; wv) " \
           f"AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/124.0.6367.82 " \
           f"Mobile Safari/537.36 Kuro/2.5.0 KuroGameBox/2.5.0"


# ---------- 库街区 API 调用 ----------


def send_sms_code(phone, gee_test_json):
    form = {
        "mobile": phone,
        "geeTestData": gee_test_json or "",
    }
    headers = {
        "User-Agent": SMS_UA,
        "source": "h5",
        "devcode": random_dev_code(),
        "version": SMS_VERSION,
    }
    status, obj = http_post_form(URL_GET_SMS_CODE_H5, form, headers)
    if status == 0:
        return False, "网络错误: " + obj.get("_error", "")
    if status < 200 or status >= 300:
        return False, f"连接失败，响应状态码:{status}"
    if not obj:
        return False, "服务器返回空响应"
    success = bool(obj.get("success")) or obj.get("code") in (0, 200)
    msg = obj.get("msg") or ("验证码发送成功" if success else "发送失败")
    return success, str(msg)


def sdk_login(phone, code):
    did = random_did()
    devcode = get_dev_code()
    url = f"{URL_SDK_LOGIN}?code={urllib.parse.quote(code)}&mobile={urllib.parse.quote(phone)}&devCode={did}"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "source": "android",
        "devcode": devcode,
        "did": did,
    }
    status, obj = http_post_form(url, {}, headers)
    if status != 200:
        return False, None, None, f"连接失败，状态码:{status}"
    if not obj:
        return False, None, None, "服务器返回空响应"
    if obj.get("code") != 200:
        return False, None, None, str(obj.get("msg") or "登录失败")
    data = obj.get("data") or {}
    token = data.get("token")
    if not token:
        return False, None, None, "登录成功但未返回 token"
    return True, token, did, "success"


def seek_role(token, is_web=False):
    url = f"{URL_ACCOUNT_SEEK_ROLE}?gameId={PARAM_GAME_ID}"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "source": "h5" if is_web else "android",
        "token": token,
    }
    status, obj = http_post_form(url, {}, headers)
    if status != 200:
        return False, None, f"连接失败，状态码:{status}"
    if not obj:
        return False, None, "服务器返回空响应"
    if obj.get("code") != 200:
        return False, None, str(obj.get("msg") or "查询角色失败")
    data = obj.get("data") or []
    roles = []
    for item in data:
        roles.append({
            "userId": str(item.get("userId", "")),
            "roleId": str(item.get("roleId", "")),
            "roleName": item.get("roleName", ""),
        })
    return True, roles, "success"


def request_access_token(user_id, role_id, token):
    url = (f"{URL_ROLE_ACCESS_TOKEN}?serverId={PARAM_SERVER_ID}"
           f"&roleId={role_id}&userId={user_id}")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "source": "android",
        "B-At": "",
        "token": token,
    }
    status, obj = http_post_form(url, {}, headers)
    if status != 200:
        return False, None, f"连接失败，状态码:{status}"
    if not obj or obj.get("code") not in (200, 10902):
        return False, None, str((obj or {}).get("msg") or "获取 access token 失败")
    data_str = obj.get("data")
    if isinstance(data_str, str):
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            return False, None, "access token 响应解析失败"
    else:
        data = data_str or {}
    at = data.get("accessToken")
    if not at:
        return False, None, "access token 为空"
    return True, at, "success"


URL_ROLE_DETAIL = BASE + "/aki/roleBox/akiBox/getRoleDetail"  # 单角色完整详情（需 id/channelId/countryCode）


def fetch_role_detail(role_id, token, access_token, devcode, did, card_role_id):
    """拉取单个角色的完整详情（共鸣链/实际武器/实际声骸/技能等级/面板）。

    对应 WutheringWavesTool 的 GameRoleDetailTask（getRoleDetail 接口）。
    card_role_id = roleData 里该角色的 roleId（如维里奈 1503）。
    返回完整 dict（含 chainList/weaponData/phantomData/skillList/roleAttributeList）。
    """
    content_type, body = build_multipart([
        ("serverId", PARAM_SERVER_ID),
        ("roleId", role_id),
        ("gameId", PARAM_GAME_ID),
        ("id", str(card_role_id)),
        ("channelId", "19"),
        ("countryCode", "1"),
    ])
    headers = {
        "User-Agent": ANDROID_UA,
        "Accept": "application/json, text/plain, */*",
        "Source": "android",
        "Devcode": devcode,
        "B-At": access_token,
        "Did": did,
        "Token": token,
    }
    status, obj = http_post_body(URL_ROLE_DETAIL, body, content_type, headers)
    if status != 200:
        return False, None, f"连接失败，状态码:{status}"
    if not obj:
        return False, None, "服务器返回空响应"
    if obj.get("code") == 220:
        return False, None, "access token 失效，请重新登录"
    if obj.get("code") not in (200, 10902):
        return False, None, str(obj.get("msg") or f"查询角色详情失败 code={obj.get('code')}")
    data_str = obj.get("data")
    if isinstance(data_str, str):
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            return False, None, "角色详情响应解析失败"
    else:
        data = data_str or {}
    return True, data, "success"


def fetch_role_data(role_id, token, access_token, devcode, did):
    content_type, body = build_multipart([
        ("serverId", PARAM_SERVER_ID),
        ("roleId", role_id),
        ("gameId", PARAM_GAME_ID),
    ])
    headers = {
        "User-Agent": ANDROID_UA,
        "Accept": "application/json, text/plain, */*",
        "Source": "android",
        "Devcode": devcode,
        "B-At": access_token,
        "Did": did,
        "Token": token,
    }
    status, obj = http_post_body(URL_ROLE_DATA, body, content_type, headers)
    if status != 200:
        return False, None, f"连接失败，状态码:{status}"
    if not obj:
        return False, None, "服务器返回空响应"
    if obj.get("code") == 220:
        return False, None, "access token 失效，请重新登录"
    if obj.get("code") not in (200, 10902):
        return False, None, str(obj.get("msg") or f"查询角色数据失败 code={obj.get('code')}")
    data_str = obj.get("data")
    if isinstance(data_str, str):
        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            return False, None, "角色数据响应解析失败"
    else:
        data = data_str or {}
    role_list = data.get("roleList") or []
    role_list.sort(key=lambda r: int(r.get("level", 0) or 0), reverse=True)
    return True, role_list, "success"


# ---------- 本地 HTTP 服务 ----------


class LoginHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 静默

    def _send(self, code, body_bytes, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def do_GET(self):
        if self.path == "/geetest" or self.path.startswith("/geetest?"):
            html = LOGIN_HTML.replace("%CAPTCHA_ID%", CAPTCHA_ID)
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {}
        path = self.path

        if path == "/geetest_result":
            # 滑块通过：记录 geetest，后端发短信
            gee = data.get("gee_test")
            phone = (data.get("phone") or "").strip()
            LOGIN["phone"] = phone
            LOGIN["gee_test"] = gee
            if not phone or not gee:
                self._json({"ok": False, "error": "手机号或极验结果缺失"})
                return
            ok, msg = send_sms_code(phone, json.dumps(gee, ensure_ascii=False))
            if ok:
                self._json({"ok": True, "msg": msg})
            else:
                self._json({"ok": False, "error": msg})

        elif path == "/login":
            phone = (data.get("phone") or "").strip()
            code = (data.get("code") or "").strip()
            try:
                ok, token, did, msg = sdk_login(phone, code)
                if not ok:
                    self._json({"ok": False, "error": msg})
                    return
                # 拉取角色
                ok_seek, roles, msg_seek = seek_role(token)
                role_list = []
                if ok_seek and roles:
                    selected = roles[0]
                    ok_at, at, _ = request_access_token(
                        selected["userId"], selected["roleId"], token)
                    if ok_at:
                        devcode = get_dev_code()
                        _, role_list, _ = fetch_role_data(
                            selected["roleId"], token, at, devcode, did)
                account = {
                    "phone": phone,
                    "token": token,
                    "did": did,
                    "is_web": False,
                    "login_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "login_ts": int(time.time()),
                    "token_ttl": TOKEN_TTL_SECONDS,
                    "roles": roles if ok_seek else [],
                    "role_list": role_list,
                    "role_details": {},   # roleName -> 完整详情（共鸣链/武器/声骸/技能/面板）
                }
                # 为每个角色拉取完整详情（getRoleDetail）
                if ok_at and role_list:
                    devcode = get_dev_code()
                    details = {}
                    for r in role_list:
                        rname = r.get("roleName") or ""
                        rid = str(r.get("roleId") or "")
                        if not rname or not rid:
                            continue
                        try:
                            ok_d, detail, _ = fetch_role_detail(
                                selected["roleId"], token, at, devcode, did, rid)
                            if ok_d and isinstance(detail, dict):
                                details[rname] = detail
                        except Exception:
                            pass
                    account["role_details"] = details
                save_account(account)
                LOGIN["success"] = True
                LOGIN["message"] = f"登录成功，绑定角色 {len(roles) if ok_seek else 0} 个"
                LOGIN["done"] = True
                LOGIN["event"].set()
                self._json({"ok": True, "msg": LOGIN["message"]})
            except Exception as e:
                self._json({"ok": False, "error": f"登录异常: {e}"})

        else:
            self._json({"error": "not found"}, 404)


def run_login_server(timeout=300):
    """启动登录服务，阻塞直到用户完成登录或超时。返回 bool（是否登录成功）"""
    reset_login()
    server = ThreadingHTTPServer((HOST, PORT), LoginHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    print(f"[登录] 已在本地启动服务: http://{HOST}:{PORT}/geetest")
    try:
        webbrowser.open(f"http://{HOST}:{PORT}/geetest")
    except Exception:
        pass
    print("[登录] 已尝试自动打开浏览器。若未弹出，请手动打开上面的网址。")
    print("[登录] 请在网页里：填手机号 → 拖滑块 → 填验证码 → 点登录。")
    if not LOGIN["event"].wait(timeout=timeout):
        server.shutdown()
        print("[登录] 等待超时，未完成登录")
        return False
    server.shutdown()
    print(f"[登录] {LOGIN['message']}")
    return LOGIN["success"]


# ---------- 校验 ----------


def is_valid_cn_mobile(mobile):
    return bool(mobile and re.match(r"^1[3-9]\d{9}$", mobile))


# ---------- 命令 ----------


def cmd_sync(args):
    """用现有 token 全量对齐账号角色完整数据（不重新登录）。

    流程：seek_role 刷新角色列表 → 换 B-At → 遍历每个角色拉 getRoleDetail。
    漏的角色自动补，练度变化的自动更新，role_list 也同步刷新。
    """
    acc = load_account()
    if not acc or not acc.get("token"):
        print("[错误] 尚未登录。请先执行 my login（浏览器登录）")
        sys.exit(1)
    token = acc.get("token")
    did = acc.get("did") or random_did()
    # 1. seek_role 刷新绑定角色
    ok, roles, msg = seek_role(token)
    if not ok:
        print(f"[错误] token 失效或网络异常：{msg}")
        print("       → 请执行 my renew / my login 重新登录")
        sys.exit(1)
    if not roles:
        print("[错误] 账号没有绑定角色")
        sys.exit(1)
    sel = roles[0]
    uid, rid = str(sel.get("userId")), str(sel.get("roleId"))
    # 2. 换 B-At
    ok_at, at, msg_at = request_access_token(uid, rid, token)
    if not ok_at:
        print(f"[错误] 获取 access token 失败：{msg_at}")
        sys.exit(1)
    # 3. 拉角色列表 + 每个角色完整详情
    devcode = get_dev_code()
    ok_data, role_list, msg_data = fetch_role_data(rid, token, at, devcode, did)
    if not ok_data:
        print(f"[错误] 拉取角色列表失败：{msg_data}")
        sys.exit(1)
    details = dict(acc.get("role_details") or {})
    added = updated = same = 0
    for r in role_list:
        rname = r.get("roleName") or ""
        crid = str(r.get("roleId") or "")
        if not rname or not crid:
            continue
        try:
            ok_d, detail, _ = fetch_role_detail(rid, token, at, devcode, did, crid)
            if not ok_d or not isinstance(detail, dict):
                continue
            if rname not in details:
                added += 1
            elif detail != details.get(rname):
                updated += 1
            else:
                same += 1
            details[rname] = detail
        except Exception:
            pass
        time.sleep(0.05)  # 轻限速，防风控
    acc["role_list"] = role_list
    acc["role_details"] = details
    acc["login_ts"] = int(time.time())
    save_account(acc)
    print(f"[同步完成] 角色总数 {len(role_list)} | 新增 {added} | 更新 {updated} | 未变 {same}")
    if added or updated:
        names = [r.get("roleName") for r in role_list]
        print(f"[角色] {', '.join(names)}")


def cmd_login(args):
    if args.phone and not is_valid_cn_mobile(args.phone):
        print(f"[错误] 手机号格式不正确: {args.phone}（应为 11 位大陆手机号）")
        sys.exit(1)
    ok = run_login_server(timeout=args.timeout)
    if not ok:
        sys.exit(1)


def cmd_roles(args):
    acc = load_account()
    if not acc:
        print("[错误] 尚未登录。请先执行 my login（浏览器登录）")
        sys.exit(1)
    print(f"# 当前登录: {acc.get('phone')}（登录于 {acc.get('login_time')}）")
    role_list = acc.get("role_list") or []
    if not role_list:
        print("[提示] 没有角色详情数据（可能登录时未拉到）。以下为绑定角色列表：")
        for r in acc.get("roles") or []:
            print(f"  - {r.get('roleName')} (roleId={r.get('roleId')})")
        return
    print(f"拥有角色 {len(role_list)} 个（按等级降序）：")
    print(f"{'角色':<10}{'等级':<6}{'突破':<6}{'共鸣链':<8}{'属性':<10}{'武器类型':<12}{'星级'}")
    print("-" * 68)
    for r in role_list:
        print(f"{r.get('roleName',''):<10}{r.get('level',0):<6}{r.get('breach',0):<6}"
              f"S{r.get('chainUnlockNum',0):<7}{r.get('attributeName',''):<10}"
              f"{r.get('weaponTypeName',''):<12}{r.get('starLevel',0)}")


def cmd_status(args):
    acc = load_account()
    if not acc:
        print("[错误] 尚未登录。请先执行 my login（浏览器登录）")
        sys.exit(1)
    print(f"手机号   : {acc.get('phone')}")
    print(f"登录时间 : {acc.get('login_time')}")
    print(f"绑定角色 : {len(acc.get('roles') or [])} 个")
    for r in acc.get("roles") or []:
        print(f"  - {r.get('roleName')} (roleId={r.get('roleId')})")


def cmd_account(args):
    acc = load_account()
    if not acc:
        print("[错误] 尚未登录。")
        sys.exit(1)
    print(json.dumps(acc, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(prog="kuro_login", description="库街区鸣潮账号登录器（纯浏览器交互）")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_login = sub.add_parser("login", help="登录库街区账号（浏览器操作：填手机号→拖滑块→填验证码）")
    p_login.add_argument("phone", nargs="?", help="11 位大陆手机号（可选，也可在网页里填）")
    p_login.add_argument("--timeout", type=int, default=300, help="等待用户完成登录的超时秒数（默认300）")
    p_login.set_defaults(fn=cmd_login)

    p_roles = sub.add_parser("roles", help="列出已登录账号拥有的角色")
    p_roles.set_defaults(fn=cmd_roles)

    p_status = sub.add_parser("status", help="查看当前登录账号")
    p_status.set_defaults(fn=cmd_status)

    p_acct = sub.add_parser("account", help="打印 account.json 原始内容")
    p_acct.set_defaults(fn=cmd_account)

    p_sync = sub.add_parser("sync", help="用现有 token 全量对齐角色完整数据（补新角色/更新变化，无需重新登录）")
    p_sync.set_defaults(fn=cmd_sync)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()