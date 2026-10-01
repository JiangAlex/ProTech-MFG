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
- ✅ **Task 2（單台 Pi4 部署）完成並實機驗證**（2026-10-01）：
  - `deploy/install.sh`（五步 idempotent：apt 套件 / venv+pip / udev 規則 /
    VERSION / systemd service）、`deploy/protech-mfg.service`、`deploy/README.md` 完成。
  - **實機部署成功**：Pi4 `192.168.131.166`，install.sh 五步全過，
    `protech-mfg.service` enabled + started，GUI 在 `:8020`。
  - **連通性實測**：從開發機 `curl http://192.168.131.166:8020` 回 **HTTP 200**（~32ms），
    ping 0% loss。後端 + GUI 確認正常對外服務。
  - 專案已 push 到 GitHub：`https://github.com/JiangAlex/ProTech-MFG`（分支 main）。
  - 待 Pi4 本機確認（硬體相關、無法遠端驗）：plugdev 群組生效、`/dev/mfg-power`
    與 `/dev/mfg-console` 符號連結、GUI header 主機 badge 顯示 eth0 MAC。
- ⏳ **Task 3 起未開始**：Task 3~6 OTA 中控（PC OTA server + ota-update.sh + 儀表板）
  → Task 7 文件。

## RPI5 實機 console/硬體上線除錯紀錄（2026-10-01，已全部打通）

> 實機為 *Raspberry Pi 5*（`192.168.131.166`，hostname RPI5），非 Pi4；arm64 完全相容。
> 一次把掃碼→電源→console→uboot 全鏈路跑通，過程踩了數個雷，結論如下。

### 裝置對應（實機確認）
- *電源 relay* = FT232H（`0403:6014`）→ `/dev/mfg-power`，pyftdi `ftdi://ftdi:232h/1`。
  low-trigger 板，testbed 需 `active_high: false`（三個 testbed 已正確設定）。
- *DUT console (EAP111)* = *PL2303*（`067b:2303`）→ `/dev/mfg-console`，115200。
- *FT4232H*（`0403:6011`，Quad，ttyUSB0..3）*不是* console，只是其他 UART。

### 踩雷與根因（避免重犯）
1. *console 不是 FT4232H*：中途插著 FT4232H，一度誤判 console 走它，在四條 UART 上
   掃鮑率全是雜訊。EAP111 console 一直是 PL2303。→ `99-mfg-serial.rules` 已移除
   FT4232H 搶 `mfg-console`，PL2303 專屬 `mfg-console`，FT4232H 只給 `mfg-console-a/b/c/d`。
2. *udev SYMLINK 時序*：`udevadm control --reload-rules` + `udevadm trigger` *不會*對
   已存在裝置重套 `SYMLINK+=`。必須真實 add 事件：重插 USB，或
   `echo 1-2 | sudo tee /sys/bus/usb/drivers/usb/{unbind,bind}`。
3. *ser2net 設定路徑*：Raspberry Pi OS 讀 `/etc/ser2net.yaml`（非 Ubuntu 的
   `/etc/ser2net/ser2net.yaml`）；systemd ExecStart 用 `-c /etc/ser2net.yaml`。
   `deploy/install.sh` *沒有*部署 ser2net 設定（缺口，待補）。
4. *ser2net log 權限*：GUI live console 讀 `/var/log/ser2net/ttyUSB0.log`，該檔預設
   root-only → GUI permission denied。修：`sudo chgrp adm <log> && sudo chmod 640 <log>`。
5. *讀取時機（最關鍵）*：EAP111 uboot 訊息是*一次性、只在上電瞬間噴發*。必須
   *先開讀取執行緒 → relay_off 3 秒(真 reset，1.5 秒電容殘電不夠) → relay_on → 持續捕捉*。
   先前都在 power_cycle 之後才讀，錯過噴發，誤判成「讀不到/亂碼」。
   ser2net 獨佔 device，裸 `serial.Serial` 直開會讀 0 bytes，須先 `systemctl stop ser2net`。

### 驗證成功證據
- 直讀 `/dev/mfg-console` @115200，先讀→斷電3秒→開電，捕捉 3367 bytes、printable 99%：
  `NOTICE: BL2 ... CPU: MT7981 (1300MHz) ... DRAM 512MB ... SPI_NAND ID 0xc2`（EAP111 開機）。
- 全鏈路確認正常：掃碼 / FT232H relay 送電（「喀」聲）/ PL2303 console / 115200。

### 讀取穩定性：第一次「暴量亂碼」非硬體故障（2026-10-01 補充）
連跑同一讀取腳本 3 次，結果：
- 第 1 次：*1,839,484 bytes*、printable 6%（暴量亂碼洪流）。
- 第 2 次：3,544 bytes、*99%*，讀到 `Hit any key to stop autoboot`。
- 第 3 次：3,330 bytes、*99%*，`Hit any key` + MT7981 開機 log。

結論：*接線/PL2303 線材沒問題*（2/3 次完美）。第 1 次的 184 萬 bytes 不是接觸不良
（那會是少資料），而是*上一輪 DUT 殘留狀態 + PL2303 input buffer 積壓*被一次吸入的洪流。
18:00 單跑一次得 0%，就是撞上這種殘留狀態。

程式層對應點：`src/mfg/console.py` `connect()` 在 telnet(rfc2217) 模式*沒有*在連線後
清 input buffer（有 `drain()`/`flush()` 方法但 connect 未呼叫）。*建議*：connect 後先
`reset_input_buffer()`/`drain()` 丟棄殘留，再開始比對。

量產注意：正式 `manufacturing_script.py` Step 1 enter_uboot_menu 用*文字錨點*
（偵測 U-Boot menu 後每秒送 `0`），比裸讀固定秒數穩健；驗收應跑正式測試而非裸讀腳本。

### 待補進專案（下次 push）
- `deploy/install.sh`：部署 ser2net 設定到正確路徑 + 建 `/var/log/ser2net`（group adm, 640）。
- `ser2net.yaml` 註解更正安裝路徑（Raspberry Pi OS vs Ubuntu）。
- 考慮 ser2net `trace-read` 檔名與 console 裝置綁定（目前寫死 `ttyUSB0.log`）。



## 下一步（Task 3：OTA 中控）
- PC 端 OTA server（集中管理多台 Pi4、派送版本）。
- Pi4 端 `ota-update.sh`（比對 VERSION、拉新版、重啟 service）。
- OTA 儀表板（各台 Pi4 版本 / 線上狀態）。
- 多台 Pi4：各台重複 `deploy/install.sh` 即可，治具識別自動取各台 eth0 MAC。

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
