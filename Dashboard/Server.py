#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Time    : 2019/6/26 16:12
# @Author  : Miyouzi
# @File    : Server.py
# @Software: PyCharm

# 非阻塞
from gevent import monkey; monkey.patch_all()
from gevent import spawn

import json, sys, os, re, time
import threading, traceback
from datetime import datetime

from aniGamerPlus import Config
from flask import Flask, request, jsonify
from flask import render_template
from flask_basicauth import BasicAuth
from aniGamerPlus import __cui as cui
import logging, termcolor
from ColorPrint import err_print
from logging.handlers import TimedRotatingFileHandler
import mimetypes
import ssl
from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler

mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/x-javascript', '.js')
template_path = os.path.join(Config.get_working_dir(), 'Dashboard', 'templates')
static_path = os.path.join(Config.get_working_dir(), 'Dashboard', 'static')
app = Flask(__name__, template_folder=template_path, static_folder=static_path)
app.debug = False

# 日志处理
# logger = logging.getLogger('werkzeug')
logger = logging.getLogger('geventwebsocket')
logging.basicConfig(level=logging.INFO)  # 记录访问
web_log_path = os.path.join(Config.get_working_dir(), 'logs', 'web.log')
handler = TimedRotatingFileHandler(filename=web_log_path, when='midnight', backupCount=7, encoding='utf-8')
handler.suffix = '%Y-%m-%d.log'
handler.extMatch = re.compile(r'^\d{4}-\d{2}-\d{2}.log')
logger.addHandler(handler)
logger.propagate = False  # 不在控制台上输出



# 处理 Flask 写日志到文件带有颜色控制符的问题
def colored(text, color=None, on_color=None, attrs=None):
    who_invoked = traceback.extract_stack()[-2][2]  # 函数调用人
    if who_invoked == 'log_request':
        # 如果是来自 Flask/werkzeug 的调用
        return text
    else:
        # 来自其他的调用正常高亮
        COLORS = termcolor.COLORS
        HIGHLIGHTS = termcolor.HIGHLIGHTS
        ATTRIBUTES = termcolor.ATTRIBUTES
        RESET = termcolor.RESET
        if os.getenv('ANSI_COLORS_DISABLED') is None:
            fmt_str = '\033[%dm%s'
            if color is not None:
                text = fmt_str % (COLORS[color], text)
            if on_color is not None:
                text = fmt_str % (HIGHLIGHTS[on_color], text)
            if attrs is not None:
                for attr in attrs:
                    text = fmt_str % (ATTRIBUTES[attr], text)
            text += RESET
        return text


termcolor.colored = colored
app.logger.addHandler(handler)


# 读取web需要的配置名称列表
id_list_path = os.path.join(Config.get_working_dir(), 'Dashboard', 'static', 'js', 'settings_id_list.js')
with open(id_list_path, 'r', encoding='utf-8') as f:
    id_list = re.sub(r'(var id_list\s*=\s*|\s*\n?)', '', f.read()).replace('\'', '"')
    id_list = json.loads(id_list)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/monitor')
def monitor():
    return render_template('monitor.html')


@app.route('/data/config.json', methods=['GET'])
def config():
    settings = Config.read_settings()
    web_settings = {}
    for id in id_list:
        web_settings[id] = settings[id]  # 仅返回 web 需要的配置

    return jsonify(web_settings)


@app.route('/uploadConfig', methods=['POST'])
def recv_config():
    data = json.loads(request.get_data(as_text=True))
    new_settings = Config.read_settings()
    for id in id_list:
        new_settings[id] = data[id]  # 更新配置
    Config.write_settings(new_settings)  # 保存配置
    err_print(0, 'Dashboard', '通過 Web 控制臺更新了 config.json', no_sn=True, status=2)
    return '{"status":"200"}'


@app.route('/manualTask', methods=['POST'])
def manual_task():
    data = json.loads(request.get_data(as_text=True))
    settings = Config.read_settings()

    # 下载清晰度
    if data['resolution'] not in ('360', '480', '540', '720', '1080'):
        # 如果不是合法清晰度
        resolution = settings['download_resolution']
    else:
        resolution = data['resolution']

    # 下载模式
    if data['mode'] not in ('single', 'latest', 'all', 'largest-sn'):
        mode = 'single'
    else:
        mode = data['mode']

    # 下载线程数
    if data['thread']:
        thread = int(data['thread'])
    else:
        thread = 1
    if thread > Config.get_max_multi_thread():
        # 是否超过最大允许线程数
        thread_limit = Config.get_max_multi_thread()
    else:
        thread_limit = thread

    def run_cui():
        cui(data['sn'], resolution, mode, thread_limit, [], classify=data['classify'], realtime_show=False, cui_danmu=data['danmu'])

    server = threading.Thread(target=run_cui)
    err_print(0, 'Dashboard', '通過 Web 控制臺下達了手動任務', no_sn=True, status=2)
    server.start()  # 启动手动任务线程
    return '{"status":"200"}'


@app.route('/data/sn_list', methods=['GET'])
def show_sn_list():
    return Config.get_sn_list_content()


