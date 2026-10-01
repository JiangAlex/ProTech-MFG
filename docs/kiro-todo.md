# ProTech-MFG 待辦（kiro-todo）

> 待實作 / 待決策事項。慣例：技術解釋用繁體中文；變數 / 函數 / 檔名 / 代碼保持英文。

---

## OAP101 MFG 支援（分析自 PASS log，尚未實作）

參考 log：`docs/logfiles/OAP101_WW_PASS_Y_V0.7.1E.4.0_205216.cap`
（SN=EC2516004150, MAC=C0C989AD2A6C, Model=OAP101-6E-0622-WL, TP Ver V0.7.1E.4.0）

### 【關鍵發現】OAP101 與 EAP111 是完全不同平台，MFG 流程根本不同
不是「改 ap.mfg 幾個參數」能支援的 —— **流程步驟本身不同**，需獨立實作。

| 項目 | EAP111 | OAP101 |
|------|--------|--------|
| SoC | MediaTek MT7981 | **Qualcomm IPQ5018** |
| U-Boot prompt | `MT7981>` | **`IPQ5018#`** |
| U-Boot 版本 | 2023.04 | 2016.01 (Feb 07 2023) |
| machid | — | `8040004` |
| NAND | serial NAND (nmbm) | Winbond W25N02JWZEIF 256MiB + NOR SPI W25Q128FW 16MiB |
| 燒錄方式 | `tftpboot`+`nmbm write` 固定 offset | **`nand scrub -y 0x0 0x8000000`→`nand erase`→`tftpboot <img>`→`imgaddr=$fileaddr && source $imgaddr:script`→`sf erase 0x1e0000 0x10000`→`reset`**（image 內含燒錄 script）|
| 韌體檔名 | tip_fip.bin + squashfs-factory | **`norplusnand-ipq5018-apps-OAP101-v0.7-20240123.img`**（單一 img, ~46MB, load 0x44000000）|
| 讀 HW 版本 | U-Boot `mtd read factory`+`md.b` offset | **無 factory MTD 讀取**；MAC 從 ART 分區 |
| 寫 SN/MAC/HW | U-Boot `setenv`+`saveenv` | **Linux 下 `sh oap101_mac all <SN> OAP101 R01 <MAC-prefix>:<MAC-suffix>`**（寫 ART /dev/mtd16）|
| root 登入 | 有密碼 `ail:oY7R` | **無密碼**（`There is no root password defined`, prompt `root@OpenWrt:/#`）|
| Linux 主控台路徑 | login: → root | 進 runtime 後直接 `root@OpenWrt`，工作目錄 `/etc/Accton` |
| 電源 | Terminal block relay (FT232H) | **Terminal Block + PoE 雙電源**（log 有 PoE Power ON/OFF）|

### OAP101 完整流程（依 PASS log，18 個測項，共 257 秒）
1. `_f_TerminalBlckPwrOn` — Terminal Block 上電 → 等 `IPQ5018#`
2. `_f_CheckPhyInit` — `setenv serverip 192.168.2.19 && setenv ipaddr 192.168.2.1`；
   `setenv gatewayip 255.255.255.0`；`ping 192.168.2.19` → `host ... is alive`
3. `_f_UpdateDiagCode` — `nand scrub -y 0x0 0x8000000` → `nand erase 0x0 0x8000000`
   → `tftpboot norplusnand-ipq5018-apps-OAP101-v0.7-20240123.img`
   → `imgaddr=$fileaddr && source $imgaddr:script`（flash ubi + wifi_fw）
   → `sf probe` → `sf erase 0x1e0000 0x10000`（清 APPSBLENV）→ `reset`
4. `_f_UbootVerAndDdrTest` — `version`（比對 U-Boot 2016.01）；
   `mtest 0x44000000 0x45000000 0xaa55aa55 10`
5. `_f_IntExtAntenaSet` — `setenv bootargs console=ttyMSM0,115200n8
   cnss2.bdf_integrated=0x24 cnss2.bdf_pci0=0x60` → `save` → `run bootcmd`（boot Linux）
