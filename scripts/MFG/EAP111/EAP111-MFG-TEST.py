"""EAP111-MFG-TEST — EAP111 manufacturing flow (validated PASS on real HW).

Step order follows the reference PASS log
(docs/logfiles/EAP111_T_PASS_Y_V4.1.1.1F.1.2_093645.txt). Certification steps
are removed (backend stubs); SN/MAC come from the Scan step.
"""
import time
from mfg.manufacturing_script import ManufacturingScript


class TestCase(ManufacturingScript):
    tc_id = "EAP111-MFG-TEST"
    station = "FDL"
    headline = "EAP111-MFG-TEST"
    purpose = "EAP111 manufacturing flow (barcode -> flash -> MFG data -> verify)"

    def run(self):
        try:
            self.dcjack_off()
            self.scan_barcode(source="usb_hid", timeout=30, expected_len=12)
            self.dcjack_power_cycle(off_delay=5)
            self.enter_uboot_menu()
            self.read_hw_version()
            self.write_manufacturing_data()
            self.enter_tip_kernel(username="root", password="ail:oY7R")
            self.check_tip_version()
            self.check_manufacturing_data()
            self.enter_tip_kernel_2()
            self.reset_default()
            self.message("PASS")
        finally:
            self.cleanup()
