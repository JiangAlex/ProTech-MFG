# ProTech-MFG — 單台 Raspberry Pi 4 治具部署

本文件說明如何把一台 Raspberry Pi 4 設定為 ProTech-MFG 製造測試治具（跑完整
後端 + GUI，硬體 FT232H 電源 / ser2net console / TFTP / USB 掃碼全接這台 Pi4）。
操作端（你的 PC）之後用瀏覽器連 `http://<pi4-ip>:8020` 操作，無需在 PC 安裝任何東西。

> 多台 Pi4 + OTA 中控是後續 Task 3~7；本文件只涵蓋「單台 Pi4 可用 + 開機自啟」。

---

## 前置需求

- Raspberry Pi 4（建議 2GB 以上），**Raspberry Pi OS 64-bit (arm64)**。
- Pi4 已連網（有線 eth0 建議，治具識別即取 eth0 MAC）。
- 治具硬體（可後接，安裝腳本不要求當下接上）：
  - FT232H（VID:PID `0403:6014`）→ DUT 電源繼電器
  - USB-serial（PL2303 `067b:2303` 或 CH340 `1a86:7523`）→ DUT console
  - DUT 測試網段（TFTP 燒錄用）

---

## 安裝步驟

### 1. 取得專案到 Pi4

```bash
cd ~
git clone <ProTech-MFG repo URL> ProTech-MFG   # 或用其他方式把專案放到 ~/ProTech-MFG
cd ~/ProTech-MFG
```

### 2. 執行一鍵安裝（以治具使用者身分，非 root）

```bash
bash deploy/install.sh
```

腳本會自動完成（idempotent，可重複執行）：

1. **OS 套件**：`python3-venv`、`ser2net`、`libusb-1.0-0`、`git`
2. **venv + Python 依賴**：建立 `.venv` 並 `pip install -r requirements.txt`
   （`pyyaml tftpy pexpect pyftdi fastapi uvicorn ...`，皆支援 arm64）
3. **udev 規則**：
   - 跑 `tools/setup_ft232h_gpio.sh`：解除 kernel `ftdi_sio` 對 FT232H 的佔用，
     讓 pyftdi 能驅動電源繼電器
   - 安裝 `99-mfg-serial.rules`：穩定裝置名 `/dev/mfg-console`、`/dev/mfg-power`
   - 把治具使用者加入 `plugdev` 群組（pyftdi 存取 libusb）
4. **VERSION 檔**：寫入 git short hash（供後續 OTA 版本比對）
5. **systemd 服務**：安裝並啟用 `protech-mfg.service`（GUI 跑在 `:8020`，開機自啟、
   失敗自動重啟）

### 3. 驗證

```bash
# 服務狀態
sudo systemctl status protech-mfg
# 即時日誌
journalctl -u protech-mfg -f
# 從操作 PC 的瀏覽器開啟（<pi4-ip> 用 `hostname -I` 查）
#   http://<pi4-ip>:8020
```

GUI header 右上的「主機」badge 會顯示這台 Pi4 的 **eth0 MAC**，即治具識別。

> **首次安裝提醒**：若 pyftdi 無法開啟 FT232H（權限不足），登出再登入一次
> （或重開機）讓 `plugdev` 群組生效。

---

## 服務管理

```bash
sudo systemctl restart protech-mfg    # 重啟（改程式/設定後）
sudo systemctl stop protech-mfg       # 停止
sudo systemctl disable protech-mfg    # 取消開機自啟
```

---

## 設定說明

- **GUI port**：預設 8020。安裝時可用 `MFG_PORT=9000 bash deploy/install.sh` 改。
- **治具識別**：預設讀 `eth0` MAC。若網卡介面名不同，可在 service 檔加
  `Environment=MFG_HOST_IFACE=<iface>`；或直接指定 `Environment=MFG_HOST=<值>`。
  （改 service 請重跑 `install.sh` 或手動編 `/etc/systemd/system/protech-mfg.service`
  後 `daemon-reload`）
- **DUT console / 電源**：ser2net 指向 `/dev/mfg-console`；FT232H 由 pyftdi 以
  `ftdi://ftdi:232h/1` 存取（對應 `/dev/mfg-power` 符號連結）。見
  `config/console/ser2net.yaml`、`config/test_node/*.yaml`。

---

## 疑難排解

| 症狀 | 檢查 |
|------|------|
| GUI 連不上 | `systemctl status protech-mfg`；`journalctl -u protech-mfg -e` |
| 主機 badge 顯示「未知」 | 該機無 `eth0`（確認網卡名，或設 `MFG_HOST_IFACE`） |
| 電源繼電器不動作 | 重跑 `sudo tools/setup_ft232h_gpio.sh`；確認已登出入讓 plugdev 生效 |
| console 連不到 DUT | `ls -l /dev/mfg-console`；`sudo systemctl restart ser2net` |
| pip 裝不起來 | 確認是 64-bit OS（`uname -m` = `aarch64`） |

---

## 新增第 N 台 Pi4

每台重複「安裝步驟」即可。治具識別自動取各台 eth0 MAC，**無需改任何腳本或設定**。
集中管理與 OTA 更新（PC 中控）屬後續 Task 3~7。