6. `_f_EnterRunTimeMode` — 等 Linux boot 到 `root@OpenWrt:/#`（無密碼），
   `cd /etc/Accton`（115 秒，含 coldboot calibration）
7. `_f_CheckDiagVer` — `cat /etc/oap101_diag_version` → `Version: 0.7`
8. `_f_CheckAntaBdWlanFile` — `dmesg | grep bdwlan.b24` / `bdwlan.b60`
9. `_f_I2cTest` — `sh i2c_tpm.sh`（TPM STM）
10. `_f_TemperatureHeaterTest` — `sh heater_test.sh 1/2 on/off` + `sh tmp102.sh`（溫差 > 2 度 PASS）
11. `_f_CheckEthPHYLinkUp` — `dmesg | grep "Link up"`（eth0 1000, eth1 2500）
12. `_f_EthSpedLikPngTest` — `sh eth_speed.sh eth0 1000` / `eth1 2500`；ping
13. `_f_CheckAntBdWlanMd5sum` — `md5sum /lib/firmware/.../bdwlan.b24/b60/bb0/...`
14. `_f_CheckLEDTest` — `sh led_test.sh all/orange/green/blue on/off`
15. `_f_ResetButnTest` — `sh reset_button_detect.sh`
16. `_f_WrtSnMacHwVer` — **`sh oap101_mac all EC2516004150 OAP101 R01 C0:C9:89:AD:2A:6C`**
    （寫 5 個 MAC：eth0/eth1/wifi0/wifi1/wifi2 遞增，寫入 ART /dev/mtd16）
17. `_f_WdtTest` — `sh wdt_sw_rst.sh`（含 CC26X2R1 韌體 CRC 檢查 via /dev/ttyMSM1）
18. `_f_PoEPowerOn` — Terminal Block OFF → PoE Power ON → 等 `IPQ5018#`

### 實作方向（待決策）
- **不建議**硬套 EAP111 的 U-Boot(nmbm/mtd) 流程 —— 機制完全不同。
- **方向 1（建議）**：OAP101 用獨立 MFG script + 新增 OAP101/IPQ5018 專屬後端方法
  與積木：
  - 可共用：console 連線、`_uboot_send`（prompt 換 `IPQ5018#`）、message、wait、
    ssh、Linux 登入（改支援無密碼直接進 shell）。
  - 需新增（IPQ5018/OAP101 專屬）：ipq_check_phy_init / ipq_update_diag_code /
    ipq_uboot_ddr_test / ipq_set_antenna_bootargs / oap101_enter_runtime /
    oap101_check_diag_version / oap101_check_bdwlan / oap101_i2c_tpm_test /
    oap101_heater_test / oap101_led_test / oap101_reset_button_test /
    oap101_eth_speed_test / oap101_write_mac（sh oap101_mac ...） /
    oap101_wdt_test / oap101_poe_power_on / PoE 電源控制。
- `ap.mfg` 參數化可用於 uboot_prompt=IPQ5018#、韌體檔名、diag 版本字串等；但大多
  是新流程方法，不是舊流程換參數。

### 待確認（硬體/規格）
- OAP101 console 是否也走 ser2net telnet？baudrate？
- PoE 電源如何控制（PDU？另一個 relay？）— Terminal Block + PoE 雙電源切換。
- TFTP server IP：log 用 192.168.2.19（EAP111 用 192.168.1.2），OAP101 testbed 網段待調。
- 是否移植全部 18 測項，或先做核心（燒錄 + 寫 MAC + 版本檢查）子集。
- oap101_mac / heater_test.sh / led_test.sh 等是 DUT firmware 內建（/etc/Accton/），
  框架只需下指令；確認 image 燒錄後這些 script 存在。

### 目前骨架（僅 prompt 等少數可沿用；MFG 流程尚未依 OAP101 改寫）
- config/test_node/oap101_testbed.yaml（ap.mfg 仍是 EAP111 值 + TODO；
  **需改 uboot_prompt=IPQ5018#、韌體檔名、網段、password 空**）
