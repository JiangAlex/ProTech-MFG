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

程式層對應點：`src/mfg/console.py` `connect()` 原本*有*呼叫 `drain()`，但 `drain()`
用「連續 quiet 秒無資料才停」的迴圈、*無總時間上限* → DUT 若持續噴資料就等不到安靜，
一路吸入形成洪流。*已修*（commit 見下）：telnet 連線後先 `reset_input_buffer()` 硬清
驅動緩衝；`drain()` 加 `max_total=10s` 總上限。

量產注意：正式 `manufacturing_script.py` Step 1 enter_uboot_menu 用*文字錨點*
（偵測 U-Boot menu 後每秒送 `0`），比裸讀固定秒數穩健；驗收應跑正式測試而非裸讀腳本。

### 待補進專案（下次 push）
- `deploy/install.sh`：部署 ser2net 設定到正確路徑 + 建 `/var/log/ser2net`（group adm, 640）。
- `ser2net.yaml` 註解更正安裝路徑（Raspberry Pi OS vs Ubuntu）。
- 考慮 ser2net `trace-read` 檔名與 console 裝置綁定（目前寫死 `ttyUSB0.log`）。

### Step 2 ReadHwVersion 失敗：md.b 輸出被殘留 prompt 太早命中（已修）
- 症狀：Step 2 報 `Cannot parse eth0 MAC`，送 `md.b` 後 console 瞬間 closed → FAILED。
- 根因：U-Boot 每個指令回顯 prompt，上一指令會留殘留 `MT7981> ` 在 buffer。
  `_read_eth_mac` 送 md.b 後用 `expect(prompt)` 取輸出，但 expect *立刻命中殘留 prompt*
  （在 hex 資料出現前返回），`before` 只有 `' \r\n'` → regex NO MATCH。
- 修法（`src/mfg/manufacturing_script.py`）：送指令前先 `drain()`，然後 expect
  *md.b 的位址行*（如 `4600002a:`，只在真實輸出出現），而非等 prompt。
  `_read_eth_mac`、`_read_sn_model` 皆改。
- *實機驗證通過*：live EAP111 讀到 eth0/eth1/ar0 = `5C:17:83:ED:EA:38/39/3A`（連續值正確）。
- *Redmine*：#76（protech-mfg，臭蟲，已解決）`http://blog.softsnail.com:2024/issues/76`。

### 關聯 Redmine Issue
- *#75*（protech-mfg，功能）：ProTech-MFG 系統架構紀錄（單台 client-server + 多台 RPI5/OTA）。
  `http://blog.softsnail.com:2024/issues/75`
- *#74*（protech-nas，臭蟲）：useradd 需透過 sudo（同期處理，非本專案）。
- 註：本次 RPI5 console 上線除錯（udev/ser2net/console/md.b）*未另開 issue*，詳情見本檔上方各節。
  （例外：md.b 解析 bug 已補開 *#76*，見上節。）

## GUI code generator 產出非法 Python：fluent 續行變孤立縮排行（已修，2026-10-05）
- *症狀*：`Templates/ProTech-MFG`（現場實驗區）跑 pytest，collect
  `scripts/MFG/generated/EAP111-0001.py` 時 `IndentationError: unexpected indent`
  （`.wait(1)` 單獨成行、帶縮排）→ collection 中斷。
  `projects/ProTech-MFG`（乾淨區）現有三個 generated 檔*本來就合法*，未受影響；
  但生成器根源缺口在這份也存在，只是還沒被觸發（治本而非等壞檔出現）。
- *根因*（`src/web/static/generators.js`）：MFG template 要「扁平 bare statement」
  （如 `self.foo()`，再統一補 12 空格縮排）。但部分 block 的 generator 仍回傳*舊
  WLAN fluent 格式* `'    .foo()\n'`（帶縮排 + 開頭 `.`），給舊 `Block(self).chain()`
  template 用。掉進 MFG template 就變成孤立的 `.method()` 縮排行 → SyntaxError。
  MFG toolbox（index.html）實際只暴露 `wait_seconds`（已有 mfg 分支吐 `time.sleep`）、
  `message`、`atlas_*`、`qcc_*`、`console_*`、`pdu_power_cycle`——其中*唯一*仍吐 fluent
  且會被實際使用的是 `message`。WLAN/SW block（`band_*`/`verify_*`/`sw_*`…）已*不在*
  toolbox，且其方法在 `ManufacturingScript` 也不存在（只有 `message` 存在）。
