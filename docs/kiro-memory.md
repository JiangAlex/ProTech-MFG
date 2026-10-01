# ProTech-MFG 工作記錄（kiro-memory）

> 本檔記錄 ProTech-MFG（製造測試專案）的架構決策、變更與待辦。
> 慣例：技術解釋用繁體中文；變數 / 函數 / 檔名 / 代碼保持英文。
> 來源：從 `kiro-ATLAS` 抽出 MFG 而成（見 kiro-ATLAS/docs/protech-mfg-extraction.md、
> mfg-gui-separation.md、kiro-memory.md 的 MFG 相關章節）。

---

## 2026-09-17 — 架構決策：單一 repo，含 src/mfg（後端）+ src/web（GUI），純 MFG

### 決策
- **單一 github repo = ProTech-MFG**（不分成 GUI/測試兩個 repo）。
- 專案內同時放：
  - `src/mfg/` — MFG 後端（console / power_controller / manufacturing_script）
  - `src/web/` — Blockly GUI（FastAPI + 前端），**純 MFG**（移除 Switch/AP 相關）
- 因 GUI 與 scripts/config 在同一專案，**不需要 `MFG_PROJECT_ROOT` 環境變數**；
  GUI 沿用相對路徑（src/web → src → 專案根）找 scripts/config，與現行一致。

### 目標結構
```
~/projects/ProTech-MFG/
├── src/
│   ├── mfg/        console.py, power_controller.py, manufacturing_script.py, __init__.py
│   └── web/        app.py, runner.py, models.py, db.py, script_parser.py,
│                   console_stream.py, scheduler.py, static/(blocks.js,
│                   generators.js, index.html, style.css ...)
├── scripts/MFG/    EAP111/, OAP101/, Pi7a/
├── config/         test_node/(eap111_testbed.yaml, oap101_testbed.yaml,
│                   pi7a_testbed.yaml), profiles/(EAP111.yaml, OAP101.yaml, Pi7a.yaml)
├── tools/          setup_ft232h_gpio.sh, ft232h_polarity_test.py
├── tftp/           韌體檔（.gitkeep；binary 不進 git）
├── docs/           kiro-memory.md, kiro-todo.md, logfiles/
├── conftest.py     精簡：只 --mfg-testbed / --sku + MfgCollector/MfgItem
├── pytest.ini      addopts = -v --tb=long
└── requirements.txt pyyaml tftpy pexpect pyftdi fastapi uvicorn websockets pydantic pytest
```

### GUI 純 MFG — 待處理的去耦合（在 kiro-ATLAS 內先改好再搬）
1. **runner.py**：移除 `_test_env()` 的 Spirent `Libs/` 環境變數
   （TCLLIBPATH / STC_TCL / TCL_RUNNING_DIR / hltapi PYTHONPATH）；MFG 不需要。
   保留 `PYTHONPATH=<proj>/src`（讓 pytest 子行程 `import mfg`）。
2. **移除 device_monitor.py**（C50/Switch 狀態監看，MFG 無關）與其 app 路由。
3. **app.py**：移除 SW/AP 相關（topology plan、SW-AP profile 過濾等），
   profiles/skus API 保留（讀 config/profiles、config/test_node 的 ap.mfg.skus）。
4. **static**：Blockly 只保留 MFG 積木（atlas_*/console_*/pdu/wait/message/ssh），
   移除 SW（sw_*）/ AP（chain）積木與 plan.html/topology.js/console.html（Switch 用）。
5. 路徑：GUI 在 `src/web`，`parent.parent.parent` = 專案根，維持不變（結構相同）。

### 後端狀態（已在 kiro-ATLAS 完成，可直接搬）
- `src/mfg/` 已解耦為獨立套件，零耦合 core/Spirent/wlan；import 為 `mfg.*`。
- MFG 腳本、GUI generator 產出的 import 皆為 `mfg.manufacturing_script`。
- 支援機型參數化（testbed `ap.mfg`）+ 多 SKU（`ap.mfg.skus` + GUI SKU 下拉 + --sku）。
- 已跑通 EAP111-MFG-TEST（實機 PASS）。

### 待辦
1. 在 kiro-ATLAS 把 `src/web` 改成純 MFG + 去 Spirent/Switch 耦合（上述 1-4）。
2. 搬遷：cp src/mfg, src/web, scripts/MFG, config, tools, docs 到 ProTech-MFG；
   建精簡 conftest.py + requirements.txt + pytest.ini。
3. 驗證：`python -m py_compile src/mfg/*.py src/web/*.py`；
   `cd src/web && python app.py 8020` 開 GUI；跑一支 EAP111-MFG-TEST。
4. 新機型 OAP101(IPQ5018)/Pi7a 的實作（見 kiro-todo.md，需獨立平台流程/積木）。

### 待確認
- generated 腳本目錄：維持 `scripts/wlan/generated/` 還是改 `scripts/MFG/generated/`？

### 已確認（使用者：純 MFG）
- GUI 純 MFG：device_monitor（Switch 監看）、topology plan、SW/AP 積木、
  plan.html / topology.js / console.html（Switch 用）、runner 的 Spirent 環境變數
  —— 全部**移除**。只保留 MFG 積木與 MFG 執行/腳本/SKU 相關功能。

---

## 2026-09-17（續）— 搬遷進度：純 MFG 檔案已寫入 ProTech-MFG

### 決策確認
- generated 腳本目錄改為 **`scripts/MFG/generated/`**（純 MFG，不再用 wlan/generated）。
- device_profile 搬進 **`src/mfg/device_profile.py`**（GUI profile API 用）。

### Kiro 已直接寫入 ProTech-MFG（純 MFG 修改版）
- `src/mfg/__init__.py`、`console.py`、`device_profile.py`（新位置）
- `src/web/app.py`（純 MFG：/ → index.html；移除 device_monitor / topology /
  plans / dashboard / editor / console(switch) 頁；保留 tests/scripts/runs/
  console-stream/profiles/skus/schedules/files；generated=scripts/MFG/generated；
  profile 從 `mfg.device_profile`）
- `src/web/runner.py`（純 MFG：移除 Spirent 環境變數；PYTHONPATH=src 讓子行程
  import mfg；generated=scripts/MFG/generated；移除 plan/sync runner；腳本分類全 mfg）
- `conftest.py`（精簡：--mfg-testbed/--sku + MfgFile/MfgItem，PYTHONPATH src）
- `pytest.ini`、`requirements.txt`、`.gitignore`、`migrate_from_kiro_atlas.sh`

### 待辦（尚未完成）
1. ~~前端純 MFG（static）~~ **已完成**：`src/web/static/index.html` 已寫入純 MFG 版
   （固定 MFG，移除 SW/AP nav 與 dev-type 選單；toolbox 只留「🔧 工具 Utility」
   （MFG atlas_*/pdu/wait/message/scan）+「🔌 Console 製造」；保留 SKU 下拉、
   掃碼彈窗、儲存/執行/腳本搜尋邏輯）。
   - blocks.js / generators.js **verbatim 複製**（GUI 靠 toolbox 過濾，多餘的
     SW/AP 積木定義不顯示、不影響）：`bash copy_static_js.sh`。
