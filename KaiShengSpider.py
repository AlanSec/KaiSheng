import requests
import json
from retrying import retry
from queue import Queue
import re
import pymongo
import threading
import time
import random


class KSSpider:
    def __init__(self):
        self.mobile_num = ""
        self.password = ""
        self.login_url = "http://api.capvision.cn/ks_web/api/login/loginwithpassword"
        self.list_url = "http://api.capvision.cn/ks_web/api/conference/v3/conference_list"
        self.detail_url = "http://api.capvision.cn/ks_web/api/conference/v2/detail"
        self.content_url = "http://api.capvision.cn/ks_web/api/live/v3/works/homepage"
        self.s = requests.Session()

        self.proxies = self.get_proxy()
        self.headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Host": "api.capvision.cn",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": "okhttp/2.7.2",
            "ak": "0211000000609900",
            "device_id": "ec6aad9a-8913-45b6-8919-de94cc4691a7",
            "role": "client",
            "user_id": "",
        }

        self.id_queue = Queue()
        self.detail_queue = Queue()
        self.data_queue = Queue()
        self.session_id, self.uid = self.login()

        self.database_name = "test"
        self.host = "192.168.0.8"
        self.coll_name = "conference_info"
        # 连接Mongo 账号 密码
        self.mongo_user = "indexvc"
        self.mongo_psw = "indexvc01"
        # 以上为连接MongoDB数据库相关配置
        self.client = pymongo.MongoClient(self.host)
        # self.client.admin.authenticate(self.mongo_user, self.mongo_psw)

        self.db = self.client[self.database_name]
        self.data_info_list = self.db[self.coll_name]
        # self.CompanyColl = self.db[self.CompanyInfo]
        # IT桔子相关表

    @retry(stop_max_attempt_number=10)
    def get_proxy(self):
        """
        1 .调用快代理api 获取代理ip地址
        :return: proxies
        """
        proxy_url = ""
        r = requests.get(proxy_url)
        if r.status_code == 200:
            proxies = {
                "http": "http://" + r.content.decode(),
                "https": "https://" + r.content.decode()
            }
            return proxies

    @retry(stop_max_attempt_number=10)
    def __parse_request(self, url, headers, data=None, method='GET'):
        if method == "GET":
            response = self.s.get(url=url, headers=headers, proxies=self.proxies)
            time.sleep(random.uniform(1, 2))
            if response.status_code == 200:
                return response

        elif method == "POST":
            response = self.s.post(url=url, headers=headers, data=data, proxies=self.proxies)
            time.sleep(random.uniform(1, 2))
            if response.status_code == 200:
                return response

    @retry(stop_max_attempt_number=10)
    def login(self):
        post_data = {
            "mobilenum": self.mobile_num,
            "password": self.password,
            "role": "tourist",
            "session_id": "",
            "userid": "0"
        }
        post_data = json.dumps(post_data)
        login_res = self.__parse_request(self.login_url, self.headers, data=post_data, method='POST')
        if login_res:
            response = json.loads(login_res.content.decode('utf-8'))
            data = response.get('data')
            if data:
                session_id = data.get('session_id')
                uid = data.get('uid')
                uid = str(uid)
                return session_id, uid

    def get_list_page(self):

        page_data = {"role": "client", "session_id": self.session_id, "type": "1", "userid": self.uid}
        page_data = json.dumps(page_data)

        self.headers['session_id'] = self.session_id
        self.headers['user_id'] = self.uid

        response = self.__parse_request(url=self.list_url, headers=self.headers, data=page_data, method='POST')
        if response:
            response = json.loads(response.content.decode('utf-8'))
            data = response.get('data')
            conference_list = data.get('conference_list')
            print(len(conference_list))
            for i in conference_list[0:10]:
                conference_id = i.get('conference_id')
                category = i.get('title')
                # print(conference_id)
                self.id_queue.put({'conference_id': conference_id, 'category': category})

    def parse_detail_info(self):
        detail_data = {
            "id": None,
            "role": "client",
            "session_id": self.session_id,
            "userid": self.uid
        }
        # print(type(detail_data))
        while True:
            text = self.id_queue.get()
            conference_id = text['conference_id']
            category = text['category']
            # print("*" * 100)
            # print(type(conference_id))
            detail_data['id'] = conference_id
            params_data = json.dumps(detail_data)
            response = self.__parse_request(url=self.detail_url, headers=self.headers, data=params_data, method='POST')
            if response:
                response = json.loads(response.content.decode('utf-8'))
                data = response.get('data')
                if data:
                    # print(data)
                    title = data.get('title')
                    live_id = data.get('live_id')
                    date = data.get('start_time')
                    if date is not None:
                        date = str(date)
                        time_stamp = int(date[0:-3])
                        time_array = time.localtime(time_stamp)
                        conference_time = time.strftime("%Y-%m-%d %H:%M:%S", time_array)
                        # print(conference_time)  # 2013--10--10 23:40:00
                    else:
                        conference_time = None

                    paragraph_list = data.get('paragraph_list')
                    if len(paragraph_list) == 3:
                        conference_background = paragraph_list[0].get('paragraph_content')
                        expert_profile = paragraph_list[1].get('paragraph_content')
                        expert_name = paragraph_list[1].get('paragraph_title')
                        meeting_outline = paragraph_list[2].get('paragraph_content').replace('\r\n', "")
                        expert_dict = {
                            "expert_name": expert_name,
                            "expert_profile": expert_profile
                        }
                        expert_list = list(expert_dict)
                        conference_info = {
                            "conference_background": conference_background,
                            "expert": expert_list,
                            "meeting_outline": meeting_outline
                        }
                        self.detail_queue.put(
                            {
                                "conference_info": conference_info,
                                "conference_time": conference_time,
                                "title": title,
                                "category": category,
                                "conference_id": conference_id,
                                'live_id': live_id
                            })
                    elif len(paragraph_list) == 4:
                        conference_background = paragraph_list[0].get('paragraph_content')
                        meeting_outline = paragraph_list[-1].get('paragraph_content').replace('\r\n', "")
                        expert_list = list()
                        for i in paragraph_list[1:3]:
                            expert_name = i['paragraph_title']
                            expert_profile = i['paragraph_content']
                            expert_list.append({'expert_name': expert_name, "expert_profile": expert_profile})
                        conference_info = {
                            "conference_background": conference_background,
                            "expert": expert_list,
                            "meeting_outline": meeting_outline
                        }
                        self.detail_queue.put(
                            {
                                "conference_info": conference_info,
                                "conference_time": conference_time,
                                "title": title,
                                "category": category,
                                "conference_id": conference_id,
                                "live_id": live_id
                            })
            self.id_queue.task_done()

    def parse_content_info(self):
        content_data = {"live_id": "", "role": "client", "session_id": self.session_id, "userid": self.uid}
        while True:
            info = self.detail_queue.get()
            live_id = info['live_id']
            content_data['live_id'] = live_id

            params_data = json.dumps(content_data)
            response = self.__parse_request(url=self.content_url, headers=self.headers, data=params_data,
                                            method='POST')
            if response:
                response = json.loads(response.content.decode('utf-8'))
                data = response.get('data')
                if data:
                    # print(data)
                    content_text = data.get('speech_outline')
                    if content_text is not None:
                        content_text = content_text.replace("</p>", '').replace("<p>", '').replace('&nbsp;',
                                                                                                   '').replace('\t',
                                                                                                               "").replace(
                            '\r\n', "").replace('<br/>', "")
                        if ("speech_outline" in content_text) and ("版权声明" in content_text):
                            content_text = re.findall(r"speech_outline=(.*?)版权声明.*?", content_text)
                            content = content_text[0]
                        elif ("speech_outline" not in content_text) and ("版权声明" in content_text):
                            content_text = re.findall(r"(.*?)版权声明.*?", content_text)
                            content = content_text[0]
                        else:
                            content = content_text[0]
                        info['content'] = content
                        self.data_queue.put(info)
            self.detail_queue.task_done()

    def save_data(self):
        while True:
            data = self.data_queue.get()
            # self.data_info_list.update_one({}, {}, True, False)
            print(data)
            self.data_info_list.update_one({"conference_id": data["conference_id"], "live_id": data['live_id']},
                                           {'$set': data}, True, False)
            print("update done")
            self.data_queue.task_done()

    def run(self):
        self.get_list_page()
        thread_list = list()
        for i in range(5):
            t7 = threading.Thread(target=self.parse_detail_info)
            thread_list.append(t7)

        for i in range(5):
            t8 = threading.Thread(target=self.parse_content_info)
            thread_list.append(t8)

        for i in range(1):
            t5 = threading.Thread(target=self.save_data)
            thread_list.append(t5)

        for t in thread_list:
            t.setDaemon(True)  # 设置守护线程，说明该线程不重要，主线程结束，子线程结束
            t.start()  # 线程启动

        for q in [self.id_queue, self.detail_queue, self.data_queue]:
            q.join()


if __name__ == '__main__':
    ks = KSSpider()
    ks.run()
