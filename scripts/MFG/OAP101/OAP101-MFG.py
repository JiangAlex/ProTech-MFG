"""
OAP101-MFG: OAP101 manufacturing (FDL) flow.

Shares the same ManufacturingScript backend + blocks as EAP111; model-specific
values (U-Boot prompt, factory MTD offsets, flash layout, setenv model/sku,
firmware image names) come from the testbed's ap.mfg section
(config/test_node/oap101_testbed.yaml). Run with:

    pytest scripts/MFG/OAP101/OAP101-MFG.py \
        --testbed config/test_node/oap101_testbed.yaml
"""
import time
from mfg.manufacturing_script import ManufacturingScript


class TestCase(ManufacturingScript):
    tc_id = "OAP101-MFG"
    station = "FDL"
    headline = "OAP101-MFG"
    purpose = "OAP101 full manufacturing flow (barcode -> flash -> MFG data -> verify)"

    def run(self):
        try:
            # 0. Scan SN + MAC (two scans, any order; auto-detected).
            self.scan_barcode(source="usb_hid", timeout=30, expected_len=12)
            # 1. Enter U-Boot menu (DC OFF->ON, interrupt autoboot)
            self.enter_uboot_menu()
            # 2. Read HW version (MAC/SN/Model/HW Rev) from factory MTD
            self.read_hw_version()
            time.sleep(5)
            # 3. TFTP download + flash FIP and firmware images
            self.update_flash_image()
            # 4. Write U-Boot env: bootcount/active/upgrade_available/SN
            self.write_uboot_env_serial()
            # 5. Write manufacturing data env vars (MAC & SN from scan)
            self.write_manufacturing_data()
            # 6. Enter TIP kernel (first Linux boot + login)
            self.enter_tip_kernel()
            # 7. Check TIP version
            self.check_tip_version()
            # 8. Check manufacturing data (jffs2reset+reboot -> U-Boot verify)
            self.check_manufacturing_data()
            # 9. Reboot & wait login (second Linux boot)
            self.enter_tip_kernel_2()
            # 10. Reset to default (final state: U-Boot menu)
            self.reset_default()

            self.message("PASS")
        finally:
            self.cleanup()
