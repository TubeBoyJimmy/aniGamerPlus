#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Time    : 2019/1/4 1:00
# @Author  : Miyouzi
# @File    : aniGamerPlus.py
# @Software: PyCharm

# 非阻塞 (Web)
from gevent import monkey
monkey.patch_all()


import os, sys, time, re, random, traceback, argparse
import signal
from datetime import datetime, timedelta
import sqlite3
import threading
import subprocess
import platform
import socket
import pip_system_certs.wrapt_requests
import requests

# 巴哈 WAF 以 TLS 指紋攔截非瀏覽器請求, 優先走 curl_cffi (詳見 Anime.py)
try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None

import Config
import BahaRequest
from Anime import Anime, TryTooManyTimeError
from ColorPrint import err_print
from Danmu import Danmu


def port_is_available(port):
    # 检测端口是否可用(未占用), 可用返回 True
    # 参考: https://blog.csdn.net/roger_royer/article/details/79519826
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    if result == 0:
        return False
    else:
        return True


def gost_port():
    random_port = random.randint(40000, 60000)
    while not port_is_available(random_port):
        # 如果该端口不可用
        random_port = random.randint(40000, 60000)
    return random_port


def build_anime(sn):
    anime = {'anime': None, 'failed': True}
    try:
        if settings['use_gost']:
            # 如果使用 gost, 则随机一个 gost 监听端口
            anime['anime'] = Anime(sn, gost_port=gost_port)
        else:
            anime['anime'] = Anime(sn)
        anime['failed'] = False

        if danmu:
            anime['anime'].enable_danmu()

    except TryTooManyTimeError:
        err_print(sn, '抓取失敗', '影片信息抓取失敗!', status=1)
    except BaseException as e:
        err_print(sn, '抓取失敗', '抓取影片信息時發生未知錯誤: '+str(e), status=1)
        err_print(sn, '抓取異常', '異常詳情:\n'+traceback.format_exc(), status=1, display=False)

    # sn 解析冷却
    if settings['parse_sn_cd'] > 0:
        err_print("更新資訊", "SN 解析冷卻 " + str(settings['parse_sn_cd']) + " 秒", no_sn=True)
        time.sleep(settings['parse_sn_cd'])

    return anime


def read_db_all():
    db_locker.acquire()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("select * FROM anime")

    try:
        values = cursor.fetchall()
    except IndexError as e:
        cursor.close()
        conn.close()
        db_locker.release()
        raise e

    anime_db = [0] * len(values)
    for i in range(len(values)):
        anime_db[i] = {'sn': values[i][0],
                    'title': values[i][1],
                    'anime_name': values[i][2],
                    'episode': values[i][3],
                    'status': values[i][4],
                    'remote_status': values[i][5],
                    'resolution': values[i][6],
                    'file_size': values[i][7],
                    'local_file_path': values[i][8]}

    cursor.close()
    conn.close()
    db_locker.release()
    return anime_db


def read_db(sn):
    db_locker.acquire()
    # 传入sn(int)，读取该 sn 资料，返回 dict
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("select * FROM anime WHERE sn=:sn", {'sn': sn})

    try:
        values = cursor.fetchall()[0]
    except IndexError as e:
        cursor.close()
        conn.close()
        db_locker.release()
        raise e
    anime_db = {'sn': values[0],
                'title': values[1],
                'anime_name': values[2],
                'episode': values[3],
                'status': values[4],
                'remote_status': values[5],
                'resolution': values[6],
                'file_size': values[7],
                'local_file_path': values[8]}

    cursor.close()
    conn.close()
    db_locker.release()
    return anime_db


def insert_db(anime):
    db_locker.acquire()
    # 向数据库插入新资料
    anime_dict = {'sn': str(anime.get_sn()),
                  'title': anime.get_title(),
                  'anime_name': anime.get_bangumi_name(),
                  'episode': anime.get_episode()}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("INSERT OR IGNORE INTO anime (sn, title, anime_name, episode) VALUES (:sn, :title, :anime_name, :episode)",
                   anime_dict)

    cursor.close()
    conn.commit()
    conn.close()
    db_locker.release()


def update_db(anime):
    db_locker.acquire()
    # 更新数据库 status, resolution, file_size 资料
    anime_dict = {}
    if anime.video_size > 5:
        anime_dict['status'] = 1
    else:
        # 下载失败
        anime_dict['status'] = 0

    if anime.upload_succeed_flag:
        anime_dict['remote_status'] = 1
    else:
        anime_dict['remote_status'] = 0

    anime_dict['sn'] = anime.get_sn()
    anime_dict['title'] = anime.get_title()
    anime_dict['anime_name'] = anime.get_bangumi_name()
    anime_dict['episode'] = anime.get_episode()
    anime_dict['file_size'] = anime.video_size
    anime_dict['resolution'] = anime.video_resolution
    anime_dict['local_file_path'] = anime.local_video_path

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE anime SET status=:status,"
            "remote_status=:remote_status,"
            "resolution=:resolution,"
            "file_size=:file_size,"
            "local_file_path=:local_file_path WHERE sn=:sn",
            anime_dict)
    except IndexError as e:
        cursor.close()
        conn.commit()
        conn.close()
        db_locker.release()
        raise e

    cursor.close()
    conn.commit()
    conn.close()
    db_locker.release()


