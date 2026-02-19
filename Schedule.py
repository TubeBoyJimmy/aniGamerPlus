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

    def fetch_schedule(self):
        """抓取排程表, 使用快取避免頻繁請求. 回傳 True 表示成功."""
        if self._last_fetch and (time.time() - self._last_fetch) < self._cache_ttl:
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

            # 解析 timeline-ver 中的排程 (依日期排列, 含星期和時間)
            timeline_ver = soup.find('div', class_='timeline-ver')
            if timeline_ver is None:
                err_print(0, '排程解析', '未找到排程區塊 (.timeline-ver)', status=1, no_sn=True)
                return False

            newanime_block = timeline_ver.find('div', class_='newanime-block')
            if newanime_block is None:
                err_print(0, '排程解析', '未找到排程區塊 (.newanime-block)', status=1, no_sn=True)
                return False

            # 星期對應 (Python weekday: 0=Monday)
            day_map = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6}

            anime_items = newanime_block.find_all('div', class_='newanime-date-area')
            for item in anime_items:
                if 'premium-block' in item.get('class', []):
                    continue

                # 取得連結和 SN
                link = item.find('a', class_='anime-card-block')
                if not link:
                    continue
                href = link.get('href', '')
                sn_match = re.findall(r'sn=(\d+)', href)
                if not sn_match:
                    continue
                sn = int(sn_match[0])

                # 取得標題
                name_el = item.find('p', class_='anime-name')
                title = name_el.get_text(strip=True) if name_el else ''

                # 取得時間
                time_el = item.find('span', class_='anime-hours')
                air_time = time_el.get_text(strip=True) if time_el else ''

                # 取得日期資訊, 推斷星期幾
                date_info_el = item.find(class_='anime-date-info')
                day_of_week = -1
                if date_info_el:
                    date_text = date_info_el.get_text(strip=True)
                    # 嘗試從日期文字中解析星期
                    for day_char, day_num in day_map.items():
                        if '(' + day_char + ')' in date_text or '（' + day_char + '）' in date_text \
                                or '週' + day_char in date_text:
                            day_of_week = day_num
                            break
                    # 如果從括號中找不到, 嘗試從日期推算
                    if day_of_week == -1:
                        date_match = re.findall(r'(\d+)/(\d+)', date_text)
                        if date_match:
                            month, day = int(date_match[0][0]), int(date_match[0][1])
                            try:
                                now = datetime.now()
                                year = now.year
                                dt = datetime(year, month, day)
                                day_of_week = dt.weekday()
                            except ValueError:
                                pass

                if day_of_week == -1:
                    continue

                entry = {'sn': sn, 'title': title, 'time': air_time}
                if day_of_week not in schedule:
                    schedule[day_of_week] = []
                schedule[day_of_week].append(entry)
                sn_schedule[sn] = {'day': day_of_week, 'time': air_time, 'title': title}
                title_schedule[title] = {'day': day_of_week, 'time': air_time, 'sn': sn}

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

    def should_check_now(self, sn, window_before=30, window_after=120, title_hints=None):
        """
        判斷當前時間是否在該 sn 的更新窗口內.
        回傳 True = 在窗口內, False = 不在窗口內, None = 不在排程表中.
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

        # 檢查是否在窗口內
        window_start = scheduled_datetime - timedelta(minutes=window_before)
        window_end = scheduled_datetime + timedelta(minutes=window_after)

        return window_start <= now <= window_end

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
                        if anime_name in title or title in anime_name:
                            return {'day': info['day'], 'time': info['time'], 'title': title}
            except Exception:
                pass

        # 3. 使用 title_hints 做標題比對 (來自 sn_list 的 plex/rename 設定)
        if title_hints:
            for hint in title_hints:
                if not hint:
                    continue
                for title, info in self._title_schedule.items():
                    if hint in title or title in hint:
                        return {'day': info['day'], 'time': info['time'], 'title': title}

        return None

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