@app.route('/data/tasks_progress', methods=['GET'])
def tasks_progress():
    """回傳任務進度資料供前端輪詢 (取代原 WebSocket 方案)"""
    return jsonify(Config.tasks_progress_rate)


@app.route('/data/recent_logs', methods=['GET'])
def recent_logs():
    """回傳今日最近 N 行日誌"""
    n = request.args.get('n', 80, type=int)
    n = min(n, 300)
    log_path = os.path.join(Config.get_working_dir(), 'logs', datetime.now().strftime("%Y-%m-%d") + '.log')
    if not os.path.exists(log_path):
        return jsonify({'lines': []})
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        lines = [l.rstrip('\n\r') for l in all_lines[-n:]]
    except Exception:
        lines = []
    return jsonify({'lines': lines})


@app.route('/sn_list', methods=['POST'])
def set_sn_list():
    data = request.get_data(as_text=True)
    Config.write_sn_list(data)
    err_print(0, 'Dashboard', '通過 Web 控制臺更新了 sn_list', no_sn=True, status=2)
    return '{"status":"200"}'


_schedule_cache = None  # 快取排程實例, 避免每次開啟頁面都重新抓取

@app.route('/data/schedule', methods=['GET'])
def get_schedule():
    """回傳排程資料供前端顯示"""
    global _schedule_cache
    try:
        from aniGamerPlus import sn_dict
        settings = Config.read_settings()
        # 優先使用快取的排程實例 (內建 1 小時快取 TTL)
        if _schedule_cache is None:
            from Schedule import AnimeSchedule
            _schedule_cache = AnimeSchedule(settings.get('ua', ''), schedule_delay=0)
        schedule = _schedule_cache
        schedule.fetch_schedule()
        data = schedule.get_schedule_data()
        # 標記哪些項目在 sn_list 中 (透過 SN 直接匹配 + 標題比對)
        sn_set = set(sn_dict.keys()) if sn_dict else set()
        # 從 sn_dict 收集所有標題提示 (clean_title, folder_name, rename)
        title_hints = set()
        if sn_dict:
            for sn_info in sn_dict.values():
                plex = sn_info.get('plex')
                if plex:
                    if plex.get('clean_title'):
                        title_hints.add(plex['clean_title'])
                    if plex.get('folder_name'):
                        title_hints.add(plex['folder_name'])
                elif sn_info.get('rename'):
                    title_hints.add(sn_info['rename'])
        for item in data.get('items', []):
            if item['sn'] in sn_set:
                item['in_sn_list'] = True
            else:
                # 用標題子字串比對
                matched = False
                item_title = item.get('title', '')
                for hint in title_hints:
                    if hint in item_title or item_title in hint:
                        matched = True
                        break
                item['in_sn_list'] = matched
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e), 'last_fetch': None, 'schedule': {}, 'items': []})