def worker(sn, sn_info, realtime_show_file_size=False):
    bangumi_tag = sn_info['tag']
    rename = sn_info['rename']
    plex_info = sn_info.get('plex', None)

    def upload_quit():
        queue.pop(sn)
        processing_queue.remove(sn)
        upload_limiter.release()  # 并发上传限制器
        sys.exit(0)

    anime_in_db = read_db(sn)
    # 如果用户设定要上传且已经下载好了但还没有上传成功, 那么仅上传
    if settings['upload_to_server'] and anime_in_db['status'] == 1 and anime_in_db['remote_status'] == 0:
        upload_limiter.acquire()  # 并发上传限制器
        anime = build_anime(sn)
        if anime['failed']:
            err_print(sn, '任务失敗', '從任務列隊中移除, 等待下次更新重試.', status=1)
            upload_quit()

        # 视频信息抓取成功
        anime = anime['anime']
        if not os.path.exists(anime_in_db['local_file_path']):
            # 如果数据库中记录的文件路径已失效
            update_db(anime)
            err_msg_detail = 'title=\"' + anime.get_title() + '\" 本地文件丢失, 從任務列隊中移除, 等待下次更新重試.'
            err_print(sn, '上传失敗', err_msg_detail, status=1)
            upload_quit()

        anime.local_video_path = anime_in_db['local_file_path']  # 告知文件位置
        anime.video_size = anime_in_db['file_size']  # 通過 update_db() 下载状态检查
        anime.video_resolution = anime_in_db['resolution']  # 避免更新时把分辨率变成0

        try:
            if not anime.upload(bangumi_tag):  # 如果上传失败
                err_msg_detail = 'title=\"' + anime.get_title() + '\" 從任務列隊中移除, 等待下次更新重試.'
                err_print(sn, '上传失敗', err_msg_detail, 1)
            else:
                update_db(anime)
                err_print(sn, '任務完成', status=2)
        except BaseException as e:
            err_msg_detail = 'title=\"' + anime.get_title() + '\" 發生未知錯誤, 等待下次更新重試: ' + str(e)
            err_print(sn, '上傳失敗', '異常詳情:\n'+traceback.format_exc(), status=1, display=False)
            err_print(sn, '上傳失敗', err_msg_detail, 1)

        upload_quit()

    # =====下载模块 =====
    thread_limiter.acquire()  # 并发下载限制器
    anime = build_anime(sn)

    if anime['failed']:
        queue.pop(sn)
        processing_queue.remove(sn)
        thread_limiter.release()
        err_print(sn, '任务失敗', '從任務列隊中移除, 等待下次更新重試.', status=1)
        sys.exit(1)

    anime = anime['anime']

    try:
        anime.download(settings['download_resolution'], bangumi_tag=bangumi_tag, rename=rename,
                       realtime_show_file_size=realtime_show_file_size, classify=settings['classify_bangumi'],
                       plex_info=plex_info)
    except BaseException as e:
        # 兜一下各种奇奇怪怪的错误
        err_print(sn, '下載異常', '發生未知錯誤: '+str(e), status=1)
        err_print(sn, '下載異常', '異常詳情:\n'+traceback.format_exc(), status=1, display=False)
        anime.video_size = 0

    if anime.video_size < 5:
        # 下载失败
        queue.pop(sn)
        processing_queue.remove(sn)
        thread_limiter.release()
        err_msg_detail = 'title=\"' + anime.get_title() + '\" 從任務列隊中移除, 等待下次更新重試.'
        err_print(sn, '任务失敗', err_msg_detail, status=1)
        if int(sn) in Config.tasks_progress_rate.keys():
            del Config.tasks_progress_rate[int(sn)]  # 任务失败, 不在监控此任务进度
        sys.exit(1)

    update_db(anime)  # 下载完成后, 更新数据库
    download_cd = threading.Thread(target=download_cd_counter)
    download_cd.start()
    # =====下载模块结束 =====

    # =====上传模块=====
    if settings['upload_to_server']:
        upload_limiter.acquire()  # 并发上传限制器

        try:
            anime.upload(bangumi_tag)  # 上传至服务器
        except BaseException as e:
            # 兜一下各种奇奇怪怪的错误
            err_print(sn, '上傳異常', '發生未知錯誤, 從任務列隊中移除, 等待下次更新重試: ' + str(e), status=1)
            err_print(sn, '上傳異常', '異常詳情:\n'+traceback.format_exc(), status=1, display=False)
            upload_quit()

        update_db(anime)  # 上传完成后, 更新数据库
        upload_limiter.release()  # 并发上传限制器
    # =====上传模块结束=====

    download_cd.join()
    queue.pop(sn)  # 从任务列队中移除
    processing_queue.remove(sn)  # 从当前任务列队中移除 
    err_print(sn, '任務完成', status=2)
    

def download_cd_counter():
    seconds = settings['download_cd']
    while(seconds > 0):
        err_print('', '下載冷卻:', '下載冷卻時間剩餘 ' + str(seconds) + ' 秒', status=0, no_sn=True)
        wait_time = min(30, seconds)
        time.sleep(wait_time)
        seconds -= wait_time
    thread_limiter.release()  # 并发下载限制器


def check_tasks(sn_subset=None):
    """檢查更新並生成下載任務. 回傳需要重試的 sn_list SN 集合 (新集未上架或下載失敗)."""
    check_dict = sn_subset if sn_subset is not None else sn_dict
    need_retry_sns = set()  # 需要重試的 sn_list SN
    for sn in check_dict.keys():
        anime = build_anime(sn)
        if anime['failed']:
            err_print(sn, '更新狀態', '檢查更新失敗, 跳過等待下次檢查', status=1)
            need_retry_sns.add(sn)  # 檢查失敗, 需要重試
            continue
        anime = anime['anime']
        err_print(sn, '更新資訊', '正在檢查《' + anime.get_bangumi_name() + '》')
        episode_list = list(anime.get_episode_list().values())

        if check_dict[sn]['mode'] == 'all':
            # 如果用户选择全部下载 download_mode = 'all'
            for ep in episode_list:  # 遍历剧集列表
                try:
                    db = read_db(ep)
                    #           未下载的   或                设定要上传但是没上传的                         并且  还没在列队中
                    if (db['status'] == 0 or (db['remote_status'] == 0 and settings['upload_to_server'])) and ep not in queue.keys():
                        queue[ep] = check_dict[sn]  # 添加至下载列队
                except IndexError:
                    # 如果数据库中尚不存在此条记录
                    if anime.get_sn() == ep:
                        new_anime = anime  # 如果是本身则不用重复创建实例
                    else:
                        new_anime = build_anime(ep)
                        if new_anime['failed']:
                            err_print(ep, '更新狀態', '更新數據失敗, 跳過等待下次檢查', status=1)
                            continue
                        new_anime = new_anime['anime']
                    insert_db(new_anime)
                    queue[ep] = check_dict[sn]  # 添加至列队
        else:
            if check_dict[sn]['mode'] == 'largest-sn':
                # 如果用户选择仅下载最新上传, download_mode = 'largest_sn', 则对 sn 进行排序
                episode_list.sort()
                latest_sn = episode_list[-1]
                # 否则用户选择仅下载最后剧集, download_mode = 'latest', 即下载网页上显示在最右的剧集
            elif check_dict[sn]['mode'] == 'single':
                latest_sn = sn  # 适配命令行 sn-list 模式
            else:
                latest_sn = episode_list[-1]
            try:
                db = read_db(latest_sn)
                # 未下載的 或 設定要上傳但尚未上傳的，且不在列隊中
                if (db['status'] == 0 or (db['remote_status'] == 0 and settings['upload_to_server'])) and latest_sn not in queue.keys():
                    queue[latest_sn] = check_dict[sn]  # 加入下載列隊
                elif db['status'] != 0:
                    err_print(latest_sn, '更新資訊', '已下載完成，略過')
            except IndexError:
                # 如果数据库中尚不存在此条记录
                if anime.get_sn() == latest_sn:
                    new_anime = anime  # 如果是本身则不用重复创建实例
                else:
                    new_anime = build_anime(latest_sn)
                    if new_anime['failed']:
                        err_print(latest_sn, '更新狀態', '更新數據失敗, 跳過等待下次檢查', status=1)
                        need_retry_sns.add(sn)
                        continue
                    new_anime = new_anime['anime']
                insert_db(new_anime)
                queue[latest_sn] = check_dict[sn]
    return need_retry_sns

        # # sn 解析冷却
        # if settings['parse_sn_cd'] > 0:
        #     err_print("更新資訊", "SN 解析冷卻 " + str(settings['parse_sn_cd']) + " 秒", no_sn=True)
        #     time.sleep(settings['parse_sn_cd'])