- scripts/MFG/OAP101/OAP101-MFG.py（目前呼叫 EAP111 流程方法，**對 OAP101 不適用**，
  需依方向 1 重寫）

---

## Pi7a MFG 支援（核心子集已實作；ATE RF 校準待辦）

> **狀態更新（2026-09-17）**：核心子集已實作並通過靜態驗證（py_compile + GUI 反解析）。
> 已實作：factory 寫/讀（SN/MAC）+ 版本檢查（diag/mm）+ i2c scan + fuel gauge +
> power/battery mode + LED + reset button + WDT。
> 檔案：config/test_node/pi7a_testbed.yaml（QCC74x schema）、
> src/mfg/manufacturing_script.py（qcc_* 方法）、scripts/MFG/Pi7a/Pi7a-MFG.py（核心子集流程）、
> src/web/static/blocks.js+generators.js（qcc_* 積木）、src/web/script_parser.py（qcc_* 反解析）、
> src/web/static/index.html（📶 Pi7a (QCC74x) toolbox）。實機由使用者在治具驗證。
> **ATE RF 校準（Keysight）尚未實作**（見下方「後續」）。

### 後續（ATE 階段，尚未實作）
- `qcc_enter_mfg`（送 `mfg` 進 MFG 韌體）+ `qcc_ate_rf_calibration`（觸發/解析
  Keysight E6680E 的 TX_Verify/RX_Verify log），需 VISA 環境與 ATE 工具細節。
- 待實機確認：console baudrate、reset 鍵是否有 CLI 替代（目前為實體按壓）、
  `setup_QCA.txt` Connection_ComPort 對應治具 port、factory reset 後保留行為。
- Pi7 診斷測項規格已解析（`docs/logfiles/Pi7_Diagnostic_Test_Items_version_v0.5_20260911.md`，
  Accton, Rev v0.5, CPU **QCC748**）。重點：
  - **已依規格對齊 testbed（2026-09-18）**：`factory_read_cmd` `factory` → **`factory r`**
    （§2.1.21）；`wdt_cmd` `dt_reboot` → **`wdt_reboot`**（§2.1.6）。核心子集其餘指令
    （diag_version/mm_version/power_mode/battery_mode/fuel_gauge(SY6410)/i2c_scan/
    led/factory w）與規格一致。
  - factory 讀回衍生確認：halow=base、wifi=base+1、ble=base+2（與 _mac_add 一致）。
  - shopfloor 版本基準：`mm_version` = **1.5.0-295**（§2.1.19，可作 check version 門檻）。
  - **規格提供、尚未實作的擴充 CLI**（未來 ATE/BLE/WiFi/GPIO 階段可用）：
    gpioset/gpioget、i2cget/i2cset/i2cdump、mm_test（Porting Assistant）、
    mm_scan/mm_scan_stop、ble_*（scan/init/adv/auth…）、
    wifi_scan/wifi_sta_connect/set_ipv4/ping/iperf、mfg（進 MFG 模式）。
  - 注意：規格 v0.5 與實機 PASS log 對 wdt/factory 指令曾不一致（log 為 dt_reboot/
    factory）；已依使用者決定**以規格 v0.5 為準**。若實機韌體較舊，需回退或確認韌體版本。

### 平台特性與流程（原分析，保留供參考）

參考 log：`docs/logfiles/Pi7a-EC2617002807_PASS_N_1_132811.txt`
（SN=EC2617002807, MAC=4445BA15E59C, Model=Pi7a-0825-WL, HWver=R0B, TP Ver=V0.3.1H.1.3）

### 【關鍵發現】Pi7a 是第三種平台，與 EAP111/OAP101 均不同（QCC74x，無 U-Boot）
不是 U-Boot tftpboot 燒錄流程；韌體預燒，MFG = 韌體 CLI 校驗 + `factory w` 寫 SN/MAC
+ `mfg` 進校準模式 + 外部 Keysight ATE 做 RF TX/RX 驗證。

