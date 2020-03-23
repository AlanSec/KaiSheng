#!/usr/bin/env python
# -*- coding:utf-8 -*-
import requests
import json

url = "http://api.capvision.cn/ks_web/api/conference/v3/conference_list"
login_url = "http://api.capvision.cn/ks_web/api/login/loginwithpassword"
headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Host": "api.capvision.cn",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
    "User-Agent": "okhttp/2.7.2",
    "ak": "0211000000609900",
    "device_id": "ec6aad9a-8913-45b6-8919-de94cc4691a7",
    "role": "client",
    "user_id": "66471",
}
login_data = {"mobilenum": "18191594559", "password": "1qazxdr5.", "role": "tourist", "session_id": "", "userid": "0"}
page_data = {"role": "client", "session_id": "skst8880swtt", "type": "1", "userid": "66471"}
data = json.dumps(login_data)
s = requests.Session()
res = s.post(login_url, headers=headers, data=data)
print(res.status_code)
print(res.content.decode('utf-8'))
js_data = res.content.decode('utf-8')
js_data = json.loads(js_data)
result = js_data.get('data')
session_id = result.get('session_id')
print(session_id)

page_data['session_id'] = session_id

headers['session_id'] = session_id

page_data = json.dumps(page_data)

page_res = s.post(url=url, headers=headers, data=page_data)

print(page_res.status_code)

print(page_res.content.decode('utf-8'))