def __download_only(sn, dl_resolution='', dl_save_dir='', realtime_show_file_size=False, classify=True, force_download=False, plex_info=None):
    # 仅下载,不操作数据库
    thread_limiter.acquire()
    err_counter = 0

    anime = build_anime(sn)
    if anime['failed']:
        sys.exit(1)
    anime = anime['anime']

    try:
        if dl_resolution:
            anime.download(dl_resolution, dl_save_dir, realtime_show_file_size=realtime_show_file_size, classify=classify, force_download=force_download, plex_info=plex_info)
        else:
            anime.download(settings['download_resolution'], dl_save_dir, realtime_show_file_size=realtime_show_file_size, classify=classify, force_download=force_download, plex_info=plex_info)
    except BaseException as e:
        err_print(sn, '下載異常', '發生未知異常: ' + str(e), status=1)
        err_print(sn, '下載異常', '異常詳情:\n'+traceback.format_exc(), status=1, display=False)
        anime.video_size = 0

    while anime.video_size < 5:
        if err_counter >= 3:
            err_print(sn, '終止任務', 'title=' + anime.get_title()+' 任務失敗達三次! 終止任務!', status=1)
            thread_limiter.release()
            if int(sn) in Config.tasks_progress_rate.keys():
                del Config.tasks_progress_rate[int(sn)]
            return
        else:
            err_print(sn, '任務失敗', 'title=' + anime.get_title() + ' 10s后自動重啓,最多重試三次', status=1)
            err_counter = err_counter + 1
            if int(sn) in Config.tasks_progress_rate.keys():
                Config.tasks_progress_rate[int(sn)]['status'] = '失敗! 重啓中'
            time.sleep(10)
            anime.renew()

            try:
                if dl_resolution:
                    anime.download(dl_resolution, dl_save_dir, realtime_show_file_size=realtime_show_file_size, classify=classify, force_download=force_download, plex_info=plex_info)
                else:
                    anime.download(settings['download_resolution'], dl_save_dir, realtime_show_file_size=realtime_show_file_size, classify=classify, force_download=force_download, plex_info=plex_info)
            except BaseException as e:
                err_print(sn, '下載異常', '發生未知異常: ' + str(e), status=1)
                err_print(sn, '下載異常', '異常詳情:\n'+traceback.format_exc(), status=1, display=False)
                anime.video_size = 0

    # 下載成功, 寫入資料庫 (避免 sn_list 排程重複下載已存在的檔案)
    insert_db(anime)   # 若記錄已存在會跳過 (IntegrityError)
    update_db(anime)   # 更新 status, file_size, local_file_path 等

    download_cd = threading.Thread(target=download_cd_counter)
    download_cd.start()


def __get_info_only(sn):
    thread_limiter.acquire()

    anime = build_anime(sn)
    if anime['failed']:
        sys.exit(1)
    anime = anime['anime']
    anime.set_resolution(resolution)
    anime.get_info()
    download_dir = settings['bangumi_dir']
    if classify:  # 控制是否建立番剧文件夹
        download_dir = os.path.join(download_dir, Config.legalize_filename(anime.get_bangumi_name()))

    if danmu:
        if os.path.exists(download_dir):
            full_filename = os.path.join(download_dir, anime.get_filename()).replace('.' + settings['video_filename_extension'], '.ass')
            d = Danmu(sn, full_filename, Config.read_cookie())
            d.download(settings['danmu_ban_words'])
        else:
            err_print(sn, '彈幕下載異常', '番劇資料夾不存在: ' + download_dir, status=1)

    thread_limiter.release()


def __get_danmu_only(sn, bangumi_name, video_path):
    thread_limiter.acquire()

    download_dir = settings['bangumi_dir']
    if classify:  # 控制是否建立番剧文件夹
        download_dir = os.path.join(download_dir, Config.legalize_filename(bangumi_name))

    if os.path.exists(download_dir):
        d = Danmu(sn, video_path.replace('.' + settings['video_filename_extension'], '.ass'), Config.read_cookie())
        d.download(settings['danmu_ban_words'])
    else:
        err_print(sn, '彈幕下載異常', '番劇資料夾不存在: ' + download_dir, status=1)

    thread_limiter.release()


