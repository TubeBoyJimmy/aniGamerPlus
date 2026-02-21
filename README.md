<h1 align="center">aniGamerPlus — Enhanced Fork</h1>

<p align="center">
  巴哈姆特動畫瘋自動下載工具 — 全新 Dashboard、智慧排程、Plex 整合
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/github/license/TubeBoyJimmy/aniGamerPlus?style=flat-square">
  <img alt="GitHub release" src="https://img.shields.io/github/release/TubeBoyJimmy/aniGamerPlus?style=flat-square">
  <img alt="Based on" src="https://img.shields.io/badge/based%20on-miyouzi%2FaniGamerPlus-blue?style=flat-square">
</p>

> 本專案基於 [miyouzi/aniGamerPlus](https://github.com/miyouzi/aniGamerPlus) 開發，針對 **使用者介面**、**排程精度** 及 **Plex 媒體庫整合** 進行強化。原版功能完整保留，同時支援命令行與 Web Dashboard 操作。

---

## 目錄

- [與原版差異](#與原版差異)
- [新功能亮點](#新功能亮點)
  - [全新 Dashboard UI](#全新-dashboard-ui)
  - [智慧排程](#智慧排程-timer--time-table)
  - [Plex 深度整合](#plex-深度整合)
- [安裝與使用](#安裝與使用)
- [配置說明](#配置說明)
  - [config.json](#configjson)
  - [sn_list.txt](#sn_listtxt)
  - [cookie.txt](#cookietxt)
- [命令行使用](#命令行使用)
- [Dashboard](#dashboard)
- [延伸參考](#延伸參考)

---

## 與原版差異

| | 原版 [miyouzi/aniGamerPlus](https://github.com/miyouzi/aniGamerPlus) | 本 Fork |
|---|---|---|
| **Dashboard UI** | Bootstrap + layui | Tailwind CSS 雙主題（深色 / 淺色） |
| **排程機制** | 固定週期輪詢 | 雙模式：保留原有輪詢 + 新增智慧排程（秒級精確觸發） |
| **Plex 命名** | 基礎 `plex_naming` 開關 | 進階 sn_list 語法：`{資料夾}` `<標題>` `(S季數-偏移)` |
| **Plex 目錄** | 下載至 `bangumi_dir` | 新增獨立 `plex_bangumi_dir` 分離來源與媒體庫 |
| **下載判定** | 僅檢查資料庫記錄 | 資料庫 + 檔案存在性雙重檢查（≥5MB 視為已存在） |
| **任務監控** | WebSocket 即時推送 | HTTP Polling 浮動面板 |
| **設定介面** | 基本表單 | 分類群組 + Tooltip 說明 + 排程 / Plex 專區 |

---

## 新功能亮點

### 全新 Dashboard UI

以 Tailwind CSS 重新設計的 Web 控制台，支援 **深色** 與 **淺色** 雙主題切換。

- 巴哈姆特風格配色（cyan 青色系）
- 底部抽屜式任務面板：下載進度常駐底部，不干擾主畫面操作
- 響應式佈局，適配桌面與行動裝置
- 鍵盤快捷鍵：`ESC` 關閉介面、`T` 切換任務面板
- 設定欄位分類群組 + Tooltip 輔助說明

| 深色主題 | 淺色主題 |
|:---:|:---:|
| ![深色主題](screenshot/MainPageBlack.jpg) | ![淺色主題](screenshot/MainPageWhite.jpg) |

| 任務監控抽屜 | 手動任務 + 下載流程 |
|:---:|:---:|
| ![任務監控](screenshot/Task.jpg) | ![手動任務](screenshot/TaskOverlap.jpg) |

### 智慧排程 (Timer + Time Table)

從巴哈姆特動畫瘋首頁抓取每週排程表，以 **秒級精度** 在播出時間觸發下載，取代傳統的固定週期輪詢。

**核心特點：**

- 播出時間到達後精確觸發，可設定延遲補償避免搶在新集上架前
- 未找到新集自動重試（10 分鐘 → 30 分鐘 → 60 分鐘 → 放棄）
- 每小時自動刷新排程表，Dashboard 可手動強制重新抓取
- 三層排程匹配：SN 直接匹配 → 資料庫標題比對 → sn_list 標題提示
- 不在排程表中的番劇由 Fallback 機制定期檢查（預設每 24 小時）

**請求量對比（以 10 部訂閱為例）：**

| 模式 | 每日請求量 |
|---|---|
| 固定輪詢（每 5 分鐘） | ~2,880 次 |
| 智慧排程（非播出日） | ~34 次 |

> 詳細運作機制請參考 [SCHEDULE_COMPARISON.md](SCHEDULE_COMPARISON.md)

![排程表 + 訂閱管理](screenshot/Sub.jpg)

### Plex 深度整合

原版的 `plex_naming` 開關能在檔名中加入 `[S01E01]` 格式，並自動從標題偵測「第X季」，但在實際使用上仍有幾個瓶頸：

- **命名格式固定**：輸出如 `【動畫瘋】青之壬生浪 第二季[S02E01][1080P].mp4`，前綴、解析度標記、完整標題全部混在檔名中，不符合 [Plex 推薦的命名規則](https://support.plex.tv/articles/naming-and-organizing-your-tv-show-files/)
- **季數偵測有限**：僅支援標題結尾的「第X季」中文格式（正則 `$` 錨定），無法手動覆寫。以下情況一律 fallback 為 S01：
  - 英文格式：「Season 2」、「2nd Season」
  - 以副標題區分季度：如《青春豬頭少年》系列每季標題都不同（「…兔女郎學姐」「…聖誕服裝女孩」），完全沒有季數標記
- **標題無法自訂**：巴哈姆特的標題常帶有季數標記、`[年齡限制版]` 等附加文字，原版只能原樣帶入檔名
- **集數偏移無解**：巴哈姆特的季度編排方式不統一，原版均無法正確映射集數：
  - **同頁多季**：如[《我推的孩子》](https://ani.gamer.com.tw/animeVideo.php?sn=33312)三季全部放在同一頁面，集數從 1 連續遞增（S1: 1\~11、S2: 12\~24、S3: 25\~），Plex 需要每季重新從 E01 開始，但原版只能原樣輸出
  - **分頁但不從第 1 集開始**：如[《公主殿下，「拷問」的時間到了 第二季》](https://ani.gamer.com.tw/animeVideo.php?sn=47110)雖然分季放在不同頁面，但第二季集數從第 13 集開始，原版同樣無法將其轉換為 S02E01

本 Fork 透過 `sn_list.txt` 的擴充語法，讓使用者完全掌控 Plex 檔案結構：

```
# 基本用法 — 自動推導標題和季數
46922 all {青之壬生浪 第二季}  # → 青之壬生浪 S02E01.mp4

# 同頁多季 — 三季全在同一頁面, 追蹤第三季 (從巴哈第 25 集起)
47536 latest {我推的孩子} (S3-24)  # → 我推的孩子 S03E01.mp4

# 分頁不從 1 開始 — 第二季頁面集數從第 13 集起
47487 all {公主殿下 拷問的時間到了 第二季} <拷問公主> (S2-12)  # → 拷問公主 S02E01.mp4
```

產出檔案結構：

```
D:\動畫\季番\
├── 青之壬生浪 第二季\
│   ├── 青之壬生浪 S02E01.mp4
│   └── 青之壬生浪 S02E02.mp4
├── 我推的孩子\
│   ├── 我推的孩子 S03E01.mp4   ← 巴哈第 25 集
│   └── 我推的孩子 S03E02.mp4   ← 巴哈第 26 集
└── 公主殿下 拷問的時間到了 第二季\
    ├── 拷問公主 S02E01.mp4     ← 巴哈第 13 集
    └── 拷問公主 S02E02.mp4     ← 巴哈第 14 集
```

搭配原版已有的 `plex_refresh` 設定，下載完成後自動通知 Plex 伺服器刷新媒體庫（本 Fork 增強了 URL 處理容錯性）。

> 完整語法說明見 [sn_list.txt 配置](#sn_listtxt)

### 其他改進

- **檔案存在性檢查**：自動下載時除了查資料庫，額外檢查目標檔案是否已存在（≥5MB 視為有效），避免重複下載；手動任務可跳過此檢查
- **排程表瀏覽**：Dashboard 內建每週排程表，支援一鍵訂閱 / 取消訂閱
- **從巴哈重新抓取**：排程表每小時自動刷新，季度換新時亦可手動強制重新抓取
- **HTTP 存取日誌控制**：可開關 Dashboard 的 HTTP access log
- **手動下載命名**：手動任務支援指定輸出資料夾、檔名標題、季數與集數偏移，可套用 Plex `S##E##` 命名格式；輸入連結後即時預覽檔名，「智慧預填」可自動從訂閱清單或動畫標題填入建議值
- **正體中文統一**：所有日誌與介面文字統一使用正體中文

---

## 安裝與使用

### :warning: 注意

**本專案依賴 ffmpeg，請事先將 ffmpeg 放入系統 PATH 或程式目錄下！**

[下載 ffmpeg](https://ffmpeg.org/download.html) — 不知道如何放入 PATH 的話，直接將 `ffmpeg.exe` 放在和本程式同一資料夾下即可。

:warning: [**使用 Cookie 解析存在帳號被封鎖風險，不可解封，請三思後使用！**](https://github.com/miyouzi/aniGamerPlus/issues/207) :warning:

### EXE 執行

前往 [Releases](https://github.com/TubeBoyJimmy/aniGamerPlus/releases/latest) 下載最新 exe 檔案。

`Dashboard/` 資料夾需與 exe 放在同一目錄下（不打包進 exe）。

### 原始碼執行

Python 3 以上。

```bash
git clone https://github.com/TubeBoyJimmy/aniGamerPlus.git
cd aniGamerPlus
pip3 install -r requirements.txt
python3 aniGamerPlus.py
```

---

## 配置說明

### config.json

首次執行時自動產生，或可複製 `config-sample.json` 修改後更名。

以下列出主要設定項目（依 Dashboard 分類群組排列），🆕 標記為本 Fork 新增。

#### 路徑設定

| 設定 | 類型 | 預設 | 說明 |
|---|---|---|---|
| `bangumi_dir` | string | `""` | 下載存放目錄，以番劇為單位建立子資料夾 |
| `temp_dir` | string | `""` | 臨時目錄，留空使用程式目錄下 `temp/` |
| `classify_bangumi` | bool | `true` | 以番劇名建立子資料夾 |

#### 下載設定

| 設定 | 類型 | 預設 | 說明 |
|---|---|---|---|
| `download_resolution` | string | `"1080"` | 下載解析度，可選 360 / 480 / 540 / 576 / 720 / 1080 |
| `lock_resolution` | bool | `false` | 鎖定解析度，指定解析度不存在時放棄下載 |
| `default_download_mode` | string | `"latest"` | 預設下載模式：`latest` / `all` / `largest-sn` |
| `segment_download_mode` | bool | `true` | 分段下載模式（速度更快、容錯率更高） |
| `multi-thread` | int | `1` | 最大並行下載數（上限 5） |
| `multi_downloading_segment` | int | `2` | 每部影片並行下載分段數（上限 5） |
| `download_cd` | int | `60` | 下載冷卻時間（秒） |
| `parse_sn_cd` | int | `5` | SN 頁面解析冷卻時間（秒） |
| `add_bangumi_name_to_video_filename` | bool | `true` | 檔名包含番劇名 |
| `add_resolution_to_video_filename` | bool | `true` | 檔名包含解析度標記 `[1080P]` |
| `customized_video_filename_prefix` | string | `"【動畫瘋】"` | 檔名前綴 |
| `customized_video_filename_suffix` | string | `""` | 檔名後綴 |
| `use_mobile_api` | bool | `false` | 使用行動端 API 解析影片 |
| `danmu` | bool | `false` | 下載彈幕（.ass 格式） |
| `check_frequency` | int | `5` | 固定輪詢間隔（分鐘），僅在未啟用智慧排程時使用 |

#### 排程設定 🆕

| 設定 | 類型 | 預設 | 說明 |
|---|---|---|---|
| `smart_schedule` | bool | `false` | 啟用智慧排程（Timer + Time Table） |
| `schedule_delay` | int | `0` | 觸發延遲補償（秒），建議 20~60 避免新集尚未上架 |
| `schedule_fallback_frequency` | int | `1440` | 未排程番劇的全量檢查間隔（分鐘），預設 24 小時 |

#### Plex 設定

| 設定 | 類型 | 預設 | 說明 |
|---|---|---|---|
| 🆕 `plex_bangumi_dir` | string | `""` | Plex 媒體目標資料夾，留空使用 `bangumi_dir` |
| `plex_refresh` | bool | `false` | 下載完成後自動通知 Plex 刷新媒體庫 |
| `plex_url` | string | `""` | Plex 伺服器 URL（例：`https://192.168.1.100:32400`） |
| `plex_token` | string | `""` | Plex 認證 Token |
| `plex_section` | string | `""` | Plex 媒體庫 Section ID |

#### 代理設定

| 設定 | 類型 | 預設 | 說明 |
|---|---|---|---|
| `use_proxy` | bool | `false` | 啟用代理 |
| `proxy` | string | `""` | 代理地址，格式見[延伸參考](#使用代理) |

#### 其他設定

| 設定 | 類型 | 預設 | 說明 |
|---|---|---|---|
| `ua` | string | Chrome UA | 請求 UA，需與取得 cookie 的瀏覽器一致 |
| `check_latest_version` | bool | `true` | 啟動時檢查程式更新 |
| `read_sn_list_when_checking_update` | bool | `true` | 每次檢查更新時重讀 sn_list.txt |
| `read_config_when_checking_update` | bool | `true` | 每次檢查更新時重讀 config.json |
| `save_logs` | bool | `true` | 記錄日誌（一天一個檔案） |
| `quantity_of_logs` | int | `7` | 日誌保留天數 |

> 其他進階設定（FTP 上傳、推送通知、影片封裝格式等）請參考[延伸參考](#其他原版功能)或[原版 config.json 說明](https://github.com/miyouzi/aniGamerPlus#configjson)。

---

### sn_list.txt

自動下載的番劇列表，一個番劇中任選一個 sn 填入即可。

#### 基本格式（與原版相容）

```
sn碼 [下載模式] [<重命名>] [# 注釋]
```

```
10147 all                    # 前進吧！登山少女（下載全部）
11285 <史萊姆>               # 重命名資料夾為「史萊姆」
11317 latest                 # 僅下載最新一集
11388                        # 使用預設下載模式
```

- 下載模式可選 `latest`、`all`、`largest-sn`，省略時使用 config.json 設定
- `<重命名>` 將作為番劇資料夾名稱
- `#` 後方為注釋，程式不會讀取

#### 分類標籤

以 `@` 開頭定義分類資料夾，單獨 `@` 表示不分類：

```
@2024秋季番
46922 all    # 青之壬生浪 第二季
47063 all    # 和機器人啪啪啪
@
11468 all    # 不分類，直接放在番劇目錄下
```

#### 🆕 Plex 命名語法

在 sn 行中加入 `{資料夾名}` 即可啟用 Plex 模式，可選搭配 `<標題>` 和 `(S季數)`：

```
sn碼 [模式] {資料夾名} [<標題>] [(S季數[-集數偏移])] [# 注釋]
```

| 語法 | 必要性 | 說明 |
|---|---|---|
| `{資料夾名}` | **必填**（啟用 Plex 的前提） | Plex 媒體資料夾名稱 |
| `<標題>` | 選填 | Plex 檔名標題，省略時自動從資料夾名去除季數標記推導 |
| `(S季數)` | 選填 | 季數編號，省略時自動從資料夾名偵測 |
| `(S季數-偏移)` | 選填 | 集數偏移，用於跨季分割（cour split） |

**範例：**

```
# 自動推導標題和季數 — 最常用的寫法
46922 all {青之壬生浪 第二季}
# <標題> 自動推導為「青之壬生浪」（去除「第二季」）
# 季數自動偵測為 S02（從「第二季」）
# 產出: 青之壬生浪 第二季/青之壬生浪 S02E01.mp4

# 完整指定所有參數
47063 all {和機器人啪啪啪 第一季} <和機器人> (S1)
# 產出: 和機器人啪啪啪 第一季/和機器人 S01E01.mp4

# 同頁多季 — 我推的孩子三季全在同一頁面, 追蹤第三季
47536 latest {我推的孩子} (S3-24)
# 巴哈第 25 集 → 我推的孩子 S03E01.mp4
# 巴哈第 26 集 → 我推的孩子 S03E02.mp4

# 分頁但不從第 1 集開始 — 公主殿下第二季從巴哈第 13 集起
47487 all {公主殿下 拷問的時間到了 第二季} <拷問公主> (S2-12)
# 巴哈第 13 集 → 拷問公主 S02E01.mp4
# 巴哈第 14 集 → 拷問公主 S02E02.mp4
```

**自動推導規則：**

- **標題推導**：從 `{資料夾名}` 去除「第X季」或「Season N」等季數標記
  - `{青之壬生浪 第二季}` → 標題 `青之壬生浪`
  - `{Anime Season 3}` → 標題 `Anime`
- **季數偵測**：從 `{資料夾名}` 偵測中文或英文季數
  - `第一季` → S01、`第三季` → S03、`Season 2` → S02
  - 偵測不到時預設 S01

---

### cookie.txt

將瀏覽器的巴哈姆特 cookie 複製，以 `cookie.txt` 為檔名儲存在程式目錄下。`config.json` 的 `ua` 需與取得 cookie 的瀏覽器一致。

> Cookie 取得步驟請參考[延伸參考](#cookie-取得教學)或[原版教學](https://github.com/miyouzi/aniGamerPlus#cookietxt)（附截圖）。

---

## 命令行使用

本 Fork 完整保留原版命令行功能。EXE 使用者將 `python3 aniGamerPlus.py` 替換為 `aniGamerPlus` 即可。

```bash
# 下載單集
python3 aniGamerPlus.py -s 12345

# 下載全部劇集
python3 aniGamerPlus.py -s 12345 -m all

# 下載指定範圍 (第 5~8 集 + 第 12 集)
python3 aniGamerPlus.py -s 12345 -m range -e 5-8,12

# 指定解析度
python3 aniGamerPlus.py -s 12345 -r 720
```

> 完整參數說明請參考[原版命令行文件](https://github.com/miyouzi/aniGamerPlus#命令行使用)。

---

## Dashboard

Web 控制台預設啟用，預設 port 5000，支援 SSL 與 BasicAuth。

```jsonc
"dashboard": {
    "host": "127.0.0.1",  // 外部存取請改為 "0.0.0.0"
    "port": 5000,
    "SSL": false,          // 證書位於 Dashboard/sslkey/
    "BasicAuth": false,     // 注意：密碼為明文傳輸，建議搭配 SSL
    "username": "admin",
    "password": "admin"
}
```

> **SSL 安全提示**：repo 內附的 `Dashboard/sslkey/` 憑證為公開的預設自簽憑證，僅供快速啟用 HTTPS 加密連線。由於私鑰隨原始碼公開，任何人皆可取得，**不具備身份驗證效力**。若 Dashboard 暴露於不受信任的網路環境，建議自行產生憑證替換：
> ```bash
> openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
>   -keyout Dashboard/sslkey/server.key \
>   -out Dashboard/sslkey/server.crt \
>   -subj "/CN=your-hostname"
> ```

---

## 延伸參考

> 以下為進階功能的補充說明。完整原版文件請參考 [miyouzi/aniGamerPlus README](https://github.com/miyouzi/aniGamerPlus/blob/master/README.md)。

### 下載模式說明

影片下載支援兩種底層模式：

- **分段下載模式**（`segment_download_mode: true`，預設）：由 aniGamerPlus 下載個別分段再用 ffmpeg 合併，速度快且可自動重試失敗分段
- **ffmpeg 下載模式**（`segment_download_mode: false`）：直接將 m3u8 交給 ffmpeg 處理，不產生臨時資料夾

> 詳細比較請參考[原版說明](https://github.com/miyouzi/aniGamerPlus#下載模式説明)。

### Cookie 取得教學

1. 開啟瀏覽器 **無痕模式**，登入動畫瘋（勾選「保持登入狀態」）
2. F12 開發者工具 → Network → 選取 `ani.gamer.com.tw` → 複製 Cookie 欄位內容
3. 存為程式目錄下的 `cookie.txt`
4. 在 config.json 或 Dashboard 設定對應的 UA（可使用 Dashboard「取得當前 UA」按鈕）

> 附截圖的完整步驟請參考[原版教學](https://github.com/miyouzi/aniGamerPlus#cookietxt)。

### 使用代理

支援 `http`、`https`、`socks5h` 代理，可在 Dashboard 或 config.json 中設定。

```
# 無密碼驗證
http://example.com:1000

# 有密碼驗證
http://user:passwd@example.com:1000

# SOCKS5（支援遠端 DNS）
socks5h://127.0.0.1:1483
```

> 詳細說明請參考[原版代理設定](https://github.com/miyouzi/aniGamerPlus#使用代理)。

### 資料庫 aniGamer.db

SQLite3 資料庫，記錄影片下載狀態等資訊。一般無需手動修改。

> 欄位結構請參考[原版說明](https://github.com/miyouzi/aniGamerPlus#anigamerdb)。

### 其他原版功能

以下功能由原版提供，本 Fork 完整保留但未修改，詳細設定請參考[原版 README](https://github.com/miyouzi/aniGamerPlus/blob/master/README.md)：

- **[FTP 上傳](https://github.com/miyouzi/aniGamerPlus#configjson)** — 將影片上傳至遠端 FTP 伺服器，支援 FTP over TLS
- **[coolQ 推送](https://github.com/miyouzi/aniGamerPlus#configjson)** — 下載完成後向酷Q推送通知
- **[Telegram Bot](https://github.com/miyouzi/aniGamerPlus#configjson)** — 下載完成後透過 Telegram Bot 推送通知
- **[Discord 推送](https://github.com/miyouzi/aniGamerPlus#configjson)** — 下載完成後透過 Discord 推送通知
- **[Docker 部署](https://github.com/miyouzi/aniGamerPlus#docker-運行)** — 使用 Docker Container 運行

---

## 鳴謝

- [miyouzi/aniGamerPlus](https://github.com/miyouzi/aniGamerPlus) — 本專案的基礎
- [BahamutAnimeDownloader](https://github.com/c0re100/BahamutAnimeDownloader) — m3u8 模組參考