2. **跑 migrate 腳本**（已完成）：`bash migrate_from_kiro_atlas.sh` ✓
3. **複製前端 JS**（使用者）：`bash copy_static_js.sh`（複製 blocks.js/generators.js）。
4. **驗證**：
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   PYTHONPATH=src python -c "from mfg.manufacturing_script import ManufacturingScript; print('OK')"
   cd src/web && python app.py 8020   # 開 GUI
   pytest scripts/MFG/EAP111/EAP111-MFG-TEST.py --mfg-testbed config/test_node/eap111_testbed.yaml --sku TE -s
   ```

### 注意
- migrate 腳本複製的 manufacturing_script.py / MFG 腳本 import 均為 `mfg.*`（在
  kiro-ATLAS 已改），搭配 conftest 的 `PYTHONPATH=src` 即可 import。
- 不複製 gui.db（首次啟動自動建空 db）；不複製 device_monitor / Switch 用 html。

---

## 2026-09-17（續 2）— ProTech-MFG 搬遷完成（靜態檢查通過）

### 完成狀態
- 檔案齊全：src/mfg/*、src/web/*（純 MFG）、src/web/static/{index.html(純MFG),
  blocks.js, generators.js, style.css}、scripts/MFG/{EAP111,OAP101,Pi7a,generated}、
  config/{test_node,profiles,console}、tools/、conftest.py、pytest.ini、
  requirements.txt、.gitignore。
- `copy_static_js.sh` 已跑（blocks.js/generators.js verbatim）。

### 靜態檢查（用 code/grep 工具，非執行）
- models.py 有 app.py 需要的 TestCreate/RunCreate(含 sku)/FileContent/ScheduleCreate。
- console_stream.py / scheduler.py / script_parser.py / db.py **無** wlan/core/
  device_monitor 耦合；只剩 GUI 內部 `from runner import ...`（正常）。
- scripts/MFG/EAP111/EAP111-0010.py 是完整 ManufacturingScript 腳本（conftest 會收）；
  conftest.MfgFile.collect 對 exec 失敗有 try/except，非 MFG 檔會被跳過。

### 驗證步驟（使用者實跑）
```bash
cd ~/projects/ProTech-MFG
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -c "from mfg.manufacturing_script import ManufacturingScript; print('OK')"
cd src/web && python app.py 8020    # GUI: http://localhost:8020（首頁即 Blockly）
# 實跑（需實機 + FT232H + ser2net）：
pytest scripts/MFG/EAP111/EAP111-MFG-TEST.py \
  --mfg-testbed config/test_node/eap111_testbed.yaml --sku TE -s