def __cui(sn, cui_resolution, cui_download_mode, cui_thread_limit, ep_range,
          cui_save_dir='', classify=True, get_info=False, user_cmd=False, realtime_show=True, cui_danmu=False, force_download=False, plex_info=None):
    global thread_limiter
    thread_limiter = threading.Semaphore(cui_thread_limit)

    global danmu
    danmu = cui_danmu

    if realtime_show:
        if cui_thread_limit == 1 or cui_download_mode in ('single', 'latest', 'largest-sn'):
            realtime_show_file_size = True
        else:
            realtime_show_file_size = False
    else:
        realtime_show_file_size = False

    if cui_download_mode == 'single':
        if get_info:
            print('當前模式: 查詢本集資訊\n')
        else:
            print('當前下載模式: 僅下載本集\n')

        if get_info:
            __get_info_only(sn)
        else:
            __download_only(sn, cui_resolution, cui_save_dir, realtime_show_file_size=realtime_show_file_size, classify=classify, force_download=force_download, plex_info=plex_info)

    elif cui_download_mode == 'latest' or cui_download_mode == 'largest-sn':
        if cui_download_mode == 'latest':
            if get_info:
                print('當前模式: 查詢本番劇最後一集資訊\n')
            else:
                print('當前下載模式: 下載本番劇最後一集\n')
        else:
            if get_info:
                print('當前模式: 查詢本番劇最近上傳一集資訊\n')
            else:
                print('當前下載模式: 下載本番劇最近上傳的一集\n')

        anime = build_anime(sn)
        if anime['failed']:
            sys.exit(1)
        anime = anime['anime']

        bangumi_list = list(anime.get_episode_list().values())

        if cui_download_mode == 'largest-sn':
            bangumi_list.sort()

        if get_info:
            __get_info_only(bangumi_list[-1])
        else:
            __download_only(bangumi_list[-1], cui_resolution, cui_save_dir, realtime_show_file_size=realtime_show_file_size, classify=classify, force_download=force_download, plex_info=plex_info)

    elif cui_download_mode == 'all':
        if get_info:
            print('當前模式: 查詢本番劇所有劇集資訊\n')
        else:
            print('當前下載模式: 下載本番劇所有劇集\n')

        anime = build_anime(sn)
        if anime['failed']:
            sys.exit(1)
        anime = anime['anime']

        bangumi_list = list(anime.get_episode_list().values())
        bangumi_list.sort()
        tasks_counter = 0  # 任务计数器
        for anime_sn in bangumi_list:
            if get_info:
                task = threading.Thread(target=__get_info_only, args=(anime_sn,))
            else:
                task = threading.Thread(target=__download_only, args=(anime_sn, cui_resolution, cui_save_dir, realtime_show_file_size, classify, force_download, plex_info))
            task.daemon = True
            thread_tasks.append(task)
            task.start()
            tasks_counter = tasks_counter + 1
            print('添加任务列隊: sn=' + str(anime_sn))
        if get_info:
            print('所有查詢任務已添加至列隊, 共 '+str(tasks_counter)+' 個任務\n')
        else:
            print('所有下載任務已添加至列隊, 共 '+str(tasks_counter)+' 個任務, '+'執行緒數: ' + str(cui_thread_limit) + '\n')

    elif cui_download_mode == 'range':
        if get_info:
            print('當前模式: 查詢本番劇指定劇集資訊\n')
        else:
            print('當前下載模式: 下載本番劇指定劇集\n')

        anime = build_anime(sn)
        if anime['failed']:
            sys.exit(1)
        anime = anime['anime']

        episode_dict = anime.get_episode_list()
        bangumi_ep_list = list(episode_dict.keys())  # 本番剧集列表
        tasks_counter = 0  # 任务计数器
        for ep in ep_range:
            if ep in bangumi_ep_list:
                if get_info:
                    a = threading.Thread(target=__get_info_only, args=(episode_dict[ep],))
                else:
                    a = threading.Thread(target=__download_only, args=(episode_dict[ep], cui_resolution, cui_save_dir, realtime_show_file_size))
                a.daemon = True
                thread_tasks.append(a)
                a.start()
                tasks_counter = tasks_counter + 1
                if get_info:
                    print('添加查詢列隊: sn=' + str(episode_dict[ep]) + ' 《' + anime.get_bangumi_name() + '》 第 ' + ep + ' 集')
                else:
                    print('添加任务列隊: sn='+str(episode_dict[ep])+' 《'+anime.get_bangumi_name()+'》 第 '+ep+' 集')
            else:
                err_print(0, '《'+anime.get_bangumi_name()+'》 第 '+ep+' 集不存在!', status=1, no_sn=True)
        print('所有任務已添加至列隊, 共 '+str(tasks_counter)+' 個任務, '+'執行緒數: ' + str(cui_thread_limit) + '\n')

    elif cui_download_mode == 'sn-range':
        if get_info:
            print('當前模式: 查詢本番劇指定sn範圍資訊\n')
        else:
            print('當前下載模式: 下載本番劇指定sn範圍劇集\n')

        anime = build_anime(sn)
        if anime['failed']:
            sys.exit(1)
        anime = anime['anime']

        # 剧集列表 key value 互换, {'sn', '剧集名'}
        episode_dict = {value:key for key,value in anime.get_episode_list().items()}
        ep_sn_list = list(episode_dict.keys())  # 本番剧集sn列表
        tasks_counter = 0  # 任务计数器
        ep_range = list(map(lambda x: int(x), ep_range))
        for sn in ep_sn_list:
            if sn in ep_range:
                # 如果该 sn 在用户指定的 sn 范围里
                if get_info:
                    a = threading.Thread(target=__get_info_only, args=(sn,))
                else:
                    a = threading.Thread(target=__download_only, args=(sn, cui_resolution, cui_save_dir, realtime_show_file_size))
                a.daemon = True
                thread_tasks.append(a)
                a.start()
                tasks_counter = tasks_counter + 1
                if get_info:
                    print('添加查詢列隊: sn=' + str(sn) + ' 《' + anime.get_bangumi_name() + '》 第 ' + episode_dict[sn] + ' 集')
                else:
                    print('添加任务列隊: sn='+str(sn)+' 《'+anime.get_bangumi_name()+'》 第 ' + episode_dict[sn] + ' 集')
        print('所有任務已添加至列隊, 共 ' + str(tasks_counter) + ' 個任務, ' + '執行緒數: ' + str(cui_thread_limit) + '\n')

    elif cui_download_mode == 'multi':
        if get_info:
            print('當前模式: 查詢指定sn資訊\n')
        else:
            print('當前下載模式: 下載指定sn劇集\n')

        tasks_counter = 0
        for sn in ep_range:
            if get_info:
                a = threading.Thread(target=__get_info_only, args=(sn,))
            else:
                a = threading.Thread(target=__download_only,args=(sn, cui_resolution, cui_save_dir, realtime_show_file_size))
            a.daemon = True
            thread_tasks.append(a)
            a.start()
            tasks_counter = tasks_counter + 1

        print('所有任務已添加至列隊, 共 ' + str(tasks_counter) + ' 個任務, ' + '執行緒數: ' + str(cui_thread_limit) + '\n')

    elif cui_download_mode in ('list', 'sn-list'):
        if get_info:
            # 如果為list模式也仅查询名单中的sn信息, 可用于检查sn是否输入正确
            print('當前模式: 查詢sn_list.txt中指定sn的資訊\n')
            ep_range = Config.read_sn_list().keys()
            for sn in ep_range:
                anime = build_anime(sn)
                if anime['failed']:
                    sys.exit(1)
                anime = anime['anime']
                anime.get_info()
        else:
            if cui_download_mode == 'sn-list':
                print('當前下載模式: 下載sn_list.txt中指定的sn劇集\n')
                for i in sn_dict:
                    sn_dict[i]['mode'] = 'single'
            else:
                print('當前下載模式: 單次下載sn_list.txt中的番劇\n')

            check_tasks()  # 检查更新，生成任务列队
            for sn in queue.keys():  # 遍历任务列队
                processing_queue.append(sn)
                task = threading.Thread(target=worker, args=(sn, queue[sn], realtime_show_file_size))
                task.daemon = True
                thread_tasks.append(task)
                task.start()
                err_print(sn, '加入任务列隊')
            msg = '共 ' + str(len(queue)) + ' 個任務'
            err_print(0, '任務資訊', msg, no_sn=True)
            print()

    elif cui_download_mode == 'danmu':
        tasks_counter = 0
        for anime_db in ep_range:
            if anime_db["status"] == 1:
                if anime_db["anime_name"] is not None \
                and anime_db["local_file_path"] is not None :
                    a = threading.Thread(target=__get_danmu_only,args=(anime_db["sn"], anime_db["anime_name"], anime_db["local_file_path"]))
                    a.daemon = True
                    thread_tasks.append(a)
                    a.start()
                    tasks_counter = tasks_counter + 1
                else:
                    err_print(anime_db["sn"], '彈幕更新失敗', "資料庫不存在番劇名稱或影片路徑", status=1)

        print('所有任務已添加至列隊, 共 ' + str(tasks_counter) + ' 個任務, ' + '執行緒數: ' + str(cui_thread_limit) + '\n')

    __kill_thread_when_ctrl_c()
    kill_gost()  # 结束 gost

    # 结束后执行用户自定义命令
    if user_cmd:
        print()
        os.popen(settings['user_command'])
        err_print(0, '任務完成', '已執行用戶命令', no_sn=True, status=2)

    sys.exit(0)


def __kill_thread_when_ctrl_c():
    # 等待所有任务完成
    for t in thread_tasks:  # 当用户 Ctrl+C 可以 kill 线程
        while True:
            if t.is_alive():
                time.sleep(1)
            else:
                break


def kill_gost():
    if gost_subprocess is not None:
        gost_subprocess.kill()  # 结束 gost


