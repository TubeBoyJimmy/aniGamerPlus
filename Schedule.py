#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Schedule.py - 巴哈姆特動畫瘋每週排程表抓取與匹配

import re
import time
import sqlite3
import os
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from ColorPrint import err_print


class AnimeSchedule:
    """抓取並快取動畫瘋每週排程表, 判斷是否在更新窗口內"""

    def __init__(self, ua, proxies=None, db_path='', schedule_delay=0):
        self._ua = ua
        self._proxies = proxies or {}
        self._db_path = db_path
        self._schedule_delay = schedule_delay  # 排程延遲補償(秒)
        self._schedule = {}       # {day_of_week(0-6): [{'sn': int, 'title': str, 'time': 'HH:MM'}, ...]}
        self._sn_schedule = {}    # {sn: {'day': int, 'time': 'HH:MM', 'title': str}}
        self._title_schedule = {} # {title: {'day': int, 'time': 'HH:MM', 'sn': int}}
        self._last_fetch = None
        self._cache_ttl = 3600    # 快取 1 小時

    def fetch_schedule(self, force=False):
        """抓取排程表, 使用快取避免頻繁請求. 回傳 True 表示成功. force=True 時忽略快取."""
        if not force and self._last_fetch and (time.time() - self._last_fetch) < self._cache_ttl:
            return True

        try:
            url = 'https://ani.gamer.com.tw/'
            headers = {'User-Agent': self._ua}
            resp = requests.get(url, headers=headers, proxies=self._proxies, timeout=15)
            if resp.status_code != 200:
                err_print(0, '排程解析', '首頁請求失敗, HTTP ' + str(resp.status_code), status=1, no_sn=True)
                return False

            soup = BeautifulSoup(resp.content, 'html.parser')

            schedule = {}
            sn_schedule = {}
            title_schedule = {}

            # 解析週期表 (預定播出時間, 不受延播影響)
            # 週期表位於 div.programlist-wrap, 以 <h3> 分隔星期, <a.text-anime-info> 為各項目
            programlist = soup.find('div', class_='programlist-wrap')
            if programlist is None:
                err_print(0, '排程解析', '未找到週期表區塊 (.programlist-wrap)', status=1, no_sn=True)
                return False

            # 星期對應 (Python weekday: 0=Monday)
            day_map = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6}

            current_day = -1
            for el in programlist.find_all(['h3', 'a']):
                if el.name == 'h3':
                    h3_text = el.get_text(strip=True)
                    for day_char, day_num in day_map.items():
                        if '週' + day_char in h3_text:
                            current_day = day_num
                            break
                    continue

                # <a class="text-anime-info">
                if el.name != 'a' or 'text-anime-info' not in el.get('class', []):
                    continue
                if current_day == -1:
                    continue

                # 取得 SN
                href = el.get('href', '')
                sn_match = re.findall(r'sn=(\d+)', href)
                if not sn_match:
                    continue
                sn = int(sn_match[0])

                # 取得時間
                time_el = el.find('span', class_='text-anime-time')
                air_time = time_el.get_text(strip=True) if time_el else ''

                # 取得標題
                name_el = el.find('p', class_='text-anime-name')
                title = name_el.get_text(strip=True) if name_el else ''

                entry = {'sn': sn, 'title': title, 'time': air_time}
                if current_day not in schedule:
                    schedule[current_day] = []
                schedule[current_day].append(entry)
                sn_schedule[sn] = {'day': current_day, 'time': air_time, 'title': title}
                title_schedule[title] = {'day': current_day, 'time': air_time, 'sn': sn}

            self._schedule = schedule
            self._sn_schedule = sn_schedule
            self._title_schedule = title_schedule
            self._last_fetch = time.time()

            total = sum(len(v) for v in schedule.values())
            err_print(0, '排程解析', '成功解析 ' + str(total) + ' 個排程項目', status=2, no_sn=True)
            return True

        except Exception as e:
            err_print(0, '排程解析失敗', str(e), status=1, no_sn=True)
            return False

    def should_check_now(self, sn, window_after=120, title_hints=None):
        """
        判斷當前時間是否已過播出時間且在檢查窗口內.
        回傳 True = 已到播出時間, False = 尚未到播出時間, None = 不在排程表中.
        title_hints: 來自 sn_list 的標題提示列表, 用於輔助匹配排程表.
        """
        info = self._find_schedule_info(sn, title_hints=title_hints)
        if info is None:
            return None

        now = datetime.now()
        today_weekday = now.weekday()  # 0=Monday

        scheduled_day = info['day']
        air_time_str = info['time']

        if not air_time_str or ':' not in air_time_str:
            return None

        try:
            hour, minute = map(int, air_time_str.split(':'))
        except ValueError:
            return None

        # 計算本週該排程時間
        days_diff = (today_weekday - scheduled_day) % 7
        scheduled_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0) - timedelta(days=days_diff)

        # 加入排程延遲補償
        scheduled_datetime = scheduled_datetime + timedelta(seconds=self._schedule_delay)

        # 播出時間後才檢查，不提前
        window_end = scheduled_datetime + timedelta(minutes=window_after)

        return scheduled_datetime <= now <= window_end

    @staticmethod
    def _title_match(a, b):
        """判斷兩個標題是否匹配: 要求子字串長度 >= 4 且佔較長字串的 40% 以上"""
        if not a or not b:
            return False
        if a == b:
            return True
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        if shorter in longer:
            return len(shorter) >= 4 and len(shorter) / len(longer) >= 0.4
        return False

    def _find_schedule_info(self, sn, title_hints=None):
        """在排程表中尋找 sn 對應的排程資訊, 支援 SN 直接匹配、資料庫匹配和標題提示匹配"""
        # 1. 直接 SN 匹配
        if sn in self._sn_schedule:
            return self._sn_schedule[sn]

        # 2. 從資料庫取得 anime_name, 做標題子字串比對
        if self._db_path and os.path.exists(self._db_path):
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT anime_name FROM anime WHERE sn=?", (sn,))
                row = cursor.fetchone()
                cursor.close()
                conn.close()
                if row and row[0]:
                    anime_name = row[0]
                    for title, info in self._title_schedule.items():
                        if self._title_match(anime_name, title):
                            err_print(sn, '排程匹配',
                                      'DB 標題比對命中: "' + anime_name + '" → "' + title
                                      + '" (' + info['time'] + ')')
                            return {'day': info['day'], 'time': info['time'], 'title': title}
            except Exception:
                pass

        # 3. 使用 title_hints 做標題比對 (來自 sn_list 的 plex/rename 設定)
        if title_hints:
            for hint in title_hints:
                if not hint:
                    continue
                for title, info in self._title_schedule.items():
                    if self._title_match(hint, title):
                        err_print(sn, '排程匹配',
                                  'title_hint 比對命中: "' + hint + '" → "' + title
                                  + '" (' + info['time'] + ')')
                        return {'day': info['day'], 'time': info['time'], 'title': title}

        return None

    def get_next_check_seconds(self, sn_dict, window_after=120,
                               schedule_delay=0, title_hints_map=None):
        """
        計算距離下一個播出時間的秒數。
        只關心「下一個還沒到的播出時間」，重試邏輯由主迴圈負責。

        回傳 (seconds, next_time_str):
          seconds: 距離下次播出的秒數, None 表示無排程資訊
          next_time_str: 下次播出時間的 HH:MM 字串 (用於日誌)
        """
        now = datetime.now()
        candidates = []

        for sn in sn_dict:
            hints = title_hints_map.get(sn) if title_hints_map else None
            sched = self._find_schedule_info(sn, title_hints=hints)
            if sched is None:
                continue

            time_str = sched.get('time', '')
            if not time_str or ':' not in time_str:
                continue
            try:
                hour, minute = map(int, time_str.split(':'))
            except ValueError:
                continue

            day = sched['day']

            # 計算本週播出時間
            days_diff = (now.weekday() - day) % 7
            scheduled_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0) \
                           - timedelta(days=days_diff) \
                           + timedelta(seconds=schedule_delay)

            if now < scheduled_dt:
                # 播出時間未到 → 等到播出時間
                candidates.append(scheduled_dt)
            else:
                # 播出時間已過 → 下週播出時間
                candidates.append(scheduled_dt + timedelta(weeks=1))

        if not candidates:
            return None, ''

        nearest = min(candidates)
        seconds = max((nearest - now).total_seconds(), 60)  # 至少 60 秒
        return seconds, nearest.strftime('%H:%M')

    def build_time_table(self, sn_dict, schedule_delay=0, title_hints_map=None):
        """
        建構任務時間表: 對每個 sn_list 中的 SN 匹配排程, 算出觸發時間.
        回傳 {sn: {'day': int, 'time': str, 'trigger_hour': int, 'trigger_minute': int,
                   'trigger_second': int, 'trigger_time': str, 'title': str}}
        trigger_time 為顯示用字串, trigger_hour/minute/second 為比對用數值.
        """
        self.fetch_schedule()
        table = {}
        for sn in sn_dict:
            hints = title_hints_map.get(sn) if title_hints_map else None
            info = self._find_schedule_info(sn, title_hints=hints)
            if info is None:
                continue
            air_time = info['time']
            if not air_time or ':' not in air_time:
                continue
            try:
                hour, minute = map(int, air_time.split(':'))
            except ValueError:
                continue
            trigger_dt = datetime(2000, 1, 1, hour, minute) + timedelta(seconds=schedule_delay)
            table[sn] = {
                'day': info['day'],
                'time': air_time,
                'trigger_hour': trigger_dt.hour,
                'trigger_minute': trigger_dt.minute,
                'trigger_second': trigger_dt.second,
                'trigger_time': trigger_dt.strftime('%H:%M:%S') if trigger_dt.second else trigger_dt.strftime('%H:%M'),
                'title': info.get('title', '')
            }
        return table

    def get_all_scheduled_sns(self):
        """取得排程表中所有 sn"""
        return set(self._sn_schedule.keys())

    def get_schedule_data(self):
        """取得排程資料供 API 使用"""
        day_names = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
        result = {
            'last_fetch': datetime.fromtimestamp(self._last_fetch).isoformat() if self._last_fetch else None,
            'schedule': {},
            'items': []
        }
        for day in range(7):
            day_name = day_names[day]
            items = self._schedule.get(day, [])
            result['schedule'][day_name] = items
            for item in items:
                result['items'].append({
                    'sn': item['sn'],
                    'title': item['title'],
                    'time': item['time'],
                    'day': day,
                    'day_name': day_name
                })
        return result