```

### 驗證時的注意點
- GUI 首頁（/）即積木編輯器；toolbox 只有「🔧 工具 Utility」+「🔌 Console 製造」。
- 型號下拉來自 config/profiles（EAP111/OAP101/Pi7a）；選 EAP111 出現 SKU 下拉(TE/TIP)。
- 首次啟動自動建空 gui.db（src/web/data/）；無歷史 run。
- FT232H：需先跑 tools/setup_ft232h_gpio.sh（sudo）解除 ftdi_sio，pyftdi 才能控電源。
- ser2net console：需 config/console 設定 + ser2net 服務（見 kiro-ATLAS docs/console_server.md）。

### 與 kiro-ATLAS 的關係
- kiro-ATLAS **完全未被改動**（所有搬遷/純化都在 ProTech-MFG 進行）。
- kiro-ATLAS 內仍有 src/mfg（解耦版）+ wlan shim，可持續運作；未來確認 ProTech-MFG
  穩定後，kiro-ATLAS 可選擇性移除 MFG 相關（避免雙處維護）。

---

## 2026-09-17（續 3）— 新增根目錄啟動腳本 run_gui.py

### 需求
- 希望在專案根 `~/projects/ProTech-MFG` 直接啟動 GUI，不必先 `cd src/web`。

### 做法（做法 A）
- 新增 `run_gui.py`（專案根）：把 `src/` 與 `src/web/` 加入 sys.path
  （前者供 `import mfg`，後者供 app.py 的隱式 import db/models/runner），
  再 `from app import app` 以 uvicorn 啟動。
- **不 chdir**：已確認所有路徑都基於 `Path(__file__)` 的絕對路徑，不依賴 CWD：
  - db.py `DB_PATH = Path(__file__).parent/"data"/"gui.db"`
  - app.py `PROJECT_ROOT`/`STATIC_DIR` 基於 __file__
  - runner.py `PROJECT_ROOT` 基於 __file__，pytest 子行程 `cwd=PROJECT_ROOT`
  → 在任何目錄執行 run_gui.py 都能正確找到 data/static/scripts/config。

### 用法
```bash
cd ~/projects/ProTech-MFG
python run_gui.py 8020        # 根目錄啟動（推薦）
# 或沿用舊方式：
cd src/web && python app.py 8020
```

---

## 2026-09-17（續 4）— 修正：GUI 選 MFG 腳本積木區空白（script_parser 缺 MFG 反解析）

### 症狀
- 全新啟動 GUI（`python run_gui.py 8020`），選 `EAP111-MFG-TEST`，中間積木區空白。

### 根因
- ProTech-MFG 是全新空 `gui.db`，沒有該測試的 workspace_json；GUI 遂走「反解析
  磁碟腳本」路徑（`/api/scripts/parse` → `script_parser.parse_script_to_blocks`）。
- 但 `script_parser._PATTERNS` **只認得舊的 console/switch/iperf 方法**，
  **沒有 MFG 方法**（self.scan_barcode/enter_uboot_menu/read_hw_version/...）→
  全部比對不到 → 0 積木 → 空白。
- 在 kiro-ATLAS 之所以能看到積木，是因為 DB 有存 workspace_json（走「DB 還原」），
  不是反解析。空 db 才暴露此問題。

### 修正
- `src/web/script_parser.py` 的 `_PATTERNS` 最前面加入 MFG 方法反解析規則
  （self.xxx() → atlas_* / pdu_power_cycle）。順序重點：
  `enter_tip_kernel_2` 在 `enter_tip_kernel` 前；`dcjack_power_cycle` 在
  `dcjack_on/off` 前（避免前綴誤匹配）。
- 對應：scan_barcode→atlas_scan_barcode、enter_uboot_menu→atlas_enter_uboot_menu、
  read_hw_version→atlas_read_hw_version、update_flash_image→atlas_update_flash_image、
  write_uboot_env_serial→atlas_write_uboot_env_serial、
  write_manufacturing_data→atlas_write_manufacturing_data、
  enter_tip_kernel→atlas_enter_tip_kernel、enter_tip_kernel_2→atlas_reboot_and_wait_login、
  check_tip_version→atlas_check_tip_version、
  check_manufacturing_data→atlas_check_manufacturing_data、
  reset_default→atlas_reset_default、dcjack_*→pdu_power_cycle(ACTION)、
  prepare/write/check_certification→atlas_*_certification。

### 驗證
- py_compile OK；反解析 EAP111-MFG-TEST.py 產出 **11 積木**（對應 11 步）。
- 重啟 GUI + 重新整理瀏覽器後，選 EAP111-MFG-TEST **積木有出現**（使用者確認）。

### 反解析欄位值（續 5 已補齊）
- `script_parser` 反解析 MFG 積木時已帶出實際欄位值：
  scan_barcode→SOURCE/TIMEOUT/EXPECTED_LEN；dcjack_power_cycle→ACTION=CYCLE+DELAY(off_delay)；
  dcjack_on/off→ACTION=ON/OFF；enter_tip_kernel→USERNAME/PASSWORD；
  prepare_certification→CERT_SERVER；write_certification→DUT_IP。
  實測 EAP111-MFG-TEST 反解析：11 積木、欄位值正確（timeout=30/len=12、delay=5、
  password=ail:oY7R）。

### 也修正
- `scripts/MFG/EAP111/EAP111-MFG-TEST.py` 更新為「跑到 PASS 的版本」（移除
  certification、write_manufacturing_data() 無硬編 MAC、掃碼取 SN/MAC、密碼
  ail:oY7R）。原搬過來的是 scripts/MFG/EAP111 的舊版（13 步含 cert）。
- requirements.txt 補 `apscheduler`（scheduler.py 需要）。
- 新增 `run_gui.py`（根目錄啟動，見續 3）。

---

## 2026-09-17（續 6）— 補搬三個 GUI 頁面：監控面板 / 檔案編輯 / 即時 Console（純 MFG）

### 需求
- 使用者指示：「監控面板、檔案編輯、即時 Console」凡與 MFG 有關者也要搬到 ProTech-MFG。
- 修正先前（續 1）的過度移除：這三頁的 MFG 相關部分應保留，不是全刪。

### 發現（重要）
- **後端其實早已就緒**：`src/web/app.py` 已有這三個功能的 API——
  `/api/files`（檔案編輯，白名單）、`/ws/console` + `/api/console/status`（即時
  Console，tail ser2net trace log）、`/api/runs/html` + `/ws/runs/{id}`（執行歷史）。
- 缺的只是**前端頁面（static html）**：先前 static 只有 index.html（Blockly）。
- 釐清：console.html 走 `/ws/console`（ser2net trace log tail），**MFG 也用**，
  續 1 標記「console.html（Switch 用）」為誤判 → 本次搬入。

### 做法（新增 3 個 static 頁 + 3 個頁面路由 + index nav）
1. `src/web/static/console.html`（即時 Console）：verbatim 自 kiro-ATLAS，只改
   標題與 nav。用 `/ws/console` / `/api/console/status`。
2. `src/web/static/editor.html`（檔案編輯）：用 `/api/files`（白名單已限定
   scripts/MFG、config/*、pytest.ini），只改 nav。
3. `src/web/static/dashboard.html`（監控面板，**純 MFG**）：
   - **移除**拓撲圖（topology.js）與設備狀態（C50/Switch 的 `/api/devices`，
     MFG 無此 API）。
   - **只保留**執行歷史 `/api/runs/html`（htmx 每 10s 更新）。
   - 自寫 `toggleLog`/`stopRun`/`reloadHistory`；`toggleLog` 讀 run 的 `log`
     欄位（已確認 db.py runs 表有 `log TEXT`）。
4. `app.py`：Pages 區塊新增 `/dashboard`、`/editor`、`/console`（FileResponse）。
5. `index.html`：header 加入 nav（四頁互通）：積木編輯(/)、監控面板(/dashboard)、
   檔案編輯(/editor)、即時 Console(/console)。四頁 nav 一致。

### 驗證（實際執行）
- `python -m py_compile src/web/app.py` → OK。
- 啟動 `run_gui.py` 後 curl：`/`、`/dashboard`、`/editor`、`/console` 皆 HTTP 200，
  標題正確（Blockly / 監控面板 / 檔案編輯器 / 即時 Console）。
- 支援 API：`/api/runs/html`、`/api/files`、`/api/console/status` 皆 200。
- 四頁皆含完整 4 連結 nav（grep 驗證 unique nav links = 4）。

### 注意
- dashboard 未納入 topology / device_monitor（純 MFG，無 C50/Switch）。
- editor 可編輯範圍受 app.py `EDITABLE_PATTERNS` 白名單控制。
- console 需 ser2net + config/console 設定才有實際 log（否則 status.available=false）。

---

## 2026-09-17（續 7）— Pi7a MFG 核心子集實作（QCC74x 平台，不含 ATE）

### 需求
- 為 Pi7a 新增製造測試支援。Pi7a = Qualcomm QCC744 (QCC74x)，是與 EAP111(MT7981)、
  OAP101(IPQ5018) 都不同的第三種平台：**無 U-Boot、無 tftpboot 燒錄**，韌體預燒，
  MFG 走韌體 CLI（prompt `qcc74x />`）。
- 首版做**核心子集**（不含 Keysight ATE RF 校準）；SN/MAC 沿用現有 scan_barcode
  兩次掃碼自動辨識；只寫程式碼 + py_compile + GUI 反解析驗證，實機由使用者自測。
- 依據：實機 PASS log `docs/logfiles/Pi7a-EC2617002807_PASS_N_1_132811.txt`。

### 做法（不改動 EAP111/OAP101 既有流程）
1. **config/test_node/pi7a_testbed.yaml**：console prompt 設 `qcc74x />`；ap.mfg 改為
   QCC74x schema（platform/console_prompt/model=Pi7a-0825-WL/hw_rev=R0B/
   diag_version_expected/i2c_expected_addrs/fuel_gauge_v_min,max/factory_write_cmd/
   factory_read_cmd/led_cmd_on,off/wdt_cmd）；移除 EAP111-style U-Boot/tftp offset 欄位。
2. **src/mfg/manufacturing_script.py**：在 Lifecycle 前新增 qcc_* 方法（全部指令/門檻走
   self.mfg）：`_qcc_prompt`、`_mac_to_colon`（4445BA15E59C→44:45:BA:15:E5:9C）、
   `_mac_add`（wifi=base+1, ble=base+2）、`_qcc_send`、`qcc_connect`、
   `qcc_power_mode_test`、`qcc_battery_mode_test`、`qcc_fuel_gauge_test`（解析電壓驗範圍）、
   `qcc_check_versions`（diag 比對 + mm 記錄）、`qcc_i2c_scan`（驗 expected addrs）、
   `qcc_factory_write`（factory w <MAC冒號> <SN> <Model> <HWver>）、
   `qcc_factory_check`（讀回驗 6 欄：halow/wifi/ble mac + S/N + Model + HWver）、
   `qcc_led_test`、`qcc_reset_button_test`（提示按住≥5s + 驗 factory 未清）、
   `qcc_wdt_test`（dt_reboot）。
3. **scripts/MFG/Pi7a/Pi7a-MFG.py**：整支重寫（移除 EAP111 U-Boot 步驟），run() 依序：
   scan_barcode → qcc_connect → power_mode → battery_mode → fuel_gauge →
   check_versions → i2c_scan → factory_write → factory_check → led → reset_button →
   wdt → PASS；finally cleanup。
4. **GUI**：blocks.js/generators.js 新增 11 個 qcc_* 積木（無欄位，colour 160）；
   script_parser.py `_PATTERNS` 加 self.qcc_*() 反解析（名稱互不為前綴，順序無虞）；
   index.html toolbox 新增「📶 QCC74x」category（原命名「📶 Pi7a (QCC74x)」，
   後於續 8 toolbox 重整改為純 SoC 命名「📶 QCC74x」）。

### 驗證（靜態，實機由使用者）
- `py_compile` manufacturing_script.py / script_parser.py / Pi7a-MFG.py → OK。
- testbed 載入 + self.mfg 解析：platform=qcc74x、console_prompt=`qcc74x />`、
  model=Pi7a-0825-WL、hw_rev=R0B、factory_write_cmd=`factory w`；
  `_mac_to_colon('4445BA15E59C')`=44:45:BA:15:E5:9C、+1=...9D、+2=...9E（與 log 相符）。
- 反解析 Pi7a-MFG.py：直接呼叫 parse 得 **12 積木**（atlas_scan_barcode + 11 qcc_*，
  順序正確）；GUI `/api/scripts/parse` 亦回傳完整 block 樹（11 qcc_* 全在）。
- run_gui.py GET / → HTTP 200。

### 待辦（僅記入 kiro-todo，本階段不做）
- ATE 階段：qcc_enter_mfg（mfg）+ qcc_ate_rf_calibration（觸發/解析 Keysight log），需 VISA。
- 待實機確認：console baudrate、reset 鍵 CLI 替代、setup_QCA.txt port 對應、
  factory reset 後保留行為。
- Pi7 診斷測項規格 .doc 為二進位無法讀取，待轉 txt/pdf 補強校驗門檻。

---

## 2026-09-17（續 8）— GUI toolbox 重整：通用 + 各機型（SoC 命名）

### 症狀 / 需求
- 使用者發現 /blockly 左側只有「📶 Pi7a (QCC74x)」機型分類，卻沒有 EAP111/OAP101。
- 根因：純 MFG 化（續 1）時把 EAP111 的 U-Boot 流程積木（atlas_*）全放進「🔧 工具
  Utility」統一分類，未各開機型 category；續 7 為 Pi7a 開了獨立 category，造成不一致。

### 決策
- toolbox 重整為「通用 + 各機型」，機型 category **以 SoC 命名**（使用者選定）。
- 改名範圍採**層次 A（零風險）**：只改 toolbox category 顯示名稱與積木文字標籤；
  積木內部 type（atlas_* / qcc_*）、generators.js、script_parser.py 全部不動，
  既有 EAP111 腳本/DB workspace 反解析不受影響。

### 做法（純前端，只改 src/web/static/index.html）
- 🔧 工具 Utility：只留通用積木（wait_seconds / wait_ssh_ready / message /
  atlas_scan_barcode / pdu_power_cycle）= 5 積木。
- 🏭 MT7981（新）：EAP111 的 U-Boot 流程積木（atlas_enter_uboot_menu …
  atlas_check_certification）= 13 積木。
- 📶 QCC74x：原「📶 Pi7a (QCC74x)」改名（Pi7a 的 qcc_*）= 11 積木。
- 🔌 Console 製造：維持 = 8 積木。
- OAP101 目前無專屬積木（骨架沿用 MT7981 的 atlas_*），待依 IPQ5018 重寫時再開
  自己的 category。

### 驗證
- 啟動 run_gui.py，抓 index.html：四個 category 齊全，積木數
  Utility=5 / MT7981=13 / QCC74x=11 / Console=8。
- 未動後端流程、generator、反解析與既有腳本（零相容性風險）。

---

## 2026-09-18（續 9）— 監控面板新增「治具接線 / Testbed」唯讀區塊

### 需求
- 使用者：「這台治具怎麼接」應顯示在監控面板。現況監控面板（續 6 純 MFG 版）只有
  執行歷史，移除了 ATLAS 的拓撲圖/設備狀態（Switch/C50，MFG 無關）。
- 接線資訊其實存在 config/test_node/<model>_testbed.yaml，但無頁面呈現。
- 決策：1=a 監控面板加唯讀「治具接線」表格（跟隨型號下拉）；b(圖形化拓撲圖)+
  c(即時狀態) 記入 kiro-todo 後續。2=a 來源跟隨型號下拉。

### 做法
- **app.py** 新增 `GET /api/testbed/{model}`：model 去符號轉小寫 → 讀
  `config/test_node/<stem>_testbed.yaml`；回傳 model/console/ssh/tftp/power/
  pc(label,ip,ports)；`_mask` 遞迴遮罩 key 含 password/passwd/secret/token 的值
  （非空→「••••」），避免把密碼回給 UI；無檔 → 404。
- **dashboard.html**：執行歷史前新增「治具接線 / Testbed」section，含型號下拉
  `tb-model`（來源 /api/profiles，與首頁一致）+ `loadTestbed()` 呼叫
  `/api/testbed/{model}` + `kvTable` 渲染 console/power/tftp/ssh，pc.ports 以
  port/ip/connect_to 表格顯示。因 dashboard 與首頁不共享狀態，dashboard 自帶下拉。

### 驗證
- py_compile app.py OK。
- `/api/testbed/EAP111` 200：console.prompt=MT7981>、power.url=ftdi://ftdi:232h/1、
  tftp.server_ip=192.168.1.2、pc.ports=eth1~4、ssh.password 遮罩（此檔為空字串）。
- `/api/testbed/Pi7a` console.prompt=`qcc74x />`（QCC74x schema 正確）。
- `/api/testbed/NOPE` 404；/dashboard 頁含 tb-model 下拉。

### 後續（見 kiro-todo「監控面板後續」）
- (b) 圖形化拓撲圖（SVG，自訂 MFG 版）。
- (c) 即時狀態偵測（console 連通/上電/ser2net log，可先用 /api/console/status）。

---

## 2026-09-18（續 10）— MFG 站別體系（討論結論，尚未實作）

> 本節記錄與使用者討論 MFG 站別（PT/FT/FDL…）的結論。目前**僅記錄，未動程式**。
> 站別體系刻意設計為「開放可擴充 + 積木跨站共用」，供日後若要做站別維度時參考。

### 三站定義
- **PT 站** — 初測 / 板級測試（板子階段的基本功能）。
- **FT 站** — **組合後測試**（整機組裝後的功能驗證）。
- **FDL 站** — 韌體燒錄（firmware download）。

### 核心性質
1. **站別 = 開放可擴充集合**：不是固定三站，會依需求加開細分站，例如 **PT1、PT2**
   （未來也可能 FT1/FT2…）。因此站別**不可寫死**在程式/目錄；若日後要做站別維度，
   應資料驅動（站別當可設定的清單/欄位）。
2. **PT1/PT2 因「腳本不同」而區分**：細分站是真正不同的流程/測項（不是同測項的多治具
   並行），所以各有各的腳本。
3. **每站別 = 一支對應腳本**：機型 × 站別 → 一支腳本（如 EAP111-FDL、Pi7a-PT、未來
   Pi7a-PT1/PT2…）。
4. **積木跨站共用**（重要）：站別差異只在「用哪些積木、怎麼組合成流程」，**積木本身
   （qcc_* / atlas_* / 通用 wait/message/scan/pdu…）是跨站共用的同一套**，不需為每個
   站別各做一套積木。
   - 推論：**平台/SoC 決定有哪些積木可用；站別決定這次腳本用哪些積木、怎麼排。兩個
     維度正交。**
   - 印證現況：GUI toolbox 按平台/SoC（🏭 MT7981 / 📶 QCC74x）+ 通用分類，**不是按
     站別**分類 —— 正好符合「積木跨站共用」。

### 機型 × 站別現況
| 機型 | 站別 | 對應腳本 | 說明 |
|------|------|---------|------|
| EAP111 | **FDL** | scripts/MFG/EAP111/EAP111-MFG.py | U-Boot tftpboot 燒錄 + 寫號 + TIP 驗證 |
| Pi7a | **PT** | scripts/MFG/Pi7a/Pi7a-MFG.py | factory 寫號 + 板級檢查（依 P/T log；不含 ATE）|
| OAP101 | 待確認 | scripts/MFG/OAP101/OAP101-MFG.py | log 為 U-Boot 燒錄+18 測項，疑似 FDL（待確認）|

### 待確認（本次未收斂）
- OAP101 屬哪一站（疑 FDL）。
- 現有 EAP111 檔案歸屬：EAP111-0010.py、EAP111-TP-001/002.py（檔名 TP 是否 = PT 站）。
- FDL 站的邊界：EAP111-MFG.py 同時含燒錄 + 寫號 + TIP 驗證，這些是否都算 FDL，或
  寫號/驗證應切到別站。
- 同機型是否每站都跑（EAP111 是否也會有 EAP111-PT/FT；Pi7a 是否也會有 Pi7a-FT/FDL），
  或每機型只跑需要的站別。
- Pi7a 的 ATE RF 校準（未實作）在站別體系裡屬 PT 或獨立站。

### 尚未實作（僅討論）
- 本次不改任何程式；站別維度（GUI 站別下拉、腳本依站別組織、run 標站別、testbed 依
  站別）皆未做，待日後有需求時依上述性質（開放可擴充 + 積木跨站共用）規劃。

---

## 2026-09-18（續 11）— MFG 站別體系實作（資料驅動；PT/FT/FDL）

> 續 10 討論定案後實作。原則落實：**開放可擴充（資料驅動）+ 積木跨站共用 +
> 每站一支腳本 + 機型×站別→腳本**。決策組合：A=a1 stations.yaml、B=b1 腳本加
> station 屬性（不動目錄/檔名）、C=c1 GUI 站別下拉+過濾、D=d1 run 記站別。

### 做法
1. **config/stations.yaml**（新）：資料驅動站別清單（PT/FT/FDL；含 PT1/PT2 註解範例）。
   `code`=機器值（存於腳本 station 屬性 + run 紀錄）、`name`=GUI 顯示。加站別=加一筆。
   （微調 2026-09-18：`name` 改為純代碼「PT」/「FT」/「FDL」，說明移到 `description`；
   使用者要求站別下拉只顯示代碼，不顯示「— 韌體燒錄」等說明。）
2. **src/mfg/manufacturing_script.py**：基類加 `station = ""` 類屬性（與 tc_id/headline
   並列，開放集合，腳本自行宣告）。
3. **腳本回填 station**（不動目錄/檔名，只加一行）：
   EAP111-MFG / EAP111-MFG-TEST / EAP111-TP-001 / EAP111-TP-002 / EAP111-0010 = **FDL**；
   OAP101-MFG = **FDL**；Pi7a-MFG = **PT**。
4. **src/web/runner.py**：`_parse_station()`（regex 掃 source 的 `station = "..."`，
   不 import）；`list_existing_scripts()` 每筆加 `station`；`start_run()` 先 `_resolve_script`
   + `_parse_station` 再 `db.create_run(..., station=)`。
5. **src/web/app.py**：`GET /api/stations`（讀 stations.yaml，正規化 code/name/description，
   缺檔 fallback 內建 PT/FT/FDL）；`runs_html` 加「站別」欄（colspan 5→6）。
6. **src/web/db.py**：runs 表加 `station TEXT DEFAULT ''`（含舊 db `ALTER TABLE` 相容）；
   `create_run(station=)`；`list_runs` SELECT 帶 station。
7. **src/web/static/index.html**：header 型號旁加「站別」下拉 `dev-station`（來源
   /api/stations，含「全部」）；`updateScriptList()` 依 **model + station** 雙重過濾
   （設站別時隱藏無 station 的腳本）；`loadStations()` / `onStationChange()`。

### 設計要點
- **積木跨站共用**：toolbox 仍按平台/SoC（MT7981/QCC74x）+ 通用分類，**未按站別**。
  站別只影響「腳本用哪些積木、怎麼排」與清單過濾，不影響積木庫。
- run 的站別由**腳本的 station 屬性**自動記錄（start_run 解析），非使用者另選。
- 未做：GUI 儲存新積木時尚未把 station 注入 generated 腳本（generated 目前無 station
  屬性 → 清單顯示無站別；設站別過濾時會被隱藏）。日後若要 GUI 產生帶站別的腳本再補。

### 驗證（靜態 + GUI，實機無關）
- py_compile：基類 + 6 腳本 + app/runner/db/script_parser 全 OK。
- /api/stations 回 PT/FT/FDL（讀 yaml）。
- /api/scripts 每筆帶 station：EAP111-* / OAP101-MFG = FDL、Pi7a-MFG = PT（正確）。
- 反解析 Pi7a-MFG 仍得 11 個 qcc_*（station 屬性未破壞解析）。
- db runs 欄位含 station（ALTER 對既有 gui.db 生效）。
- index.html 含 dev-station 下拉。

### 對應續 10 待確認（本次定案）
- OAP101 = FDL（使用者確認）。EAP111 全部（含 TP/0010/MFG-TEST）= FDL（使用者確認）。
- 仍開放：同機型是否跨站（未來各站各腳本）、Pi7a ATE 屬 PT 或獨立站 —— 待日後。

---

## 2026-09-18（續 12）— GUI：另存為（跨站別複製）+ 執行中可停止

### 需求
- A「另存為」：同型號的積木可跨 SKU/站別複製。情境：載入 FDL 腳本 → 改積木 →
  另存成 PT 腳本再改（1=a 手動改名+選站別、2=a generated 寫 station、3=a 新檔不覆蓋）。
- B「執行中可停止」：首頁 /blockly 執行時要能停止（2=a 執行鈕原地切換 ⏹ 停止）。
- 現況：後端 stop_run + /api/runs/{id}/stop 早已存在（監控面板用），但首頁 UI 未接。

### 做法
- **後端**：
  - models.py `TestCreate` 加 `station: str = ""`。
  - app.py `POST /api/tests`：若 req.station 非空且 code 未含 station，於第一個
    `tc_id = "..."` 行後注入 `station = "<code>"`（同縮排），再寫入 generated 腳本。
    → 另存的 generated 腳本帶站別屬性，run 記錄站別、站別過濾可辨識。
- **前端 index.html**：
  - 加「📄 另存為」按鈕（btn-save-as，紫色）於 儲存/執行 之間。
  - `currentStation()` 讀 dev-station 下拉。`saveTest()` 也帶 currentStation()。
  - `saveTestAs()`：要求先選站別（否則提示）→ prompt 新名稱（預設建議 `<原名>-<站別>`）
    → POST /api/tests 帶 station（新 tc_id=新名稱，不覆蓋原檔）→ loadScripts 刷新。
  - 停止：`setRunButtonRunning()` 執行中把「▶️ 執行」原地換成紅色「⏹ 停止」
    （onclick=stopCurrentRun→POST /api/runs/{id}/stop）；`setRunButtonIdle()` 於
    ws.onclose 切回綠色「▶️ 執行」。restore-on-load 路徑補設 _currentRunId，讓重載
    後仍可停止。

### 驗證（靜態 + API，實機無關）
- py_compile app.py + models.py OK。
- POST /api/tests station=PT → 寫出 scripts/MFG/generated/ZZTEST-PT.py，第 7 行
  `station = "PT"`（注入正確）。
- HTML 含 btn-save-as / saveTestAs / setRunButtonRunning / stopCurrentRun。
- 已清理測試產物（generated 檔 + db tests row）。

### 注意 / 後續
- generated 腳本**不在** /api/scripts 清單（runner.list_existing_scripts 既有設計
  exclude generated）→ 另存的腳本**不顯示在「搜尋現有腳本」datalist**，但已存檔、可用
  名稱執行、run 會記站別。若要讓另存腳本也出現在搜尋清單並支援站別過濾，需讓
  list_existing_scripts 納入 generated（帶 _parse_station）—— 列為後續小改。
- 站別下拉「全部」時 saveTestAs 會要求先選站別（另存必須指定站別）。

---

## 2026-09-18（續 13）— 另存的 generated 腳本納入搜尋清單（機型 + 站別過濾）

### 需求
- 續 12 的另存腳本放在 scripts/MFG/generated/，被 list_existing_scripts 排除，故不
  出現在「搜尋現有腳本」。本次：讓 generated 腳本也出現在清單並可依 **機型 + 站別**
  過濾（1=b 另存記 model、2=a 混同一清單）。

### 做法
- **src/mfg/manufacturing_script.py**：基類加 `model = ""` 類屬性（generated 用；
  手寫腳本在 scripts/MFG/<MODEL>/ 目錄下仍靠目錄推斷，留空）。
- **models.py**：`TestCreate` 加 `model: str = ""`。
- **app.py `create_test`**：把 station + model 一併在第一個 `tc_id = "..."` 行後注入
  generated 腳本（共用同一 anchor；各自若已宣告則不重複注入）。
- **index.html**：`saveTest` / `saveTestAs` payload 加 `model`（來源 dev-model 下拉）。
- **runner.py**：新增泛用 `_parse_attr(py_file, attr)`（regex 掃 class 屬性）；
  `list_existing_scripts` **不再排除 generated**（仍排除 __pycache__）：
    - generated：model/station 從腳本屬性讀（`_parse_attr`）。
    - 非 generated：model 靠目錄名推斷、station 用 `_parse_station`。

### 驗證（靜態 + API）
- py_compile 基類 + app/models/runner OK。
- POST /api/tests station=PT model=Pi7a → generated ZZGEN-PT.py 第 7/8 行
  `station = "PT"` / `model = "Pi7a"`。
- /api/scripts：ZZGEN-PT(model Pi7a/station PT, path .../generated/)、
  EAP111-MFG(EAP111/FDL, 目錄推斷)、Pi7a-MFG(Pi7a/PT) 皆正確；反解析 Pi7a-MFG 仍
  11 個 qcc_*。已清理測試產物 + db row。

### 效果
- 另存流程端到端打通：另存為 → generated 帶 model+station → 出現在搜尋清單 → 可依
  機型（型號下拉）+ 站別（站別下拉）過濾。
- 前端過濾邏輯（updateScriptList）：model 空的 generated 在任何型號下顯示；有 model
  則依型號過濾；站別同理。

---

## 2026-09-18（續 14）— 治具環境修復：ser2net 自啟 + ttyUSB 固定命名 + FT232H 電源

> 背景：EAP111-MFG-TEST 曾在 Step 1 失敗（telnet 127.0.0.1:5001 refused / connection
> closed）。診斷為**環境問題非程式問題**：ser2net 當下沒跑、ttyUSB 編號漂移、需確認
> FT232H 電源控制。處理順序 b→c→a。

### (b) ser2net 開機自啟 — 已達成（無需動作）
- `systemctl is-enabled ser2net` = enabled、`is-active` = active（Ubuntu 套件自帶 unit
  讀 /etc/ser2net/ser2net.yaml）。先前 refused 只是當下服務沒跑，非未設自啟。

### (c) ttyUSB 固定命名 — 用 VID:PID 綁 udev symlink
- 發現：DUT console 是 **PL2303 (067b:2303)**（非 FT232H）；FT232H (0403:6014) 是電源。
  PL2303 **無唯一序號**（ID_SERIAL_SHORT 不存在），故用 VID:PID 綁定（1=b）。
- 新增 `config/console/99-mfg-serial.rules`：
  - PL2303 067b:2303 → `/dev/mfg-console`
  - FT232H 0403:6014 → `/dev/mfg-power`
  - 附 KERNELS(USB 埠路徑)綁定的註解版，供日後多顆同型晶片時切換。
- `config/console/ser2net.yaml` 的 connector **原改為 `/dev/mfg-console`（2=a），但後續
  發現 ser2net 用 symlink 有疑慮、且真正病因是連線槽（見續 15），最終 connector
  改回實體 `/dev/ttyUSB0`**。udev 的 mfg-console/mfg-power symlink 保留作「識別哪顆是
  哪顆」，不給 ser2net 用。
- 套用（sudo，使用者執行）：
  ```
  sudo cp config/console/99-mfg-serial.rules /etc/udev/rules.d/99-mfg-serial.rules
  sudo udevadm control --reload-rules && sudo udevadm trigger
  sudo cp config/console/ser2net.yaml /etc/ser2net/ser2net.yaml
  sudo systemctl restart ser2net
  ```
- 實機驗證：`/dev/mfg-console -> ttyUSB0`、`/dev/mfg-power -> bus/usb/001/024`；
  5001 仍在聽。

### (a) FT232H 電源控制 — 已解綁 + 實測可切換
- `sudo bash tools/setup_ft232h_gpio.sh` → ftdi_sio 無綁定（good）；/dev/ttyUSB0 為
  PL2303 console（保留正常）。
- 電源實測（PROTech-MFG .venv）：
  `PowerController(url='ftdi://ftdi:232h/1', active_high=False).relay_off(1)/relay_on(1)`
  → RELAY_TOGGLE_OK（relay 實際切換）。

### 結論
- 環境三項到位；EAP111-MFG-TEST Step 1 應可通過（console 連得上 + DC Jack 會真的
  斷電重開進 U-Boot menu）。程式面（Pi7a 實作/站別/GUI）先前已驗證無誤。
- 部署新治具時：套用 99-mfg-serial.rules（依實際 VID:PID/埠調整）+ setup_ft232h_gpio.sh
  + ser2net.yaml 指向 /dev/mfg-console。

---

## 2026-09-18（續 15）— EAP111-MFG-TEST 實機跑通：三個問題定位與修正

> 一連串 console 失敗的排查最終 PASS。真正卡關的是 ser2net 連線槽被多個 GUI 佔滿；
> 過程中另修好兩個真 bug（GUI 儲存、TP-001 錯誤處理）。

### 問題 1（真正根因）— ser2net max-connections 被多個 GUI 佔滿
- 症狀：EAP111-MFG-TEST Step 1 進 U-Boot menu 後，console 連上 5001、`MT7981>` 出現，
  約 1 秒後 `Connection closed by foreign host` → FAILED。ser2net log 一直有
  `ttyUSB0: Error accepting a gensio: Remote end closed connection`。
- 根因：**同時開了多個 GUI 實例（run_gui.py 8020 + 8021 + …）**，每個 GUI 的即時
  Console 監看（console_stream）會**常駐佔一條 5001 連線**；`max-connections: 2` 被
  佔滿 → pytest 子行程的 console 連線被踢。之前偶爾成功/偶爾空白，就是連線槽時滿時
  不滿。
- 處置：kill 多餘 GUI（只留一個）→ 立即可跑通。根治：`config/console/ser2net.yaml`
  `max-connections: 2 → 4`（留給 2-3 個 GUI + 測試）。套用：
  `sudo cp config/console/ser2net.yaml /etc/ser2net/ser2net.yaml && sudo systemctl restart ser2net`。
- 教訓：console 全空白 / 連上被關，先查 `ss -tn | grep :5001` 的連線數與
  `pgrep -af run_gui.py`，不要一開始就懷疑硬體。

### 問題 2（真 bug，已修）— GUI「儲存」無反應、沒存進去
- 症狀：按「💾 儲存」沒任何 alert、DB/generated 都沒東西。
- 根因：`src/web/static/generators.js` `generateTestFile()` 讀 `getElementById('dev-type').value`，
  但純 MFG 版 index.html 已移除 dev-type → `null.value` 丟 TypeError → saveTest 中斷。
- 修正：`var devType = (document.getElementById('dev-type') || {}).value || 'mfg';`
  （防護 + 純 MFG 預設走 MFG 模板）。dev-model 亦加防護。

### 問題 3（真 bug，已修）— EAP111-TP-001.py finally 掩蓋錯誤
- 根因：iperf3 未裝時 `subprocess.Popen(["iperf3",...])` 丟 FileNotFoundError，`server`
  未賦值 → finally `server.terminate()` 再丟 NameError，蓋掉真正錯誤。
- 修正：`server=None` 初始化；Popen 包 try/except FileNotFoundError → 明確報
  「iperf3 not found — apt-get install -y iperf3」；finally `if server is not None`。

### 排除但非病因（已確認 OK）
- ser2net enabled+active；FT232H 電源 relay 軟體 toggle OK（PDU ok）；DUT 確實斷電
  重開（電源燈熄再亮）；console 線/baudrate 正常（boot log、U-Boot menu、MT7981> 都
  正常出現）；connector 用 symlink vs 實體 ttyUSB0 皆非病因（病因是連線槽）。

### 結果
- EAP111-MFG-TEST：✅ PASSED（整輪跑通）。
- 續 14 的 connector 已回正為 /dev/ttyUSB0（見該節修正）。

---

## 2026-09-18（續 16）— Pi7a 對齊規格 v0.5（testbed 指令 + 積木文字）

> 取得官方規格書 `docs/logfiles/Pi7_Diagnostic_Test_Items_version_v0.5_20260911.md`
> （Accton, Rev v0.5, CPU QCC748）。使用者決定：**以規格 v0.5 為準**（非實機 PASS log）。

### 規格 vs 實機 log 的差異（已對齊為規格版）
| 項目 | 實機 log | 規格 v0.5 | 採用 |
|------|---------|-----------|------|
| WDT | `dt_reboot` | `wdt_reboot`（§2.1.6）| **wdt_reboot** |
| factory 讀 | `factory` | `factory r`（§2.1.21）| **factory r** |
- 其餘核心子集指令（diag_version/mm_version/power_mode/battery_mode/
  fuel_gauge(SY6410)/i2c_scan/led/factory w）規格與 log 一致，未動。

### 變更
- **config/test_node/pi7a_testbed.yaml**：`factory_read_cmd` `factory`→`factory r`；
  `wdt_cmd` `dt_reboot`→`wdt_reboot`。後端 qcc_* 方法讀 self.mfg，自動吃新值（無需改碼）；
  `factory r` 輸出六欄與 `factory` 相同，qcc_factory_check 解析相容。
- **src/web/static/blocks.js**（僅 label/tooltip，不動 type/generator/反解析）：
  `qcc_wdt_test` label+tooltip `dt_reboot`→`wdt_reboot`；
  `qcc_factory_check` label `factory read back`→`factory r`。

### 驗證
- testbed 載入：factory_read_cmd=`factory r`、wdt_cmd=`wdt_reboot`。
- blocks.js：無真正殘留舊字樣（`wdt_reboot` 含 `dt_reboot` 子字串為 grep 誤報）；
  規格用語到位；GUI GET / 200。

### 注意
- 若實機韌體較舊（只認 dt_reboot/factory），Pi7a-MFG 跑到 WDT/factory 讀會失敗；
  屆時把 testbed 這兩值改回 log 版，或確認/升級韌體。已記於 kiro-todo。
- 規格提供但未實作的擴充 CLI（gpio/i2c get,set,dump/mm_test/mm_scan/ble_*/wifi_*/mfg）
  待 BLE/WiFi/ATE 階段再做成積木（見 kiro-todo Pi7a 段落）。

---

## 續 17：多機型 console baudrate 解法（RFC2217 動態協商，單一 5001 port）

### 問題
同一實體 console 裝置 `/dev/mfg-console`（udev 綁 EAP111 PL2303 067b:2303 + Pi7a
CH340 1a86:7523，一次只接一台），但兩種 DUT baudrate 不同：
EAP111=115200、Pi7a=2000000（DUT banner「Pi7a Baud Rate:2000000」）。

### 作廢的錯誤嘗試（雙 ser2net port）
曾用 5001@115200(EAP111) + 5002@2000000(Pi7a) 共用同一 `/dev/mfg-console`。
**失敗**：ser2net 不能讓兩個 connection 同時開同一實體裝置（`Object was already
in use` / `Port in use`），且 GUI 即時 Console 常駐連 5001 佔住裝置。**此方案作廢**，
ser2net.yaml 的 5002 block 與 pi7a_testbed 的 5002 port 皆已移除/改回。

### 採用方案：RFC2217 動態 baudrate（單一 5001 port）
ser2net 單一 port 5001 用 `telnet(rfc2217)` accepter；client 連線時依 testbed
baudrate 透過 RFC2217 協商 → 同一 port 同一裝置，baudrate 隨機型自動切換。
EAP111(115200) 與 Pi7a(2000000) 都連 5001。

### 變更
- **src/mfg/console.py**：
  - telnet 模式改用 pyserial `serial.serial_for_url('rfc2217://host:port',
    baudrate=testbed.baudrate)`（自動協商速率），取代原 `pexpect.spawn("telnet")`
    （系統 telnet 不送 RFC2217 SET_BAUDRATE）。
  - **關鍵坑**：rfc2217 pyserial 物件是 socket-backed，無真 `fileno()`，
    `pexpect.fdpexpect.fdspawn` 用不了（`io.UnsupportedOperation: fileno`）。
    → 新增 **`_SerialExpect`**：pexpect 相容薄包裝（`sendline`/`sendcontrol`/
    `expect(pattern|list)`→回 index + `.before`/`.after`/`close`），底層直接讀寫
    pyserial read()/write()。**Console 對外介面(drain/send/expect/expect_index/
    send_and_expect/close)完全不變**，picocom(serial) 路徑仍走原 pexpect（EAP111
    picocom 場景零影響）。
  - **ANSI escape 過濾**（`_ANSI_RE`）：QCC74x firmware 給 prompt 上色
    （`ESC[36m qcc74x /> ESC[0m`），讀入時 strip 掉 CSI/SGR 等序列，讓 buffer/log
    乾淨。純文字 prompt 比對不受影響（顏色碼在文字前後）。
  - close()：telnet(rfc2217) 不再送 picocom 退出鍵(Ctrl-A Ctrl-X)，並關 `_serial`。
- **config/console/ser2net.yaml**：回到單一 5001（`telnet(rfc2217)` accepter +
  `serialdev,/dev/mfg-console,115200n81,local`）；移除 5002 block。115200 只是
  client 協商前的預設。
- **config/test_node/pi7a_testbed.yaml**：console port 5002→**5001**，baudrate
  維持 2000000（rfc2217 協商）。
- **src/mfg/manufacturing_script.py `qcc_connect`**：QCC74x boot 完停在
  `[App] Starting USB Virtual COM` 後 console 靜止、**不會自動再印 prompt**，需按
  Enter。改為 boot 後用「送 Enter → 短 expect(3s)」重試迴圈直到拿到 `qcc74x />`
  或總 timeout。

### 驗證（皆實機 Pi7a，DUT 2000000）
- `.venv` 有 pyserial 3.5 + `serial.rfc2217` + `pexpect.fdspawn`（後者因無 fileno
  棄用）。
- rfc2217 client 連 5001 @2000000 → `is_open=True`（ser2net 現有 rfc2217 支援遠端設速率）。
- 手動 Console connect/drain/expect → 讀到 `qcc74x />`（無亂碼＝2M 協商正確）。
- 手動 `qcc_connect(timeout=90)` → DC OFF/ON → rfc2217 @2000000 → 送 Enter 重試 →
  `QCC74x CLI prompt "qcc74x />" confirmed` = **PASS**。
- ANSI strip 單元：`\x1b[0m\x1b[36mqcc74x />\x1b[0m` → `qcc74x />`；實測 log 為乾淨
  `[console] qcc74x />`（無 ESC）。
- py_compile console.py / manufacturing_script.py OK；ser2net.yaml YAML OK；
  pi7a_testbed port=5001 baud=2000000。

### 附帶修正（保留）
- **conftest.py**：MfgItem.runtest 依 model 自動選 `<model>_testbed.yaml`
  （model 來源：tc.model 屬性 → 腳本路徑目錄名 → fallback eap111），取代原寫死
  fallback eap111。generated Pi7a-MFG-001 有 model="Pi7a" → 正確選到 pi7a_testbed。
- **manufacturing_script.py `_qcc_send`**：送指令前先 `drain()`。根因：QCC74x
  firmware 非同步吐背景訊息（wifi/BLE/Morse Micro init），上一指令結束後在 buffer
  遺留舊 `qcc74x />`（log 見 `qcc74x />Morse Micro driver initial`）。下一指令
  send 後 expect(prompt) 立即匹配到殘留舊 prompt → `.before` 空 → 誤判 FAIL
  （實例：power_mode 1 只見殘留 prompt + Morse 訊息而 AssertionError）。drain 後
  匹配到的 prompt 才屬於本指令回應。此修正對所有 qcc_*（走 _qcc_send）皆生效。
  實測 power_mode 0/1 皆正確得 USB power → PASS。
- **power_mode 判定確認（無需改）**：qcc_power_mode_test 對 bus 0/1 送 `power_mode
  {bus}`，輸出含 `USB power` 或 `Battery power` 皆 OK（記錄實際值），兩者皆無才 fail
  —— 與規格「USB power (OK) or Battery power (OK)」一致。

### 待辦 / 注意
- ser2net.yaml 已改，需 sudo 套用到 /etc/ser2net/ser2net.yaml + restart（若現有
  5001 已是 rfc2217，測試其實已可跑；套用主要為移除 5002 與更新註解）。
- EAP111 telnet 現在也走 `_SerialExpect`(rfc2217 @115200)——**須實機重跑一次
  EAP111-MFG-TEST 確認新 console 路徑對 EAP111 也 OK**（先前 EAP111 是走舊
  `pexpect.spawn("telnet")`，路徑已換）。
- GUI 即時 Console(console-stream) 若仍用舊 telnet 顯示 Pi7a 可能亂碼（沒走 rfc2217
  設 2M）；測試腳本(console.py)不受影響。GUI 監看 baudrate 為另議。
- Pi7a factory partition 未燒錄（boot log「No valid data in Factory, load default」／
  「No usable MAC ... burn via factory w first」），S/N/MAC 為 default 值；
  qcc_factory_check 預期值(default vs 實燒)判定待與使用者確認。

---

## 續 17 補充：Pi7a 實機跑通過程的修正（console + 各 step 判定 + GUI 提示）

依實機 Pi7a-MFG / Pi7a-MFG-TEST 逐步 debug，除前述 rfc2217/_SerialExpect 外，另完成：

### A. qcc_connect 送 Enter 重試（已實機 PASS）
QCC74x boot 完停在 `[App] Starting USB Virtual COM` 後 console 靜止、**不自動再印
prompt**，需按 Enter。qcc_connect 改為 boot 後「送 Enter → 短 expect(3s)」重試迴圈直到
拿到 `qcc74x />` 或總 timeout。

### B. _qcc_send 送指令前 drain（已實機驗證 power_mode 0/1 PASS）
QCC74x 非同步吐背景訊息(wifi/BLE/Morse)，上一指令結束後遺留舊 `qcc74x />`；下一指令
expect 立即匹配到殘留 prompt → `.before` 空 → 誤判 FAIL（實例 power_mode 1）。_qcc_send
送前先 drain，對所有 qcc_* 生效。

### C. GUI 即時 Console ANSI 過濾（console_stream.py）
QCC74x 逐字上色（每字元包 `ESC[0m`），GUI 監看(console_stream，走 ser2net trace log
tail，非 console.py)未過濾 → 滿是 `␛[0m`。console_stream.py 加 `_ANSI_RE`（同 console.py），
backlog 與增量 chunk 送前端前 strip。注意：GUI 監看與測試腳本是**兩條獨立路徑**，兩邊都各自
過濾了。

### D. qcc_check_versions 加 mm_version 期望值積木欄位（GUI 可設）
需求：讓 mm_version 比對值由 GUI 積木控制（原本只記錄不比對）。改 4 處一致：
- blocks.js：積木加 `MM_EXPECTED` 文字欄位（留空=只記錄）。
- generators.js：有填才產 `qcc_check_versions(mm_expected="...")`，留空產無參數版。
- manufacturing_script.py：`qcc_check_versions(self, mm_expected="")`，非空則需「包含」
  否則 AssertionError（填 `1.5.0` 即前綴比對，可容忍 build number `-295/-299` 差異）；
  留空只記錄。diag_version 維持吃 testbed diag_version_expected。
- script_parser.py：反解析從 `mm_expected="..."` 回填 MM_EXPECTED。
- 注意：實機 mm_version=`1.5.0-299`、規格 v0.5=`1.5.0-295`（build number 不同）；建議
  GUI 填 `1.5.0` 比主版本。
- 驗證：留空只記錄／填 1.5.0 或 1.5.0-299 OK／填 1.5.0-295 正確 raise；反解析回填 OK。

### E. Reset button：GUI 純告知 modal + 後端偵測按太短
問題：qcc_reset_button_test 只 `self.message` 叫操作員按住 ≥5s，GUI **沒有提示視窗**，
且實機按太短(200ms)只得模糊 timeout。使用者選 1=a(純告知 modal)、2=y(偵測按太短)。
- 後端 qcc_reset_button_test：改用 `expect_index` 同時等 `Resetting easyflash to
  defaults`(成功) 與 `[RESET BTN] Released after (N) ms (need (M) ms)`(按太短)；按太短
  給明確訊息(含 N/M ms)並**重試等待**(不立即 fail)直到成功或總 timeout。
- 前端 index.html：加 `#reset-modal`(醒目告知視窗，無輸入) + openResetModal/
  closeResetModal；onmessage 偵測 `Please HOLD the reset button`→開窗、`released too
  early`→更新「放太快重按」、`Reset to defaults detected`/`QccWdtTest`/`Step 11`/
  `factory preserved`→自動關；ended/onclose 也關。**純告知型**（DUT 偵測到按壓就自動繼續，
  GUI 不需回送）。

### F. 依規格 v0.5 逐一對齊 qcc_* 判定（使用者確認 1=a 2=y 3=y；mock 驗證通過）
規格來源：`docs/logfiles/Pi7_Diagnostic_Test_Items_version_v0.5_20260911.md`
§2.1.3~2.1.6 / §2.1.20~2.1.21。
- **battery_mode §2.1.3**：加 FAIL 偵測——`I2C read error` 或 `Battery Missing!` → raise；
  正常記錄 `Battery Discharging/Charging => OK`。(原本只查有無 'Battery'，會把 Missing 誤判 PASS)
- **fuel_gauge §2.1.4**：**移除電壓範圍硬檢查**（規格 PASS 範例本身即 `Fail to read from
  I2Cx 0x30 register 0x02`，此板無真正 fuel gauge 電壓）。改為：有 `SY6410 FUEL GAUGE
  STATUS:` 標頭或任何輸出即 OK，記錄實際狀態。(原本強制解析 voltage → 一定 fail)
- **led §2.1.5**：`led all on` 加回顯驗證需含 `Pi7 LED all on`(或 'LED')，否則 raise；
  仍靠操作員視覺確認實際燈。
- **wdt §2.1.6**：fallback `wdt_cmd` 由舊 `dt_reboot` 改 `wdt_reboot`；expect
  `Force WDT reboot after N seconds`(含 generic fallback)。
- **factory w/r §2.1.20/21**：六欄格式(halow/wifi/ble_mac + S/N + Model + HWver)已對齊，
  保留。

### 驗證彙總（本補充）
- py_compile manufacturing_script.py / console_stream.py / script_parser.py OK。
- index.html reset-modal 元素/函式齊全、braces 平衡；blocks.js/generators.js 括號平衡。
- mock：battery(正常/Missing/I2C err)、fuel_gauge(Fail to read 記錄)、led(回顯/無回顯)、
  mm_version(留空/前綴/精確/不符) 全數符合預期。
- 實機已驗：qcc_connect PASS、power_mode 0/1 PASS、console log 乾淨無亂碼。

### 尚待實機驗證 / 待決
- 重啟 GUI 後端讓 index.html + console_stream.py 生效，實機重跑 Pi7a-MFG-TEST 整支
  （Step 10 reset 提示視窗、按住實體 ≥5s；fuel_gauge 不再硬 fail）。
- Pi7a SN 長度：Step 0 scan_barcode 的 expected_len 原沿用 12 導致 `ECSN012345678`(13)
  fail；使用者已於 GUI 積木改對(流程已能跑到 factory 之後)。SN 規則(固定 13/前綴)未最終定案。
- reset button 目前純人手按；是否改治具自動觸發未定（使用者未回 b/c）。
- EAP111 telnet 現走 _SerialExpect(rfc2217 @115200)，仍需實機重跑 EAP111-MFG-TEST 確認。
- ser2net.yaml 需 sudo 套用(移除 5002)。
- Pi7a factory 未燒錄(default MAC/SN)，qcc_factory_check 預期值判定(default vs 實燒)待定。
