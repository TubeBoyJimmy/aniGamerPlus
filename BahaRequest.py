#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# BahaRequest.py - 巴哈頁面共用請求器 (Dashboard 預覽 / 排程表 / 彈幕過濾詞 / 我的動畫匯出)
#
# 為什麼需要這個模組:
# 1. 2026-07-16 起巴哈 WAF 以 TLS 指紋全面攔截非瀏覽器請求, 所有巴哈請求必須走 curl_cffi
# 2. 任何帶用戶 cookie 的請求都可能收到一次性的 BAHARUNE 輪替 (set-cookie),
#    收到後若不寫回 cookie.txt, 新 cookie 即遺失, 所有實例的 cookie 一起作廢。
#    Anime.py 的下載主流程自帶輪替處理 (Anime.__request), 其餘散落的請求路徑統一走這裡。

import re
import threading

import Config
from ColorPrint import err_print

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None

# 輪替寫回同一時間只允許一個執行緒進行; 搶不到鎖代表別人正在刷新, 放棄即可
# (一次性輪替只有一個回應帶新 cookie, 後續呼叫會重讀 cookie.txt)
_renew_lock = threading.Lock()

# 共用 session: __cf_bm 等 Cloudflare cookie 需要跨請求延續,
# 每次開新 session (全新 TLS 握手、無 cookie 連續性) 是典型爬蟲特徵, 會墊高 WAF 風控分數
# (併發使用同一 curl_cffi session 的安全性依循 Anime.py 分段下載的既有先例)
_session = None
_session_lock = threading.Lock()


def available():
    return curl_requests is not None


def _get_session():
    global _session
    with _session_lock:
        if _session is None:
            # thread='gevent' 理由同 Anime.py (curl 為 C 阻塞呼叫)
            _session = curl_requests.Session(impersonate='chrome', thread='gevent')
        return _session


def _drop_session():
    # 收到 WAF 挑戰後棄用當前 session, 下次請求以乾淨狀態重來
    global _session
    with _session_lock:
        _session = None


def shared_session():
    """給 Anime.py / Danmu.py 取用共用 session: 全程式對巴哈只呈現一個瀏覽器身份
    (jar/__cf_bm 連續性)。每個實例各開新 session (全新 TLS 握手) 是 WAF 風控訊號,
    2026-07-19 00:00 多排程同時觸發的 fresh session 爆發即因此吃到假 deleted 與人機驗證頁。
    併發安全: curl_cffi Session 文件明示 thread-safe (預設 use_thread_local_curl,
    各執行緒有獨立 curl handle, 共用 cookie jar)。"""
    return _get_session()


def drop_session():
    """收到 WAF 挑戰頁 (status 200 的人機驗證頁) 時棄用共用 session。
    403 由 get() 自動處理; 挑戰頁只有呼叫端解析內容才認得出, 需主動通知。"""
    _drop_session()


def _session_cookie_dict(session):
    # 將 session cookie jar 攤平成 dict (同 Anime.__session_cookie_dict)
    jar = session.cookies
    try:
        d = jar.get_dict()
    except AttributeError:
        d = dict(jar)
    # 防禦: 過期刪除標記與 CF 連線 cookie 不可寫回 cookie.txt
    # (CF cookie 由 jar 全權管理, 見 Config.strip_cf_cookies 註解)
    return Config.strip_cf_cookies({k: v for k, v in d.items() if v != 'deleted'})


def _do_get(url, cookies, headers, params, proxies, timeout, session=None):
    if session is None:
        session = _get_session()
    resp = session.get(url, headers=headers, cookies=cookies, params=params,
                       timeout=timeout, proxies=proxies or None)
    return resp, session


def _default_proxies(settings):
    # 與 Anime.py 走同一個代理出口, 避免同帳號流量分裂成兩個 IP 墊高 WAF 風控分數
    if not settings.get('use_proxy'):
        return {}
    proxy = settings.get('proxy', '')
    # 擴展協議需要 gost (由 Anime.py 啟動並設定 HTTP(S)_PROXY 環境變數), 這裡只處理原生協議
    if re.match(r'^(http|https|socks5)://', proxy.lower()):
        return {'http': proxy, 'https': proxy}
    return {}