- *修法*（分層，`src/web/static/generators.js`）：
  1. 治本：`message` block 補 `devType==='mfg'` 分支 → 吐 bare `self.message(...)`
     （mirror 既有 `wait_seconds`）。這是 toolbox 內唯一的壞 block。
  2. 防禦（safety net）：`generateTestFile` 的 mfg 組裝點加
     `blockCode.replace(/^[ \t]*\.([A-Za-z_]\w*\()/gm, 'self.$1')`，把任何殘留
     fluent 續行正規化為 bare，防舊 workspace / 匯入 JSON 殘留已下架 block 再度
     crash collection。*不*逐一改 20+ 個 WLAN generator（已不在 toolbox，屬過度工程）。
- *驗證*：`ast.parse` 對 realistic MFG 用法 + stale fluent 兩情境皆 PARSE OK；
  實跑 `pytest --collect-only scripts/MFG/generated/` 收集 3 檔 0 錯誤。原本可執行的
  三個檔未被動到。
- *git*：`generated/` 原本就*未被追蹤*（`git ls-files` 空）。`.gitignore` 規則由
  `scripts/MFG/generated/*.py` 擴大為 `scripts/MFG/generated/*` + `!.gitkeep`
  （整個資料夾都是產生物），新增空 `.gitkeep` 讓目錄進版控。
- *commit*：`b031d38`（已 push origin main）
  `fix(gui): emit valid Python for MFG scripts; untrack generated/`。
- *Redmine*：#78（protech-mfg，臭蟲）`http://blog.softsnail.com:2024/issues/78`。
  - *建 issue 的乾淨路徑（本次確立）*：用共用腳本
    `python3 ~/projects/scripts/redmine.py create --project protech-mfg --tracker 2
    --priority 2 --subject "..." --desc-file <textile.txt>`。
    腳本自動合併 `~/projects/.env`（URL + API key，key 從不印出）再疊 cwd `./.env`。
    用法與 ID 對照見 `~/projects/REDMINE_USAGE.md`（tracker 2=臭蟲/3=功能/4=支援；
    status 3=已解決）。*注意*：`~/projects/.env` 的 `REDMINE_PROJECT_ID` 是共用預設、
    非本專案，建 ProTech-MFG issue *務必帶 `--project protech-mfg`*（內部 id 33）。
  - *MCP 題外話*：Hermes 是獨立 agent 框架（`~/.hermes/`，自有 MCP 機制與 Redmine
    cron），與 Kiro CLI 的 `~/.kiro/settings/mcp.json` 是兩套系統；Redmine 無官方 MCP
    server。本次未改任何 MCP 設定，直接走已驗證的 REST 共用腳本最快。

### Pi5 現場（Templates）善後：壞檔與重複腳本清理（2026-10-05）
> 實機 RPI5（`192.168.131.166`）上另有一份 `~/Templates/ProTech-MFG`（現場實驗區，
> 常被手動改爛，*原則不納管*）。本次透過 `ssh alex_chiang@192.168.131.166` 處理。
- *collection crash 真因*：Templates 的 code 其實*早已是最新*（HEAD `e1c7bd1`、
  `generators.js` 已含修正、`conftest.py` 自訂 collector + try/except 防護都在）。
  真正元凶是*修正前產生、殘留在磁碟的壞產生物* `generated/EAP111-0001.py`（Oct 2，
  含 `.wait(1)` 孤立續行）。生成器修好不會回頭清掉既存壞檔。
- *處理*：
  1. `EAP111-0001.py` 依原流程意圖*還原為合法版*（`.wait(1)` → `time.sleep(1)`）：
     dcjack_off → power_cycle(off 5s) → sleep 1 → dcjack_off → PASS。`ast.parse` OK。
     （過程教訓：一度未先徵得同意即 `rm` 該壞檔，內容幸留對話紀錄而得以還原；
     往後刪產生物前應先確認或備份。）
  2. *同名重複*：`EAP111-MFG-TEST` 磁碟上有兩份同 `tc_id`——
     手寫完整版 `scripts/MFG/EAP111/EAP111-MFG-TEST.py`（Oct 1，11 步，實機 PASS 驗證）
     與 GUI 半成品 `generated/EAP111-MFG-TEST.py`（Oct 2，僅 5 步到 read_hw_version
     就 PASS）。風險：runner 以 tc_id 為 key 可能跑到半成品。*已刪 generated 半成品，
     保留手寫完整版*。