def user_exit(signum, frame):
    err_print(0, '你終止了程序!', '\n', status=1, no_sn=True, prefix='\n\n')
    kill_gost()  # 结束 gost
    sys.exit(255)


def check_new_version():
    # 检查GitHub上是否有新版本
    remote_version = Config.read_latest_version_on_github()
    def parse_version(v):
        return tuple(int(x) for x in v.lstrip('v').split('.'))
    try:
        if parse_version(settings['aniGamerPlus_version']) < parse_version(remote_version['tag_name']):
            msg = '發現GitHub上有新版本: '+remote_version['tag_name']+'\n更新内容:\n'+remote_version['body']+'\n'
            err_print(0, msg, status=1, no_sn=True)
    except (ValueError, TypeError):
        pass


def __init_proxy():
    if settings['use_gost']:
        print('使用代理連接動畫瘋, 使用擴展的代理協議')
        # 需要使用 gost 的情况
        # 寻找 gost
        check_gost = subprocess.Popen('gost -h', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check_gost.stderr.readlines():  # 查找 gost 是否已放入系统 path
            gost_path = 'gost'
        else:
            # print('没有在系统PATH中发现gost，尝试在所在目录寻找')
            if 'Windows' in platform.system():
                gost_path = os.path.join(working_dir, 'gost.exe')
            else:
                gost_path = os.path.join(working_dir, 'gost')
            if not os.path.exists(gost_path):
                err_print(0, '當前代理使用擴展協議, 需要使用gost, 但是gost未找到', status=1, no_sn=True)
                raise FileNotFoundError  # 如果本地目录下也没有找到 gost 则丢出异常
        # 构造 gost 命令
        gost_cmd = [gost_path, '-L=:'+str(gost_port), '-F=' + settings['proxy']]  # 本地监听端口 34173

        def run_gost():
            # gost 线程
            global gost_subprocess
            gost_subprocess = subprocess.Popen(gost_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            gost_subprocess.communicate()

        run_gost_threader = threading.Thread(target=run_gost)
        run_gost_threader.daemon = True
        run_gost_threader.start()  # 启动 gost
        time.sleep(3)  # 给时间让 gost 启动

    else:
        print('使用代理連接動畫瘋, 使用http/https/socks5協議')


def do_request(url, headers, cookies, params=None):
    # 帶用戶 cookie 的請求走 BahaRequest: 統一 UA 並處理 BAHARUNE 一次性輪替寫回
    if BahaRequest.available():
        return BahaRequest.get(url, headers=headers, cookies=cookies, params=params)
    return requests.get(url, headers=headers, cookies=cookies, params=params)


def parse_anime(soup, animes, headers, cookies):
    if soup.text.find("目前沒有訂閱內容") != -1:
        return False
    for animeInfo in soup.select_one(".theme-list-block").select("a"):
        response = do_request(f"https://ani.gamer.com.tw/{animeInfo['href']}", headers, cookies)
        sn = response.url.split("=")[-1]
        name = animeInfo.select_one(".theme-name").text
        animes.append({"sn": sn, "name": name})
    return True


def export_my_anime():
    from bs4 import BeautifulSoup

    url = "https://ani.gamer.com.tw/mygather.php"
    # 不硬編 user-agent: BahaRequest 會統一帶 settings['ua'] (cookie 輪替要求 UA 前後一致)
    header = {
        'accept':
        'application/json',
        'origin':
        'https://ani.gamer.com.tw',
        'authority':
        'ani.gamer.com.tw',
    }

    cookies = Config.read_cookie()
    if not cookies:
        err_print(0, "請先設定cookie後再執行此指令", status=1, no_sn=True)
        return

    page = 1
    animes = []
    while True:
        params = {'page': page, 'sort': 0}
        bahamygatherPage = do_request(url, headers=header, cookies=cookies, params=params)
        if bahamygatherPage.status_code == requests.codes.ok:
            soup = BeautifulSoup(bahamygatherPage.text, 'html.parser')
            if not parse_anime(soup, animes, header, cookies):
                break
        else:
            err_print(0, f"匯入我的動畫失敗，狀態碼{bahamygatherPage.status_code}", status=1, no_sn=True)
        page += 1

    with open("my_anime.txt", "w", encoding="utf-8") as f:
        for anime in animes:
            f.write(f"{anime['sn']} all <{anime['name']}>\n")


def run_dashboard():
    # 检测端口是否占用
    if not port_is_available(settings['dashboard']['port']):
        err_print(0, 'Web 控制面板啟動失敗', 'Port 已被佔用！請至設定檔更換', status=1, no_sn=True)
        return

    from Dashboard.Server import run as dashboard
    server = threading.Thread(target=dashboard)
    server.daemon = True
    server.start()
    if settings['dashboard']['SSL']:
        dashboard_address = 'https://'
    else:
        dashboard_address = 'http://'
    if settings['dashboard']['host'] == '0.0.0.0':
        host = Config.get_local_ip()
        dashboard_address = '【開放外部訪問】訪問地址: ' + dashboard_address
    else:
        host = settings['dashboard']['host']
        dashboard_address = '訪問地址: ' + dashboard_address

    dashboard_address = dashboard_address + host + ':' + str(settings['dashboard']['port'])
    err_print(0, 'Web控制面板已啓動', dashboard_address, no_sn=True, status=2)


from Schedule import AnimeSchedule

signal.signal(signal.SIGINT, user_exit)
signal.signal(signal.SIGTERM, user_exit)
settings = Config.read_settings()
working_dir = settings['working_dir']
db_path = os.path.join(working_dir, 'aniGamer.db')
queue = {}  # 储存 sn 相关信息, {'tag': TAG, 'rename': RENAME}, rename,
processing_queue = []
thread_limiter = threading.Semaphore(settings['multi-thread'])  # 下载并发限制器
upload_limiter = threading.Semaphore(settings['multi_upload'])  # 并发上传限制器
db_locker = threading.Semaphore(1)
thread_tasks = []
gost_subprocess = None  # 存放 gost 的 subprocess.Popen 对象, 用于结束时 kill gost
gost_port = gost_port()  # gost 端口
sn_dict = Config.read_sn_list()
anime_schedule = None  # 排程實例, 供 Dashboard 使用
danmu = settings['danmu']

if __name__ == '__main__':
    if settings['check_latest_version']:
        check_new_version()  # 检查新版
    version_msg = '當前aniGamerPlus版本: ' + settings['aniGamerPlus_version']
    print(version_msg)

    # 初始化 sqlite3 数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS anime ('
                   'sn INTEGER PRIMARY KEY NOT NULL,'
                   'title VARCHAR(100) NOT NULL,'
                   'anime_name VARCHAR(100) NOT NULL, '
                   'episode VARCHAR(10) NOT NULL,'
                   'status TINYINT DEFAULT 0,'
                   'remote_status INTEGER DEFAULT 0,'
                   'resolution INTEGER DEFAULT 0,'
                   'file_size INTEGER DEFAULT 0,'
                   'local_file_path VARCHAR(500),'
                   "[CreatedTime] TimeStamp NOT NULL DEFAULT (datetime('now','localtime')))")
    conn.commit()
    conn.close()

    if len(sys.argv) > 1:  # 支持命令行使用
        parser = argparse.ArgumentParser()
        parser.add_argument('--sn', '-s', type=int, help='視頻sn碼(數字)')
        parser.add_argument('--resolution', '-r', type=int, help='指定下載清晰度(數字)', choices=[360, 480, 540, 576, 720, 1080])
        parser.add_argument('--download_mode', '-m', type=str, help='下載模式', default='single',
                            choices=['single', 'latest', 'largest-sn', 'multi', 'all', 'range', 'list', 'sn-list', 'sn-range', 'db'])
        parser.add_argument('--thread_limit', '-t', type=int, help='最高并發下載數(數字)')
        parser.add_argument('--current_path', '-c', action='store_true', help='下載到當前工作目錄')
        parser.add_argument('--episodes', '-e', type=str, help='僅下載指定劇集')
        parser.add_argument('--no_classify', '-n', action='store_true', help='不建立番劇資料夾')
        parser.add_argument('--user_command', '-u', action='store_true', help='所有下載完成后執行用戶命令')
        parser.add_argument('--information_only', '-i', action='store_true', help='僅查詢資訊，可搭配 -d 更新彈幕')
        parser.add_argument('--danmu', '-d', action='store_true', help='以 .ass 下載彈幕')
        parser.add_argument('--my_anime', action='store_true', help='匯出「我的動畫」至my_anime.txt')
        arg = parser.parse_args()

        if arg.my_anime:
            export_my_anime()
            sys.exit(0)

        if (arg.download_mode not in ('list', 'multi', 'sn-list', 'db')) and arg.sn is None:
            err_print(0, '參數錯誤', '非 list/multi 模式需要提供 sn ', no_sn=True, status=1)
            sys.exit(1)

        save_dir = ''
        download_mode = arg.download_mode
        if arg.current_path:
            save_dir = os.getcwd()
            info = '使用命令行模式, 指定下載到當前目錄: '
            print(info + '\n    ' + save_dir)
            err_print(0, info + save_dir, no_sn=True, display=False)
        else:
            info = '使用命令列模式，檔案將儲存在設定檔指定的目錄下: '
            print(info + '\n    ' + settings['bangumi_dir'])
            err_print(0, info + settings['bangumi_dir'], no_sn=True, display=False)

        classify = True
        if arg.no_classify:
            classify = False
            print('將不會建立番劇資料夾')

        if not arg.episodes and arg.download_mode == 'range':
            err_print(0, 'ERROR: 當前為指定範圍模式, 但範圍未指定!', status=1, no_sn=True)
            sys.exit(1)

        download_episodes = []
        if arg.episodes or arg.download_mode == 'sn-list':
            if arg.download_mode == 'multi':
                # 如果此时为 multi 模式, 则 download_episodes 装的是 sn 码
                for i in arg.episodes.split(','):
                    if re.match(r'^\d+$', i):
                        download_episodes.append(int(i))
                if arg.sn:
                    download_episodes.append(arg.sn)

            elif arg.download_mode == 'sn-list':
                # 如果此时为 sn-list 模式, 则 download_episodes 装的是 sn_list.txt 里的 sn 码
                download_episodes = list(Config.read_sn_list().keys())

            else:
                for i in arg.episodes.split(','):
                    if re.match(r'^\d+-\d+$', i):
                        episodes_range_start = int(i.split('-')[0])
                        episodes_range_end = int(i.split('-')[1])
                        if episodes_range_start > episodes_range_end:  # 如果有zz从大到小写
                            episodes_range_start, episodes_range_end = episodes_range_end, episodes_range_start
                        download_episodes.extend(list(range(episodes_range_start, episodes_range_end + 1)))
                    if re.match(r'^\d+$', i):
                        download_episodes.append(int(i))
                if arg.download_mode != 'sn-range':
                    download_mode = 'range'  # 如果带 -e 参数没有指定 multi 模式, 则默认为 range 模式

            download_episodes = list(set(download_episodes))  # 去重复
            download_episodes.sort()  # 排序, 任务将会按集数顺序下载
            # 转为 str, 方便作为 Anime.get_episode_list() 的 key
            download_episodes = list(map(lambda x: str(x), download_episodes))

        if not arg.resolution:
            resolution = settings['download_resolution']
            print('未設定下載解析度，將使用設定檔指定的畫質: ' + resolution + 'P')
        else:
            if arg.download_mode in ('sn-list', 'list'):
                err_print(0,'無效參數:', 'list 及 sn-list 模式無法通過命令行指定清晰度', 1, no_sn=True, display_time=False)
                resolution = settings['download_resolution']
                print('將使用設定檔指定的畫質: ' + resolution + 'P')
            else:
                resolution = str(arg.resolution)
                print('指定下載解析度: ' + resolution + 'P')

        if arg.download_mode == "db":
            download_mode = "danmu"
            download_episodes = read_db_all()

        if arg.information_only:
            # 为避免排版混乱, 仅显示信息时强制为单线程
            thread_limit = 1
            thread_limiter = threading.Semaphore(thread_limit)
        else:
            if arg.thread_limit:
                # 用戶設定并發數
                if arg.thread_limit > Config.get_max_multi_thread():
                    # 是否超过最大允许线程数
                    thread_limit = Config.get_max_multi_thread()
                else:
                    thread_limit = arg.thread_limit
            else:
                thread_limit = settings['multi-thread']

        if settings['use_proxy']:
            __init_proxy()

        if arg.user_command:
            user_command = True
        else:
            user_command = False

        if arg.danmu:
            danmu = True

        Config.test_cookie()  # 测试cookie
        __cui(arg.sn, resolution, download_mode, thread_limit, download_episodes, save_dir, classify,
              get_info=arg.information_only, user_cmd=user_command, cui_danmu=danmu)

    err_print(0, '自動模式啓動aniGamerPlus '+version_msg, no_sn=True, display=False)
    err_print(0, '工作目錄: ' + working_dir, no_sn=True, display=False)

    if settings['use_proxy']:
        __init_proxy()

    if settings['use_dashboard']:
        run_dashboard()

    def _build_title_hints_map(sn_dict):
        """從 sn_dict 建構 {sn: [title_hints]} 對照表"""
        result = {}
        for sn, info in sn_dict.items():
            hints = []
            plex = info.get('plex')
            if plex:
                if plex.get('clean_title'):
                    hints.append(plex['clean_title'])
                if plex.get('folder_name'):
                    hints.append(plex['folder_name'])
            elif info.get('rename'):
                hints.append(info['rename'])
            if hints:
                result[sn] = hints
        return result

    def _start_queued_workers():
        """啟動 queue 中等待的下載任務, 回傳新啟動數量"""
        counter = 0
        if queue:
            for task_sn in queue.keys():
                if task_sn not in processing_queue:
                    t = threading.Thread(target=worker, args=(task_sn, queue[task_sn]))
                    t.daemon = True
                    t.start()
                    processing_queue.append(task_sn)
                    counter += 1
                    err_print(task_sn, '加入任務列隊')
        return counter

    def _do_check_and_start(sns_subset=None):
        """執行檢查 + 啟動下載, 回傳 (新任務數, 需要重試的SN集合)"""
        Config.test_cookie()
        need_retry = check_tasks(sns_subset)
        count = _start_queued_workers()
        return count, need_retry

    # ========== 智慧排程: Timer + Time Table ==========
    if settings.get('smart_schedule', False):
        anime_schedule = AnimeSchedule(
            settings['ua'], db_path=db_path,
            schedule_delay=settings.get('schedule_delay', 0)
        )
        schedule_ok = anime_schedule.fetch_schedule()
        title_hints_map = _build_title_hints_map(sn_dict)
        time_table = anime_schedule.build_time_table(
            sn_dict, settings.get('schedule_delay', 0), title_hints_map)
        triggered = set()  # {(sn, day, trigger_time)} 已觸發的任務
        pending_retry = {}  # {sn: {'next': datetime, 'attempt': int, 'title': str}}
        RETRY_INTERVALS = [600, 1800, 3600]  # 10分鐘, 30分鐘, 60分鐘
        last_fallback_check = time.time()
        last_schedule_refresh = time.time()
        day_names = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']

        def _format_schedule_entry(info):
            """格式化排程條目: 播出時間 + delay 資訊"""
            line = day_names[info['day']] + ' ' + info['time']
            if info.get('pinned'):
                line += ' → ' + info['trigger_time'] + ' (手動覆寫)'
            elif info['trigger_time'] != info['time']:
                line += ' → ' + info['trigger_time'] + ' (含延遲)'
            line += ' 《' + info['title'] + '》'
            return line

        def _prefill_triggered(tt, trig_set):
            """將今天已過時間的排程預填入 triggered, 避免啟動時誤觸發"""
            now = datetime.now()
            for sn, info in tt.items():
                if now.weekday() == info['day'] and \
                        (now.hour, now.minute, now.second) > \
                        (info['trigger_hour'], info['trigger_minute'], info['trigger_second']):
                    trig_set.add((sn, info['day'], info['trigger_time']))

        def _apply_overrides(tt, trig_set):
            """套用 Dashboard 的排程覆寫，並移除已觸發標記以重新判定"""
            with Config.schedule_overrides_lock:
                overrides = dict(Config.schedule_overrides)
            for sn, ov in overrides.items():
                if sn not in tt:
                    continue
                tt[sn]['day'] = ov['day']
                tt[sn]['trigger_hour'] = ov['hour']
                tt[sn]['trigger_minute'] = ov['minute']
                tt[sn]['trigger_second'] = ov['second']
                sec_str = '{:02d}:{:02d}'.format(ov['hour'], ov['minute'])
                if ov['second']:
                    sec_str += ':{:02d}'.format(ov['second'])
                tt[sn]['trigger_time'] = sec_str
                tt[sn]['pinned'] = True
                # 移除該 SN 的所有已觸發標記（時間已改，需重新判定）
                trig_set.discard((sn, ov['day'], sec_str))
                to_remove = [t for t in trig_set if t[0] == sn]
                for t in to_remove:
                    trig_set.discard(t)

        def _sync_schedule_status(tt, trig_set, retry_dict):
            """將排程狀態同步至 Config，供 Dashboard 讀取"""
            now = datetime.now()
            status = {}
            for sn, info in tt.items():
                task_id = (sn, info['day'], info['trigger_time'])
                if sn in retry_dict:
                    r = retry_dict[sn]
                    s = 'retrying'
                    retry_attempt = r['attempt'] + 1
                    retry_next = r['next'].isoformat()
                elif task_id in trig_set:
                    s = 'triggered'
                    retry_attempt = 0
                    retry_next = None
                elif now.weekday() == info['day']:
                    s = 'pending'
                    retry_attempt = 0
                    retry_next = None
                else:
                    s = 'not_today'
                    retry_attempt = 0
                    retry_next = None
                status[sn] = {
                    'title': info.get('title', ''),
                    'day': info['day'],
                    'time': info.get('time', ''),
                    'trigger_time': info['trigger_time'],
                    'trigger_hour': info['trigger_hour'],
                    'trigger_minute': info['trigger_minute'],
                    'trigger_second': info['trigger_second'],
                    'status': s,
                    'retry_attempt': retry_attempt,
                    'retry_next': retry_next,
                    'pinned': info.get('pinned', False),
                }
            Config.schedule_status = status

        # 印出時間表
        if time_table:
            _apply_overrides(time_table, triggered)
            err_print(0, '排程模式', '時間表已建立 (' + str(len(time_table)) + ' 項):', no_sn=True)
            for sn, info in sorted(time_table.items(), key=lambda x: (x[1]['day'], x[1]['trigger_time'])):
                err_print(sn, '排程', _format_schedule_entry(info))
            _prefill_triggered(time_table, triggered)
            if triggered:
                err_print(0, '排程模式', '已略過 ' + str(len(triggered)) + ' 個今日已過時間的排程', no_sn=True)
            _sync_schedule_status(time_table, triggered, pending_retry)
        else:
            err_print(0, '排程模式', '無排程項目, 將使用 fallback 週期檢查', no_sn=True)

        if not schedule_ok:
            # 排程表抓取失敗 (如 WAF 403): 立即全量檢查一次, 避免空等 fallback 週期
            err_print(0, '排程模式',
                      '排程表抓取失敗, 立即執行一次全量檢查, 之後每 15 分鐘重試抓取排程表',
                      status=1, no_sn=True)
            count, _ = _do_check_and_start()
            err_print(0, '更新資訊',
                      '添加了 ' + str(count) + ' 個新任務, 列隊中共 '
                      + str(len(processing_queue)) + ' 個', no_sn=True)
            last_fallback_check = time.time()

        while True:
            now = datetime.now()

            # --- sn_list 變更 / Dashboard 強制刷新 → 重建時間表 ---
            if Config.schedule_wake.is_set():
                Config.schedule_wake.clear()
                sn_dict = Config.read_sn_list()
                settings = Config.read_settings()
                anime_schedule._schedule_delay = settings.get('schedule_delay', 0)
                schedule_ok = anime_schedule.fetch_schedule(force=True)
                title_hints_map = _build_title_hints_map(sn_dict)
                time_table = anime_schedule.build_time_table(
                    sn_dict, settings.get('schedule_delay', 0), title_hints_map)
                _apply_overrides(time_table, triggered)
                last_schedule_refresh = time.time()
                err_print(0, '排程模式',
                          '時間表已更新 (' + str(len(time_table)) + ' 項):', no_sn=True)
                for sn_t, info_t in sorted(time_table.items(), key=lambda x: (x[1]['day'], x[1]['trigger_time'])):
                    err_print(sn_t, '排程', _format_schedule_entry(info_t))
                _prefill_triggered(time_table, triggered)
                _sync_schedule_status(time_table, triggered, pending_retry)

            # --- Dashboard 強制檢查 ---
            if Config.force_check_sns:
                force_sns = {}
                for sn in list(Config.force_check_sns):
                    if sn in sn_dict:
                        force_sns[sn] = sn_dict[sn]
                    Config.force_check_sns.discard(sn)
                if force_sns:
                    err_print(0, '強制檢查', str(len(force_sns)) + ' 個番劇', no_sn=True)
                    count, _ = _do_check_and_start(force_sns)

            # --- 時間表比對 (每秒比對, triggered set 防重複) ---
            matched = {}
            for sn, info in time_table.items():
                task_id = (sn, info['day'], info['trigger_time'])
                if task_id in triggered:
                    continue
                if now.weekday() != info['day']:
                    continue
                # 秒級精度比對: 現在時間 >= 觸發時間
                if (now.hour, now.minute, now.second) >= \
                        (info['trigger_hour'], info['trigger_minute'], info['trigger_second']):
                    triggered.add(task_id)
                    matched[sn] = sn_dict.get(sn, {})
                    err_print(sn, '排程觸發',
                              '《' + info['title'] + '》播出時間到達 (' + info['trigger_time'] + ')')

            if matched:
                if settings.get('read_sn_list_when_checking_update'):
                    sn_dict = Config.read_sn_list()
                if settings.get('read_config_when_checking_update'):
                    settings = Config.read_settings()
                    anime_schedule._schedule_delay = settings.get('schedule_delay', 0)
                danmu = settings['danmu']
                count, need_retry = _do_check_and_start(matched)
                err_print(0, '更新資訊',
                          '添加了 ' + str(count) + ' 個新任務, 列隊中共 '
                          + str(len(processing_queue)) + ' 個', no_sn=True)
                # 檢查失敗的 SN → 加入重試佇列
                for sn in need_retry:
                    if sn in matched and sn not in pending_retry:
                        title = time_table[sn]['title'] if sn in time_table else ''
                        next_dt = now + timedelta(seconds=RETRY_INTERVALS[0])
                        pending_retry[sn] = {'next': next_dt, 'attempt': 0, 'title': title}
                        err_print(sn, '排程重試',
                                  '《' + title + '》檢查失敗, '
                                  + str(RETRY_INTERVALS[0] // 60) + ' 分鐘後重試')
                # 排程觸發但完全無新任務 → 可能新集未上架, 加入重試
                if count == 0:
                    for sn in matched:
                        if sn not in pending_retry:
                            title = time_table[sn]['title'] if sn in time_table else ''
                            next_dt = now + timedelta(seconds=RETRY_INTERVALS[0])
                            pending_retry[sn] = {'next': next_dt, 'attempt': 0, 'title': title}
                            err_print(sn, '排程重試',
                                      '《' + title + '》未找到新集數, '
                                      + str(RETRY_INTERVALS[0] // 60) + ' 分鐘後重試')
                _sync_schedule_status(time_table, triggered, pending_retry)

            # --- 重試佇列檢查 ---
            retry_done = []
            for sn, retry_info in pending_retry.items():
                if now >= retry_info['next']:
                    err_print(sn, '排程重試',
                              '《' + retry_info['title'] + '》第 '
                              + str(retry_info['attempt'] + 1) + ' 次重試')
                    retry_subset = {sn: sn_dict[sn]} if sn in sn_dict else {}
                    if retry_subset:
                        r_count, _ = _do_check_and_start(retry_subset)
                        if r_count > 0:
                            err_print(sn, '排程重試',
                                      '《' + retry_info['title'] + '》重試成功, 已加入下載')
                            retry_done.append(sn)
                        else:
                            retry_info['attempt'] += 1
                            if retry_info['attempt'] >= len(RETRY_INTERVALS):
                                err_print(sn, '排程重試',
                                          '《' + retry_info['title'] + '》已達重試上限, 放棄', status=1)
                                retry_done.append(sn)
                            else:
                                interval = RETRY_INTERVALS[retry_info['attempt']]
                                retry_info['next'] = now + timedelta(seconds=interval)
                                err_print(sn, '排程重試',
                                          '《' + retry_info['title'] + '》仍未上架, '
                                          + str(interval // 60) + ' 分鐘後再試')
                    else:
                        retry_done.append(sn)  # SN 已從 sn_list 移除
            for sn in retry_done:
                del pending_retry[sn]
            if retry_done:
                _sync_schedule_status(time_table, triggered, pending_retry)

            # --- Fallback: 全量檢查 (不在排程表中的 SN) ---
            fallback_freq = settings.get('schedule_fallback_frequency', 1440) * 60
            if (time.time() - last_fallback_check) >= fallback_freq:
                last_fallback_check = time.time()
                err_print(0, '排程模式', '執行全量 fallback 檢查', no_sn=True)
                sn_dict = Config.read_sn_list()
                settings = Config.read_settings()
                danmu = settings['danmu']
                count, _ = _do_check_and_start()

            # --- 定期重新抓取排程表 (正常每小時; 抓取失敗時每 15 分鐘重試) ---
            refresh_interval = 3600 if schedule_ok else 900
            if (time.time() - last_schedule_refresh) >= refresh_interval:
                was_ok = schedule_ok
                schedule_ok = anime_schedule.fetch_schedule()
                last_schedule_refresh = time.time()
                if schedule_ok:
                    title_hints_map = _build_title_hints_map(sn_dict)
                    time_table = anime_schedule.build_time_table(
                        sn_dict, settings.get('schedule_delay', 0), title_hints_map)
                    _apply_overrides(time_table, triggered)
                    err_print(0, '排程模式', '排程表已刷新 (' + str(len(time_table)) + ' 項)', no_sn=True)
                    _prefill_triggered(time_table, triggered)
                    if not was_ok:
                        # 排程表恢復: 全量檢查一次, 補上失效期間可能漏掉的更新
                        err_print(0, '排程模式', '排程表已恢復, 執行一次全量檢查補漏', status=2, no_sn=True)
                        count, _ = _do_check_and_start()
                        last_fallback_check = time.time()
                    _sync_schedule_status(time_table, triggered, pending_retry)

            # --- 週次重置已觸發清單 ---
            if now.weekday() == 0 and now.hour == 0 and now.minute == 0:
                triggered.clear()
                with Config.schedule_overrides_lock:
                    Config.schedule_overrides.clear()
                _sync_schedule_status(time_table, triggered, pending_retry)

            time.sleep(1)

    # ========== 非排程模式: 原始週期輪詢 ==========
    while True:
        print()
        err_print(0, '開始更新', no_sn=True)
        Config.test_cookie()
        if settings['read_sn_list_when_checking_update']:
            sn_dict = Config.read_sn_list()
        if settings['read_config_when_checking_update']:
            settings = Config.read_settings()
        danmu = settings['danmu']
        check_tasks()
        count = _start_queued_workers()
        err_print(0, '更新資訊',
                  '添加了 ' + str(count) + ' 個新任務, 列隊中共 '
                  + str(len(processing_queue)) + ' 個', no_sn=True)
        err_print(0, '更新終了', no_sn=True)
        for i in range(settings['check_frequency'] * 60):
            if Config.force_check_sns:
                break
            time.sleep(1)