def get(url, cookies=None, headers=None, params=None, proxies=None, timeout=15, sn=0):
    """
    對巴哈發出 GET (curl_cffi 瀏覽器指紋).
    cookies=None 時自動讀取用戶 cookie (cookie.txt); 傳 {} 表示明確不帶 cookie.
    BAHARUNE 一次性輪替自動寫回 cookie.txt, 呼叫端毋須關心 set-cookie.
    """
    if curl_requests is None:
        raise RuntimeError('curl_cffi 未安裝, 無法通過巴哈 WAF 的 TLS 指紋檢測')
    settings = Config.read_settings()
    if cookies is None:
        cookies = Config.read_cookie() or {}
    if proxies is None:
        proxies = _default_proxies(settings)
    # 不覆寫 User-Agent: 讓 curl_cffi impersonate 自帶與 TLS 指紋一致的 UA。
    # settings['ua'] (用戶瀏覽器的 UA) 與 curl_cffi 模擬的 Chrome 版本不一致時,
    # UA/TLS 指紋錯位反而是 WAF 的 bot 訊號
    req_headers = {
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.6',
    }
    if headers:
        req_headers.update(headers)

    session = _get_session()
    # 輪替偵測基準需含 jar 送出前值: cookie.txt 被清空但共用 jar 仍載有登入 cookie 時
    # (2026-07-19 事故後的實際狀態), 輪替發生在 jar cookie 上, 只看明示 cookies 會漏寫回
    jar_rune_before = _session_cookie_dict(session).get('BAHARUNE')
    resp, _ = _do_get(url, cookies, req_headers, params, proxies, timeout, session=session)
    if resp.status_code == 403:
        # WAF 挑戰: 棄用 session, 下次請求以乾淨狀態重來 (退避節奏由呼叫端負責)
        _drop_session()

    # BAHARUNE 一次性輪替偵測: 比對送出值與回應後 jar 內的值, 不做 set-cookie 字串嗅探。
    # 實測巴哈會對「健康的登入 session」在首頁回應發出整組 BAHARUNE=deleted 刪除指令
    # (子網域 cookie 去重, jar 實際值不變), 且 MB_BAHARUNE 名稱包含 BAHARUNE 子字串,
    # 字串嗅探兩種情況都會誤判; jar 值有變才是真的收到新 cookie
    sent_rune = cookies.get('BAHARUNE') or jar_rune_before
    if sent_rune:
        jar_rune = _session_cookie_dict(session).get('BAHARUNE')
        if jar_rune and jar_rune != sent_rune:
            if _renew_lock.acquire(blocking=False):
                try:
                    # 寫回以磁碟現值為底: cookies 可能是空 dict (cookie.txt 曾被清空),
                    # 只用它當底會把 BAHAID 等欄位漏掉
                    new_cookies = Config.read_cookie() or {}
                    new_cookies.update(cookies)
                    new_cookies.update(_session_cookie_dict(session))
                    Config.renew_cookies(new_cookies, log=False)
                    # 確認請求僅允許一層: 直接走 _do_get, 不重入本輪替流程
                    _, confirm_session = _do_get('https://ani.gamer.com.tw/', new_cookies,
                                                 req_headers, None, proxies, timeout)
                    new_cookies.update(_session_cookie_dict(confirm_session))
                    Config.renew_cookies(new_cookies, log=False)
                    err_print(0, '用戶cookie已更新', '(BahaRequest)', status=2, no_sn=True)
                except BaseException as e:
                    err_print(sn, 'BahaRequest', 'cookie輪替寫回異常: ' + str(e), status=1)
                finally:
                    _renew_lock.release()
            else:
                err_print(sn, 'BahaRequest', '其他執行緒正在刷新cookie, 跳過本次寫回', display=False)
        # jar 無新值: 可能是去重刪除指令雜訊, 或送出的 cookie 已在他處輪替 —
        # 失效判定權留給 Anime.py 主流程, 這裡不標記失效也不重試

    return resp
