"""
Pi7a-MFG: Pi7a manufacturing flow — QCC74x core subset (NO ATE RF calibration).

Pi7a = Qualcomm QCC744 (QCC74x). It is a THIRD platform, different from EAP111
(MT7981 U-Boot) and OAP101 (IPQ5018 U-Boot): there is NO U-Boot / no tftpboot
flash flow — the firmware is pre-flashed and MFG drives the QCC74x firmware CLI
(prompt "qcc74x />").

This flow implements the CORE SUBSET derived from the reference PASS log
(docs/logfiles/Pi7a-EC2617002807_PASS_N_1_132811.txt):
  factory write/read (SN/MAC) + version checks + i2c/fuel gauge/power mode +
  LED / reset button / WDT.

NOT included (separate ATE stage): `mfg` mode entry and Keysight ATE RF
calibration (TX/RX verify). See docs/kiro-todo.md.

Run with:
    pytest scripts/MFG/Pi7a/Pi7a-MFG.py --mfg-testbed config/test_node/pi7a_testbed.yaml -s
"""
from mfg.manufacturing_script import ManufacturingScript


class TestCase(ManufacturingScript):
    tc_id = "Pi7a-MFG"
    station = "PT"
    headline = "Pi7a-MFG"
    purpose = "Pi7a (QCC74x) manufacturing core subset — no ATE RF calibration"

    def run(self):
        try:
            # 0. Scan SN + MAC (two scans, any order; auto-detected).
            self.scan_barcode(source="usb_hid", timeout=30, expected_len=12)
            # 1. Power on; wait for the "qcc74x />" firmware CLI prompt.
            self.qcc_connect()
            # 2. Charger power mode (power_mode 0/1).
            self.qcc_power_mode_test()
            # 3. Charger battery mode (battery_mode 0).
            self.qcc_battery_mode_test()
            # 4. SY6410 fuel gauge voltage (fuel_gauge 0/1).
            self.qcc_fuel_gauge_test()
            # 5. diag_version + mm_version.
            self.qcc_check_versions()
            # 6. I2C scan (i2c_scan / i2c_scan1).
            self.qcc_i2c_scan()
            # 7. Write factory SN/MAC/Model/HWver (factory w ...).
            self.qcc_factory_write()
            # 8. Read back and verify factory (6 fields).
            self.qcc_factory_check()
            # 9. LED test (led all on / led off).
            self.qcc_led_test()
            # 10. Reset button test (hold >=5s; verify factory preserved).
            self.qcc_reset_button_test()
            # 11. Watchdog test (dt_reboot).
            self.qcc_wdt_test()

            self.message("PASS")
        finally:
            self.cleanup()
