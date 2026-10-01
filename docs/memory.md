# memory（接續指引）— ProTech-MFG 多 Pi4 治具 + OTA

> 本檔為離開前的快速接續備忘。完整計畫見
> [`ProTech-MFG-Pi4-OTA-ToDo.md`](ProTech-MFG-Pi4-OTA-ToDo.md)（7 Task）。
> Redmine 追蹤單：kiro-ATLAS #72（刻意留在 kiro-ATLAS，非搬至 ProTech-MFG）。

## 專案現況
- MFG 已從 kiro-ATLAS 抽出為獨立專案（src/mfg + src/web GUI），已實跑過
  EAP111/OAP101/Pi7a（見 reports/，2026-09-18）。
- 後端已是 client-server（FastAPI host=0.0.0.0），PC 瀏覽器連 http://<pi4>:8020 操作。

## 進度（對齊 Pi4-OTA-ToDo 的 7 Task）
- ✅ **第 0 步 git init**：repo 已初始化（首次 commit c2f4384）。.gitignore 已排除
  .venv/reports/*.db/*.db-shm/*.db-wal/tftp binary。
- ✅ **Task 1（治具主機識別）**：commit 6f439a3。
  - **決策**：治具識別用 **eth0 MAC**（非 hostname）——硬體唯一、免設定、換機免改腳本。
  - **命名衝突處理**：現有 `station` 欄位已被「測試階段 PT/FT/FDL」(config/stations.yaml)
    佔用，故主機識別**另立 `host` 概念**，兩者並存不衝突。
  - 實作：`src/web/host.py` `get_host()`（解析序：MFG_HOST 覆寫 >
    /sys/class/net/<iface>/address，iface 可用 MFG_HOST_IFACE 改，預設 eth0 > ''）；
    `db.py` runs 表加 `host` 欄位（含向後相容 ALTER）；runner 每筆 run 記錄 host；
    app.py 加 `GET /api/host`、runs/html 加「主機」欄；index.html header 顯示主機 badge。
  - 測試：`src/web/tests/test_host.py` 7 passed（解析序/normalize/db 記錄/向後相容欄位）。
- ⏳ **Task 2 起未開始**：單台 Pi4 部署（deploy/install.sh + protech-mfg.service）→
  Task 3~6 OTA 中控（PC OTA server + ota-update.sh + 儀表板）→ Task 7 文件。

## 下一步（Task 2）
- `deploy/install.sh`（建 venv、pip install、跑 tools/setup_ft232h_gpio.sh、產生 VERSION）。
- `deploy/protech-mfg.service`（ExecStart=python run_gui.py 8020、Environment 可注入
  MFG_HOST/MFG_HOST_IFACE、開機自啟、失敗重啟）。
- 不依賴 OTA 的最小可 demo：Pi4 一鍵裝 + systemd 自啟 + 瀏覽器連得上 + header 顯示該台 MAC。

## 驗證指令備忘
```bash
# 單元測試
PYTHONPATH=src/web .venv/bin/python -m pytest src/web/tests/test_host.py -v
# app 載入 + 真實 get_host（本機無 eth0 回空；MFG_HOST_IFACE=eno2 可讀真實 MAC）
PYTHONPATH=src:src/web .venv/bin/python -c "import app; print('OK')"
# 啟動 GUI
.venv/bin/python run_gui.py 8020
```

## 注意
- `station`（PT/FT/FDL）= 測試階段；`host`（eth0 MAC）= 哪台 Pi4。**勿混用**。
- 本環境是開發 PC（介面 eno2/enp0s31f6，無 eth0），get_host() 在此回空屬正常；
  實機 Pi4 才會讀到 eth0 MAC。