| 項目 | EAP111 | OAP101 | Pi7a |
|------|--------|--------|------|
| SoC | MediaTek MT7981 | Qualcomm IPQ5018 | **Qualcomm QCC744 (QCC74x)** |
| Console prompt | `MT7981>` | `IPQ5018#` | **`qcc74x />`**（韌體 CLI，非 U-Boot）|
| Flash | serial NAND (nmbm) | NAND 256MiB + NOR 16MiB | **8MB SPI NOR**（jedec 0x1740EF）|
| 燒錄 | U-Boot tftpboot+nmbm | U-Boot nand+tftpboot+source | **無（韌體預燒）** |
| 無線模組 | MT7981 wifi | IPQ5018 wifi | **HaLow: Morse Micro MM8108B2** |
| 寫 SN/MAC | U-Boot setenv+saveenv | Linux `sh oap101_mac ...` | **CLI `factory w <MAC> <SN> <Model> <HWver>`** |
| 讀 factory | U-Boot mtd read | Linux 讀 ART | **CLI `factory`（印 halow/wifi/ble mac+SN+Model+HWver）** |
| RF 校準 | — | — | **外部 Keysight E6680E ATE (TCPIP VISA)** |
| 電源 | FT232H relay | Terminal Block + PoE | **DC Jack Power ON/OFF**（+ Battery/USB 雙電源；relay 機制待確認）|

### Pi7a 完整流程（依 log Footer 摘要：20 測項，共 180 秒，PASS）
1. `_f_plugPowerCable`（x2）— DC Jack Power ON，等 boot 到 `qcc74x />`
2. `_f_battryPowerModeTest` — `power_mode 0/1` → `Battery power`
3. `_f_batteryModeTest` — `battery_mode 0` → `Battery Discharging`
4. `_f_fuelGaugeTest` — `fuel_gauge 0/1` → 電壓 2.5~4.2V（SY6410）
5. `_f_displyFwInfo` — `diag_version`(Pi7_V0.3) + `mm_version`(1.5.0-299)
6. `_f_usbPowerModeTest` — `power_mode 0/1` → `USB power`
7. `_f_i2cScanTest` — `i2c_scan`/`i2c_scan1` → 0x30,0x3F；`i2cget 0/1 3f 09`（25秒）
8. `_f_haLowSDKPortingVald` — `mm_test`（MM-IoT-SDK Porting Assistant，13 步 11 pass）
9. `_f_wrtSnMac` — **`factory w 44:45:BA:15:E5:9C EC2617002807 Pi7a-0825-WL R0B`** → `factory` 讀回驗證 6 欄
10. `_f_preSetupRfConfig` — 更新 `Connection_ComPort=4` 到 `setup_QCA.txt`（PC 端）
11. `_f_enterMfgTest` — `mfg` → 等 `mfg task is running`/`Enter mfg test mode OK`（含大量 RF calibration trace）
12. `_f_ateRfCalibrationTest` — **Keysight E6680E ATE**：TX_Verify(36)/RX_Verify(36) PASS（108 秒）
13. `_f_plugPowerCable` — DC Jack OFF→ON（重啟）
14. `_f_resetButtonTest` — reset 鍵按住 ≥5s → `Resetting easyflash to defaults`（38 configs；**不清 factory 分區**）14秒
15. `_f_checkSnMac` — `factory` 讀回再驗 6 欄（確認 reset 後 factory 未被清）
16. `_f_ckeckLEDTest` — `led all on` / `led off`
17. `_f_trigWatchDogTest` — `dt_reboot` → `Force WDT reboot after 6 seconds` → 重啟成功（9秒）

### 實作方向（待決策）
- 屬 **情況 B（不同平台）**：需新增 QCC74x/Pi7a 專屬後端方法與積木，共用
  console/wait/message/ssh。
