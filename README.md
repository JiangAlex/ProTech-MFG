# ProTech-MFG

製造測試治具系統（Manufacturing Test Fixture）。把一台 Raspberry Pi 4 設定成製造測試治具，
跑完整後端 + Web GUI，透過 FT232H 控制 DUT 電源、ser2net 接 DUT console、TFTP 燒錄。
操作端 PC 只需用瀏覽器連 `http://<pi4-ip>:8020`，無需在 PC 安裝任何東西。

## 快速開始（單台 Raspberry Pi 4）

需 Raspberry Pi OS 64-bit (arm64)、建議 2GB 以上記憶體、建議有線 eth0。

```bash
# 1. 取得專案到 Pi4
cd ~
git clone https://github.com/JiangAlex/ProTech-MFG.git
cd ~/ProTech-MFG

# 2. 一鍵安裝（以治具使用者身分，勿用 root）
bash deploy/install.sh

# 3. 驗證
sudo systemctl status protech-mfg        # active (running)
# 瀏覽器開 http://<pi4-ip>:8020（pi4-ip 用 hostname -I 查）
```

完整安裝說明、設定選項與疑難排解見 [`deploy/README.md`](deploy/README.md)。

> 目前涵蓋「單台 Pi4 可用 + 開機自啟」。多台 Pi4 集中管理與 OTA 更新屬後續 Task，
> 見 [`docs/ProTech-MFG-Pi4-OTA-ToDo.md`](docs/ProTech-MFG-Pi4-OTA-ToDo.md)。

## 專案結構

| 路徑 | 說明 |
|------|------|
| `src/mfg/` | 製造測試核心（manufacturing script、console、power controller） |
| `src/web/` | FastAPI 後端 + Web GUI（runner、db、host 識別） |
| `config/` | 測試站 / 裝置 profile / console (ser2net) 設定 |
| `deploy/` | Pi4 部署（install.sh、systemd service、部署文件） |
| `tools/` | FT232H GPIO 設定等工具 |

## Communication

- **技術解釋**使用「繁體中文」
- **變數名稱**、**函數名稱**與**代碼註釋**必須保持英文