@app.route('/data/anime_first_sn', methods=['GET'])
def get_anime_first_sn():
    """查詢動畫第一集 SN 和標題"""
    sn = request.args.get('sn', '')
    if not sn or not sn.isdigit():
        return jsonify({'error': '無效的 SN'}), 400
    try:
        import requests as req_lib
        from bs4 import BeautifulSoup
        settings = Config.read_settings()
        ua = settings.get('ua', '')
        cookie_str = Config.read_cookie()
        headers = {'User-Agent': ua}
        if cookie_str:
            headers['Cookie'] = cookie_str
        url = 'https://ani.gamer.com.tw/animeVideo.php?sn=' + sn
        resp = req_lib.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.content, 'html.parser')
        # 提取標題
        anime_title = ''
        title_el = soup.find('h1')
        if title_el:
            anime_title = title_el.get_text(strip=True)
            anime_title = re.sub(r'\s*\[.+?\]\s*$', '', anime_title)
        # 從劇集列表中找最小 SN (第一集)
        first_sn = int(sn)
        season_section = soup.find('section', 'season')
        if season_section:
            for a in season_section.find_all('a'):
                href = a.get('href', '')
                sn_match = re.findall(r'sn=(\d+)', href)
                if sn_match:
                    ep_sn = int(sn_match[0])
                    if ep_sn < first_sn:
                        first_sn = ep_sn
        return jsonify({
            'first_sn': first_sn,
            'title': anime_title,
            'query_sn': int(sn)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _find_sn_by_title(title):
    """在 sn_dict 中透過標題比對找到對應的 SN"""
    from aniGamerPlus import sn_dict
    for list_sn, info in (sn_dict or {}).items():
        plex = info.get('plex')
        if plex:
            ct = plex.get('clean_title', '')
            fn = plex.get('folder_name', '')
            if (ct and (ct in title or title in ct)) or (fn and (fn in title or title in fn)):
                return list_sn
        rn = info.get('rename', '')
        if rn and (rn in title or title in rn):
            return list_sn
    return None


@app.route('/schedule/subscribe', methods=['POST'])
def schedule_subscribe():
    """從排程頁面訂閱動畫"""
    data = json.loads(request.get_data(as_text=True))
    sn = data.get('sn', '')
    mode = data.get('mode', 'latest')
    folder_name = data.get('folder_name', '')
    clean_title = data.get('clean_title', '')
    season = data.get('season', '')
    ep_offset = data.get('ep_offset', '')
    comment = data.get('comment', '')

    if not sn:
        return jsonify({'error': '缺少 SN'}), 400

    # 組合 sn_list 格式行
    line = str(sn) + ' ' + mode
    if clean_title:
        line += ' <' + clean_title + '>'
    if folder_name:
        line += ' {' + folder_name + '}'
    if season:
        season_str = '(S' + str(int(season)).zfill(2)
        if ep_offset and int(ep_offset) > 0:
            season_str += '-' + str(ep_offset)
        season_str += ')'
        line += ' ' + season_str
    if comment:
        line += ' # ' + comment

    # 寫入 sn_list
    current = Config.get_sn_list_content().rstrip('\n')
    if current:
        new_content = current + '\n' + line + '\n'
    else:
        new_content = line + '\n'
    Config.write_sn_list(new_content)
    err_print(0, 'Dashboard', '通過排程頁面訂閱 ' + line, no_sn=True, status=2)
    return jsonify({'status': 200, 'line': line})


@app.route('/schedule/unsubscribe', methods=['POST'])
def schedule_unsubscribe():
    """從排程頁面取消訂閱"""
    data = json.loads(request.get_data(as_text=True))
    title = data.get('title', '')
    if not title:
        return jsonify({'error': '缺少標題'}), 400

    matched_sn = _find_sn_by_title(title)
    if matched_sn is None:
        return jsonify({'error': '找不到對應的 sn_list 條目'}), 404

    # 從 sn_list 移除對應行
    current = Config.get_sn_list_content()
    lines = current.split('\n')
    new_lines = []
    removed = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            new_lines.append(line)
            continue
        parts = stripped.split()
        if parts and parts[0].isdigit() and int(parts[0]) == matched_sn:
            removed = True
            continue
        new_lines.append(line)

    if removed:
        Config.write_sn_list('\n'.join(new_lines))
        err_print(0, 'Dashboard', '通過排程頁面取消訂閱 SN=' + str(matched_sn), no_sn=True, status=2)

    return jsonify({'status': 200, 'removed': removed, 'sn': matched_sn})


@app.route('/schedule/force_check', methods=['POST'])
def schedule_force_check():
    """強制立即檢查指定動畫"""
    data = json.loads(request.get_data(as_text=True))
    title = data.get('title', '')
    if not title:
        return jsonify({'error': '缺少標題'}), 400

    matched_sn = _find_sn_by_title(title)
    if matched_sn is None:
        return jsonify({'error': '找不到對應的 sn_list 條目'}), 404

    Config.force_check_sns.add(matched_sn)
    err_print(0, 'Dashboard', '通過排程頁面請求強制檢查 SN=' + str(matched_sn), no_sn=True, status=2)
    return jsonify({'status': 200, 'sn': matched_sn})


def run():
    settings = Config.read_settings()  # 读取配置

    if settings['dashboard']['BasicAuth']:
        # BasicAuth 配置
        app.config['BASIC_AUTH_USERNAME'] = settings['dashboard']['username']  # BasicAuth user
        app.config['BASIC_AUTH_PASSWORD'] = settings['dashboard']['password']  # BasicAuth password
        app.config['BASIC_AUTH_FORCE'] = True  # 全站验证
        basic_auth = BasicAuth(app)

    port = settings['dashboard']['port']
    host = settings['dashboard']['host']

    if settings['dashboard']['SSL']:
        # SSL 配置
        ssl_path = os.path.join(Config.get_working_dir(), 'Dashboard', 'sslkey')
        ssl_crt = os.path.join(ssl_path, 'server.crt')
        ssl_key = os.path.join(ssl_path, 'server.key')
        # ssl_keys = (ssl_crt, ssl_key)
        # app.run(use_reloader=False, port=port, host=host, ssl_context=ssl_keys)
        server = WSGIServer((host, port), app, handler_class=WebSocketHandler, certfile=ssl_crt, keyfile=ssl_key)

        wrap_socket = server.wrap_socket
        wrap_socket_and_handle = server.wrap_socket_and_handle

        # 处理一些浏览器(比如Chrome)尝试 SSL v3 访问时报错
        def my_wrap_socket(sock, **_kwargs):
            try:
                # print('my_wrap_socket')
                return wrap_socket(sock, **_kwargs)
            except ssl.SSLError:
                # print('my_wrap_socket ssl.SSLError')
                pass

        # 此方法依赖上面的返回值, 因此当尝试访问 SSL v3 时, 这个也会出错
        def my_wrap_socket_and_handle(client_socket, address):
            try:
                # print('my_wrap_socket_and_handle')
                return wrap_socket_and_handle(client_socket, address)
            except AttributeError:
                # print('my_wrap_socket_and_handle AttributeError')
                pass

        server.wrap_socket = my_wrap_socket
        server.wrap_socket_and_handle = my_wrap_socket_and_handle

    else:
        # app.run(use_reloader=False, port=port, host=host)
        server = WSGIServer((host, port), app, handler_class=WebSocketHandler)

    server.serve_forever()


if __name__ == '__main__':
    run()
    pass