- 可共用：console 連線（prompt 換 `qcc74x />`）、message、wait、DC Jack 電源控制。
- 需新增（QCC74x/Pi7a 專屬）：qcc_power_mode_test / qcc_battery_mode_test /
  qcc_fuel_gauge_test / qcc_diag_version / qcc_mm_version / qcc_i2c_scan /
  qcc_halow_sdk_validation(`mm_test`) / qcc_factory_write(`factory w ...`) /
  qcc_factory_check(`factory` 讀回) / qcc_enter_mfg(`mfg`) / qcc_led_test /
  qcc_reset_button_test / qcc_wdt_test(`dt_reboot`)。
- RF 校準（ATE）由外部 Keysight 工具（Windows/VISA）執行，框架應為「觸發 + 解析
  log」而非自測。

### 現有骨架的落差
- `scripts/MFG/Pi7a/Pi7a-MFG.py` 目前是 EAP111-style（U-Boot 流程）骨架，**對 Pi7a
  完全不適用**，需依上表重寫。
- config/test_node/pi7a_testbed.yaml（ap.mfg 需改：uboot_prompt → `qcc74x />`、
  無燒錄欄、console baudrate/連接）、config/profiles/Pi7a.yaml。

### 待確認（硬體/規格）
- Pi7a 電源控制是否也用 FT232H relay（log 只見 DC Jack Power ON/OFF 字樣）？
- Pi7a console 是否走 ser2net telnet？baudrate（log 無明確 baudrate）？
- ATE 是否由框架觸發，還是既有 Windows 工具跣？框架只收集/解析 log？
- `setup_QCA.txt` 的 Connection_ComPort 如何對應治具 console port？
- 是否移植全部 20 測項，或先做核心子集（factory 寫/讀 + 版本檢查 + i2c/fuel gauge）。

---

## 增加型號的標準流程（方法論）
- **情況 A：同平台不同 SKU / 機型**（如另一款 MT7981）— 3 步，不改後端/積木：
  1. 複製 testbed YAML，改 ap.model + ap.mfg 差異值 + ap.tftp.fip_image/fw_image。
  2. 複製 scripts/MFG/<MODEL>/<MODEL>-MFG.py，改 tc_id/headline。
  3. （選用）複製 config/profiles/<MODEL>.yaml。
  - 多 SKU（同型號不同韌體/客戶）：在 ap.mfg.skus 加 SKU（各自 fw_image/sku/
    region），GUI SKU 下拉自動出現（見 kiro-memory 多 SKU 章節）。
- **情況 B：不同平台**（如 OAP101=IPQ5018）— 參數化不足，需新增平台專屬後端方法
  與積木，共用部分（console/ssh/wait/message）沿用。
- **待辦**：把此流程寫進 README 或 docs/add_model.md，附情況 A 可複製範本。

---

## 其他
- EAP111 certification 三步（prepare/write/check_certification）為後端 STUB；
  真正流程需 cert server + plink/pscp（Windows 端），本環境無法驗證。目前
  EAP111-MFG-TEST 已移除這三步；正式版 EAP111-MFG.py 仍含（stub）。
- 反解析欄位值已補齊（見 kiro-memory 續 5）。

---

## 監控面板後續（治具接線區塊已實作；以下待辦）

> 現況：監控面板（/dashboard）已新增唯讀「治具接線 / Testbed」區塊，跟隨型號下拉
> 讀 config/test_node/<model>_testbed.yaml 顯示 console/power/tftp/ssh/pc.ports
> （密碼類欄位遮罩）。後端 GET /api/testbed/{model}。見 kiro-memory 續 9。

- **(b) 圖形化拓撲圖**：把治具接線畫成 SVG 拓撲（DUT ↔ console/ser2net、FT232H
  relay、TFTP、PC ports），取代/補充目前的表格。較大工程，需為 MFG 治具自訂繪圖
  （不沿用 ATLAS 的 Switch/C50 topology.js）。
- **(c) 即時狀態偵測**：顯示治具/DUT 即時狀態（例如 console 是否連通、DUT 是否上電、
  ser2net log 是否有輸出、FT232H 是否在線）。需後端主動偵測 + 前端輪詢/WebSocket，
  比靜態接線複雜。可考慮沿用 /api/console/status（ser2net log 可用性）作為第一個
  即時指標。