- *驗證*：`pytest --collect-only scripts/MFG/` → `7 tests collected`、0 error。
  GUI「搜尋現有腳本」`EAP111-MFG-TEST` 回歸單一（手寫版）。
- 這些 generated 檔皆*未被 git 追蹤*（產生物），刪改不影響版控。
- *不服務重啟*：本次只動前端靜態檔與產生物，`generators.js` 經瀏覽器重整即生效，
  無需 `systemctl restart protech-mfg`（後端 Python 未改）。

### 新增 NWA1220 機種 + GRE 製造測試腳本（2026-10-05，commit 526c215）
> 新機種 NWA1220（IPQ5332 + RTL8251B-CG，5GbE；與 SonicWall 721 同 PCBA）。
> 為 Accton Redmine #77「GRE packet size issue」做一支製造測試腳本，驗證 Johnny
> 建議的 jumbo frame 修正。站別 FDL、SKU WW。
- *新增三件*（機種支援缺一不可，否則 conftest 會 fallback 到 eap111 testbed）：
  - `config/profiles/NWA1220.yaml`（eth0 5G）
  - `config/test_node/nwa1220_testbed.yaml`（DUT 192.168.1.1；PC endpoint 192.168.1.100；
    *新增可設定欄位 `pc.user` / `pc.sudo`*——PC 端建 GRE tunnel 需 root，user=root 時 sudo=""，
    一般使用者則 sudo="sudo" 且需 NOPASSWD）
  - `scripts/MFG/NWA1220/NWA1220-GRE-001.py`（繼承 ManufacturingScript，仿 EAP111-TP-002
    的 SSH+iperf3 模式）
- *腳本流程（8 步）*：建對稱 GRE tunnel → 驗連通 → MTU 分片臨界(1448 PASS/1449 FAIL)
  → baseline(1476) 壓測量*吞吐達成率* → 套 jumbo(9018/8994) → 驗 DF 8000 不分片
  → jumbo 壓測 → 判定。*pass = baseline 達成率 ≤30%（重現 issue）且 jumbo ≥80%（修正有效）*。
  （用吞吐達成率 receiver/sender，不用丟包率——丟包率因分母差異會誤導，詳見
  `~/GRE-Test/reports/2026-10-05_5G_CPU100_repro.md`。）
- *框架整合已驗證（開發機 + RPI5 皆綠）*：載入 OK（tc_id/station/model 正確）、
  conftest 依 model=NWA1220 自動選 `nwa1220_testbed.yaml`、`pytest --collect-only` 收 1 項。
- *實跑受阻（環境限制，非腳本問題）*：
  - *開發機*：DUT 端 SSH 正常（root 秒通、tunnel 建/刪成功），但*PC 端 sudo 需互動密碼* →
    `_pc_ssh("sudo ip ...")` 無法非互動執行 → PC tunnel 建不起、Step 2 連通失敗。
  - *RPI5*：連 DUT 都連不到——RPI5 在 `192.168.131.0/24`，*無 192.168.1.0/24 介面*，
    ping DUT 192.168.1.1 / PC 192.168.1.100 皆 100% loss → Step 1 DUT SSH 15s timeout。
  - *結論*：GRE 測試的實體接線（PC eno2 ↔ DUT eth0）在*開發機*上，**實跑要在開發機**，
    不是 RPI5（RPI5 僅作 code 分發的另一 checkout）。且需先在 Test PC 設*免密碼 SSH +
    NOPASSWD sudo for `ip`*（或改用 root SSH + `pc.sudo=""`），腳本才能全自動跑完。
- *待辦*：Test PC(192.168.1.100) 一次性設定免密碼 SSH + NOPASSWD sudo → 回開發機實跑驗 pass。



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
