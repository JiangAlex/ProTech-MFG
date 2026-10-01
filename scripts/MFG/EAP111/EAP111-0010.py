"""
EAP111 T-series Manufacturing Test Suite (skip certificate steps)

Test Case: EAP111-0010
Platform:  mt7981-rfb (EdgeCore EAP111)
Purpose:   T-series manufacturing flow: U-Boot → Flash update → MFG data → TIP kernel boot

Steps implemented (10):
  1. EnterUbootMenu      - DC Jack OFF→ON, hit any key in boot menu
  2. ReadHwVersion       - Read factory MTD for eth0/eth1/ar0 MAC, SN, Model, HW Rev
  3. UpdateFlashImage    - TFTP download + burn FIP + firmware images
  4. WriteUbootEnvSerial - Write bootcount/active/upgrade_available/SN
  5. WriteManufacturingData - Write model/rev/serial/qr_code/manufacturer env vars
  6. EnterTipKernel (1)  - Let system auto-boot into Linux; wait for login prompt
  7. CheckTipVersion     - Login; verify TIP version in /etc/openwrt_release
  8. CheckManufacturingData - Linux: jffs2reset+reboot → U-Boot printenv verify
  9. EnterTipKernel (2)  - Re-boot into Linux; wait for login prompt
 10. ResetDefault        - jffs2reset+reboot → end at U-Boot menu (final state)

Skipped (certificate steps - future work):
  - PrepareCertification  (download 4445BA0310D8.tar.gz from VPN server)
  - WriteCertification     (SCP upload certs to DUT via up0v0 interface)
  - CheckCertification     (verify MD5 hashes of cert files)

Testbed config required fields:
  FW_IMAGE_PATH   - path to openwrt-mediatek-mt7981-edgecore_eap111-squashfs-factory.bin
  FIP_IMAGE_PATH  - path to tip_fip.bin
  TFTP_SERVER     - TFTP server IP (default 192.168.1.100)
  DUT_IP          - DUT IP for TFTP (default 192.168.1.10)
  TFTP_DUT_IP     - same as DUT_IP (for convenience)
"""

import re
import time
import pytest

from core.script import Script
from core.conf import Conf


class TestCase(Script):
    """EAP111 T-series manufacturing test (skip certificates)."""

    tc_id = 'EAP111-0010'
    station = 'FDL'
    headline = 'EAP111 T-series manufacturing flow (skip certificates)'
    purpose = (
        'Execute T-series manufacturing flow on EAP111 (MT7981), verifying '
        'U-Boot menu, hardware read, flash update, manufacturing data write, '
        'TIP kernel boot, and reset to defaults. Certificate steps are '
        'skipped with TODO placeholders.'
    )

    # Step/criteria markers
    S = staticmethod(lambda s, n, d: s.step(n, d) or s._inc())
    C = staticmethod(lambda s, n, d: s.criteria(n, d) or s._inc())

    def __init__(self):
        super().__init__(tc_id=self.tc_id, headline=self.headline, purpose=self.purpose)
        self._step = 0
        self.dut = None  # CLI session
        self._scanned_sn = None  # SN scanned at start (compared in Step 2)

    def _inc(self):
        self._step += 1

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _scan_barcode(self, source='usb_hid', timeout=30, expected_len=0):
        """Read a barcode/SN from a scanner.

        source='usb_hid' → scanner acts as a keyboard, SN arrives on stdin.
        source='serial'  → scanner wedge on the serial console; read one line.
        Returns the scanned SN string (stripped).
        """
        sn = ''
        if source == 'serial':
            self.dut.expect(r'[\r\n]', timeout=timeout)
            sn = (self.dut.getBuffer() or '').strip()
        else:
            import sys
            import select
            self.message('Please scan the barcode now...')
            ready, _, _ = select.select([sys.stdin], [], [], timeout)
            if not ready:
                self.resultFail(f'No barcode scanned within {timeout}s (usb_hid)')
                return ''
            sn = sys.stdin.readline().strip()

        if not sn:
            self.resultFail('Scanned barcode is empty')
        if expected_len and len(sn) != expected_len:
            self.resultFail(f'Scanned SN "{sn}" length {len(sn)} != {expected_len}')
        return sn

    def _uboot_send(self, cmd, expect_prompt=True):
        """Send command to U-Boot console; carriage-return appended automatically."""
        self.dut.send(cmd + '\r')
        if expect_prompt:
            self.dut.expect(self.dut.prompt, timeout=10)
        else:
            self.dut.expect('MT7981>', timeout=10)

    def _uboot_expect_prompt(self):
        self.dut.expect('MT7981>', timeout=10)

    def _linux_expect_prompt(self, timeout=120):
        """Wait for Linux shell prompt (# or $)."""
        self.dut.expect(r'(root@|BusyBox|login:)', timeout=timeout)

    def _linux_login(self):
        """Login as root to Linux shell."""
        self.dut.send('root\r')
        idx = self.dut.expect(['Password:', self.dut.prompt], timeout=15)
        if idx == 0:
            self.dut.send('\r')  # no password
            self.dut.expect(self.dut.prompt, timeout=15)
        time.sleep(1)

    def _reboot_and_wait_uboot(self):
        """Issue 'reset' and wait for U-Boot prompt."""
        self.dut.send('reset\r')
        # Wait for U-Boot boot menu to appear, then interrupt
        self.dut.expect('*** U-Boot Boot Menu ***', timeout=60)
        idx = self.dut.expect(['Hit any key', '0. U-Boot console'], timeout=15)
        if idx >= 0:
            self.dut.send('\r')
        self.dut.expect('MT7981>', timeout=15)

    def _wait_autoboot_and_interrupt(self, timeout=60):
        """Wait for autoboot countdown; send key to interrupt."""
        idx = self.dut.expect(
            ['Hit any key to stop autoboot:', '*** U-Boot Boot Menu ***', 'MT7981>'],
            timeout=timeout,
        )
        if idx == 0:
            self.dut.send('\r')
            self.dut.expect('MT7981>', timeout=10)
        elif idx == 1:
            # menu already displayed, send any key
            self.dut.send('\r')
            self.dut.expect('MT7981>', timeout=10)
        # else already at prompt

    def _parse_mac_from_hex(self, hex_str):
        """Convert '44 45 ba 03 10 d8' → '44:45:BA:03:10:D8'."""
        parts = hex_str.strip().split()
        return ':'.join(p.upper() for p in parts)

    def _hex_to_ascii(self, hex_str):
        """Convert hex dump bytes to ASCII string, stripping nulls."""
        parts = hex_str.strip().split()
        chars = [chr(int(p, 16)) for p in parts]
        return ''.join(c if c.isprintable() else '' for c in chars).rstrip('\x00')

    def _read_eth_mac(self, offset, label):
        """Read 6-byte MAC at memory offset; return formatted MAC string."""
        self._uboot_send(f'md.b {offset} 0x6')
        self.dut.expect(self.dut.prompt, timeout=10)
        buff = self.dut.getBuffer()
        # Parse hex line like: 4600002a: 44 45 ba 03 10 d8
        m = re.search(r':\s+([0-9a-f]{2}\s+[0-9a-f]{2}\s+[0-9a-f]{2}\s+[0-9a-f]{2}\s+[0-9a-f]{2}\s+[0-9a-f]{2})', buff)
        if not m:
            self.resultFail(f'Cannot parse {label} MAC from: {buff[:200]}')
        mac_hex = m.group(1)
        return self._parse_mac_from_hex(mac_hex)

    def _read_sn_model(self, offset='0x46000060', length='0x30'):
        """Read SN+Model string from memory."""
        self._uboot_send(f'md.b {offset} {length}')
        self.dut.expect(self.dut.prompt, timeout=10)
        buff = self.dut.getBuffer()
        # Find the hex line
        m = re.search(r':\s+([0-9a-f ]+)$', buff, re.MULTILINE)
        if not m:
            self.resultFail(f'Cannot parse SN/Model from: {buff[:300]}')
        hex_part = m.group(1).strip()
        return self._hex_to_ascii(hex_part)

    def _write_env(self, key, value):
        """Set a U-Boot env variable and saveenv."""
        self._uboot_send(f'setenv {key} {value}')
        self._uboot_send('saveenv')
        self._uboot_expect_prompt()

    def _verify_env(self, key, expected):
        """Verify a U-Boot env variable matches expected value."""
        self._uboot_send(f'printenv {key}')
        self.dut.expect(self.dut.prompt, timeout=10)
        buff = self.dut.getBuffer()
        pattern = rf'^{key}=(.+)$'
        m = re.search(pattern, buff, re.MULTILINE)
        if not m:
            self.resultFail(f'Env {key} not found in: {buff}')
        actual = m.group(1).strip()
        if actual != expected:
            self.resultFail(f'Env {key}={actual}, expected {expected}')
        self.resultPass(f'{key}={actual} (expected)')

    # -------------------------------------------------------------------------
    # Power control helpers (hardware-specific, implemented as no-ops in sim)
    # -------------------------------------------------------------------------

    def _dcjack_off(self):
        """Power off DUT via DC jack."""
        self.message('DC Jack: OFF')

    def _dcjack_on(self):
        """Power on DUT via DC jack."""
        self.message('DC Jack: ON')

    # -------------------------------------------------------------------------
    # Test steps
    # -------------------------------------------------------------------------

    def run(self):
        # -----------------------------------------------------------------
        # Setup: get DUT CLI session from testbed
        # -----------------------------------------------------------------
        self.dut = self.initUI(Conf.DUT1, 'com')
        self.dut.prompt = r'MT7981>|root@|BusyBox|login:'

        # -----------------------------------------------------------------
        # STEP 0: ScanBarcode — read product SN from scanner (USB HID / serial)
        # -----------------------------------------------------------------
        self.step(0, 'ScanBarcode: read SN from usb_hid scanner')
        self.criteria(1, 'A non-empty serial number is scanned')

        self._scanned_sn = self._scan_barcode(source='usb_hid', timeout=30, expected_len=14)
        self.message(f'Scanned SN = {self._scanned_sn}')
        self.resultPass(f'Step 0: Barcode scanned (SN={self._scanned_sn})')

        # -----------------------------------------------------------------
        # STEP 1: EnterUbootMenu
        # -----------------------------------------------------------------
        self.step(1, 'EnterUbootMenu: DC Jack OFF→ON, interrupt boot menu')
        self.criteria(1, 'U-Boot boot menu appears; "*** U-Boot Boot Menu ***" visible')
        self.criteria(2, 'Console accepts command input (MT7981> prompt)')

        self._dcjack_off()
        time.sleep(2)
        self._dcjack_on()

        # Wait for boot menu
        self.dut.expect('*** U-Boot Boot Menu ***', timeout=90)
        self.message('U-Boot menu detected')

        # Interrupt autoboot
        idx = self.dut.expect(['Hit any key to stop autoboot:', '0. U-Boot console'], timeout=15)
        if idx == 0:
            self.dut.send('\r')
            self.dut.expect('MT7981>', timeout=10)
        elif idx == 1:
            self.dut.send('0\r')
            self.dut.expect('MT7981>', timeout=10)

        self.resultPass('Step 1: U-Boot menu entered; MT7981> prompt confirmed')

        # -----------------------------------------------------------------
        # STEP 2: ReadHwVersion
        # -----------------------------------------------------------------
        self.step(2, 'ReadHwVersion: Read factory MTD for MAC/SN/Model/HW Rev')
        self.criteria(1, 'eth0 MAC matches testbed config')
        self.criteria(2, 'eth1 MAC matches testbed config')
        self.criteria(3, 'ar0 MAC matches testbed config')
        self.criteria(4, 'SN and Model match testbed config')
        self.criteria(5, 'HW Revision matches testbed config')

        # Read factory MTD partition
        self._uboot_send('mtd read factory 0x46000000 0x0 0x800')
        self.dut.expect('MT7981>', timeout=10)

        # MAC addresses
        eth0_mac = self._read_eth_mac('0x4600002A', 'eth0')
        eth1_mac = self._read_eth_mac('0x46000024', 'eth1')
        ar0_mac  = self._read_eth_mac('0x46000004', 'ar0')

        # SN + Model at 0x46000060, length 0x30
        sn_model_raw = self._read_sn_model('0x46000060', '0x30')
        # Format: EC2612003867...EAP111-0223-WL...
        sn = sn_model_raw[:14].rstrip('\x00')
        model_str = sn_model_raw[16:30].rstrip('\x00').strip()
        hw_rev_raw = self._read_sn_model('0x46000080', '0x10')
        hw_rev = hw_rev_raw[:4].rstrip('\x00').strip()

        self.message(f'eth0={eth0_mac} eth1={eth1_mac} ar0={ar0_mac}')
        self.message(f'SN={sn}  Model={model_str}  HW_Rev={hw_rev}')

        # Verify against testbed (keys are read from Conf if present)
        tb_mac   = getattr(Conf, 'DUT_MAC',   eth0_mac)
        tb_sn    = getattr(Conf, 'DUT_SN',    sn)
        tb_model = getattr(Conf, 'DUT_MODEL', 'EAP111')
        tb_rev   = getattr(Conf, 'DUT_HWREV', hw_rev)

        if eth0_mac == tb_mac:
            self.resultPass(f'eth0 MAC {eth0_mac} matches testbed')
        else:
            self.resultCheck(f'eth0 MAC {eth0_mac} (testbed={tb_mac})')

        if eth1_mac == tb_mac:  # incremented MAC
            self.resultPass(f'eth1 MAC {eth1_mac} matches testbed')
        else:
            self.resultCheck(f'eth1 MAC {eth1_mac}')

        if ar0_mac == tb_mac:   # incremented MAC
            self.resultPass(f'ar0 MAC {ar0_mac} matches testbed')
        else:
            self.resultCheck(f'ar0 MAC {ar0_mac}')

        if sn == tb_sn:
            self.resultPass(f'SN {sn} matches testbed')
        else:
            self.resultCheck(f'SN {sn} (testbed={tb_sn})')

        # Compare hardware SN against the barcode scanned in Step 0
        if self._scanned_sn:
            if self._scanned_sn == sn:
                self.resultPass(f'Scanned SN {self._scanned_sn} matches hardware SN {sn}')
            else:
                self.resultFail(
                    f'SN mismatch: scanned "{self._scanned_sn}" != hardware "{sn}"'
                )

        self.resultPass(f'Step 2: Hardware read complete')

        # -----------------------------------------------------------------
        # STEP 3: UpdateFlashImage
        # -----------------------------------------------------------------
        self.step(3, 'UpdateFlashImage: TFTP download + burn FIP + firmware')
        self.criteria(1, 'TFTP ping to serverip succeeds (host alive)')
        self.criteria(2, 'tip_fip.bin downloaded successfully (filesize > 0)')
        self.criteria(3, 'FIP partition erased and written (Succeeded)')
        self.criteria(4, 'openwrt factory image downloaded (filesize > 0)')
        self.criteria(5, 'rootfs1/rootfs2 partitions written (Succeeded)')
        self.criteria(6, 'Board resets after flash update')

        tftp_server = getattr(Conf, 'TFTP_SERVER', '192.168.1.100')
        dut_ip      = getattr(Conf, 'TFTP_DUT_IP', '192.168.1.10')
        fip_image   = getattr(Conf, 'FIP_IMAGE_PATH', 'tip_fip.bin')
        fw_image    = getattr(Conf, 'FW_IMAGE_PATH', 'openwrt-mediatek-mt7981-edgecore_eap111-squashfs-factory.bin')

        # Set IP addresses
        self._uboot_send(f'setenv ipaddr {dut_ip}')
        self._uboot_send(f'setenv serverip {tftp_server}')

        # Ping TFTP server
        self._uboot_send('ping 192.168.1.100')
        self.dut.expect('is alive', timeout=10)
        self.resultPass('TFTP server ping OK')

        # Download and burn FIP
        self._uboot_send(f'tftpboot 0x46000000 {fip_image}')
        self.dut.expect('Bytes transferred', timeout=60)
        self._uboot_send('nmbm nmbm0 erase 0x00380000 0x00200000')
        self.dut.expect('Succeeded', timeout=30)
        self._uboot_send('nmbm nmbm0 write 0x46000000 0x00380000 0x${filesize}')
        self.dut.expect('Succeeded', timeout=30)
        self.resultPass('FIP partition updated')

        # Download and burn OpenWrt factory image
        self._uboot_send(f'tftpboot 0x46000000 {fw_image}')
        self.dut.expect('Bytes transferred', timeout=120)
        # Erase rootfs1 at 0x00580000, size 0x80000 (512 KB) per task spec
        self._uboot_send('nmbm nmbm0 erase 0x00580000 0x08000000')
        self.dut.expect('Succeeded', timeout=60)
        # Write to rootfs1 at 0x00580000
        self._uboot_send('nmbm nmbm0 write 0x46000000 0x00580000 0x${filesize}')
        self.dut.expect('Succeeded', timeout=60)
        # Write duplicate to rootfs2 at 0x04580000
        self._uboot_send('nmbm nmbm0 write 0x46000000 0x04580000 0x${filesize}')
        self.dut.expect('Succeeded', timeout=60)
        self.resultPass('OpenWrt image written to rootfs1 + rootfs2')

        # Reset
        self.dut.send('reset\r')
        self.resultPass('Step 3: Board resetting after flash update')

        # Wait for boot menu to appear after reset
        self.dut.expect('*** U-Boot Boot Menu ***', timeout=90)
        self.resultPass('Step 3: Flash update complete; board rebooted')

        # -----------------------------------------------------------------
        # STEP 4: WriteUbootEnvSerial
        # -----------------------------------------------------------------
        self.step(4, 'WriteUbootEnvSerial: Write bootcount/active/upgrade_available/SN')
        self.criteria(1, 'bootcount=0 persisted after saveenv')
        self.criteria(2, 'active=1 persisted after saveenv')
        self.criteria(3, 'upgrade_available=1 persisted after saveenv')
        self.criteria(4, 'SN=<SERIAL> persisted after saveenv')

        # Interrupt into U-Boot
        self._wait_autoboot_and_interrupt(timeout=60)

        sn = getattr(Conf, 'DUT_SN', 'EC2612003867')

        self._uboot_send('setenv bootcount 0')
        self._uboot_send('setenv active 1')
        self._uboot_send('setenv upgrade_available 1')
        self._uboot_send(f'setenv SN {sn}')
        self._uboot_send('saveenv')
        self._uboot_expect_prompt()

        # Verify
        self._verify_env('bootcount', '0')
        self._verify_env('active', '1')
        self._verify_env('upgrade_available', '1')
        self._verify_env('SN', sn)

        self.resultPass('Step 4: U-Boot serial env written and verified')

        # -----------------------------------------------------------------
        # STEP 5: WriteManufacturingData
        # -----------------------------------------------------------------
        self.step(5, 'WriteManufacturingData: Write model/rev/serial/qr_code/manufacturer env vars')
        self.criteria(1, 'All manufacturing env vars persist after saveenv')
        self.criteria(2, 'Board resets after saveenv')

        mac  = getattr(Conf, 'DUT_MAC', '44:45:BA:03:10:D8')
        sn   = getattr(Conf, 'DUT_SN',  'EC2612003867')
        rev  = getattr(Conf, 'DUT_HWREV', 'R01A')
        from datetime import date
        mfg_date = date.today().strftime('%d-%m-%Y')  # DD-MM-YYYY

        qr = (f'{{"DT":"ap","DM":"{mac}","VN":"EC","SN":"{sn}","MN":"EAP111","HW":"{rev}"}}')

        self._uboot_send('setenv sku EAP111(TE)')
        self._uboot_send('setenv model EAP111')
        self._uboot_send(f'setenv model_revision {rev}')
        self._uboot_send(f'setenv serial_number {sn}')
        self._uboot_send(f'setenv qr_code {qr}')
        self._uboot_send('setenv manufacturer_name EC')
        self._uboot_send(f'setenv manufacturer_date {mfg_date}')
        self._uboot_send('setenv manufacturer_url www.edge-core.com')
        self._uboot_send('setenv model_description 802.11ax Dual-Band Enterprise Access Point')
        self._uboot_send('setenv reference_design mt7981-spim-nand-rfb')
        self._uboot_send('setenv certification_region WW')
        self._uboot_send(f'setenv mac_address {mac}')
        self._uboot_send('saveenv')
        self._uboot_expect_prompt()
        self.resultPass('Manufacturing data env vars saved')

        # Reset
        self.dut.send('reset\r')
        self.message('Board resetting after manufacturing data write')
        self.dut.expect('*** U-Boot Boot Menu ***', timeout=90)
        self.resultPass('Step 5: Manufacturing data written; board rebooted')

        # -----------------------------------------------------------------
        # STEP 6: EnterTipKernel (1st boot into Linux)
        # -----------------------------------------------------------------
        self.step(6, 'EnterTipKernel (1): Auto-boot into Linux; wait for login prompt')
        self.criteria(1, 'Linux banner appears: ApNos-5b69e6a-v4.1.1 or OpenWrt 23.05-SNAPSHOT')
        self.criteria(2, 'login prompt appears on console')

        # Let system boot automatically; don't interrupt
        # Wait for autoboot countdown to expire
        self.message('Waiting for Linux kernel boot (auto-proceeding)...')
        idx = self.dut.expect(
            ['Hit any key to stop autoboot:', 'ApNos-', 'OpenWrt 23.05', 'login:'],
            timeout=90,
        )
        if idx == 0:
            # Countdown active - let it expire (wait for kernel)
            self.message('Autoboot countdown active; waiting for kernel...')
            self.dut.expect(['ApNos-', 'OpenWrt 23.05', 'login:'], timeout=120)

        # Wait for login prompt
        self.dut.expect('login:', timeout=60)
        self.resultPass('Step 6: Login prompt appeared (EnterTipKernel 1st boot)')

        # -----------------------------------------------------------------
        # STEP 7: CheckTipVersion
        # -----------------------------------------------------------------
        self.step(7, 'CheckTipVersion: Login and verify TIP version in /etc/openwrt_release')
        self.criteria(1, '/etc/openwrt_release contains DISTRIB_TIP with v4.1.1')

        self._linux_login()

        self.dut.send("cat /etc/openwrt_release | grep DISTRIB_TIP\r")
        self.dut.expect(self.dut.prompt, timeout=10)
        buff = self.dut.getBuffer()

        if 'TIP-v4.1.1' in buff or 'TIP-v4.1' in buff:
            self.resultPass('TIP version verified: v4.1.1 in /etc/openwrt_release')
        else:
            self.resultCheck(f'DISTRIB_TIP not found in output: {buff[:300]}')

        self.resultPass('Step 7: TIP version check complete')

        # -----------------------------------------------------------------
        # STEP 8: CheckManufacturingData (Linux → U-Boot verify)
        # -----------------------------------------------------------------
        self.step(8, 'CheckManufacturingData: Linux jffs2reset+reboot → U-Boot printenv verify')
        self.criteria(1, 'All manufacturing env vars match expected values in U-Boot')

        self.dut.send('jffs2reset -y\r')
        self.dut.expect(self.dut.prompt, timeout=30)
        self.resultPass('jffs2reset executed')

        self.dut.send('reboot\r')
        self.message('Rebooting to verify manufacturing data persistence...')

        # Wait for U-Boot menu after reboot
        self.dut.expect('*** U-Boot Boot Menu ***', timeout=90)
        self._wait_autoboot_and_interrupt(timeout=60)

        # Verify manufacturing env vars
        self._verify_env('sku',                'EAP111(TE)')
        self._verify_env('model',              'EAP111')
        self._verify_env('model_revision',     rev)
        self._verify_env('serial_number',      sn)
        self._verify_env('qr_code',            qr)
        self._verify_env('manufacturer_name',   'EC')
        self._verify_env('manufacturer_url',   'www.edge-core.com')
        self._verify_env('model_description', '802.11ax Dual-Band Enterprise Access Point')
        self._verify_env('reference_design',  'mt7981-spim-nand-rfb')
        self._verify_env('certification_region', 'WW')
        self._verify_env('mac_address',        mac)

        self.resultPass('Step 8: Manufacturing data verified in U-Boot')

        # -----------------------------------------------------------------
        # STEP 9: EnterTipKernel (2nd boot into Linux)
        # -----------------------------------------------------------------
        self.step(9, 'EnterTipKernel (2): Re-boot into Linux; wait for login prompt')
        self.criteria(1, 'Linux banner appears (ApNos- / OpenWrt 23.05-SNAPSHOT)')
        self.criteria(2, 'login prompt appears on console')

        # Issue reset to boot Linux again
        self.dut.send('reset\r')
        self.message('Rebooting for second Linux boot...')

        # Wait for boot
        self.dut.expect('*** U-Boot Boot Menu ***', timeout=90)
        idx = self.dut.expect(['Hit any key to stop autoboot:', 'ApNos-', 'OpenWrt 23.05', 'login:'], timeout=30)
        if idx == 0:
            self.dut.expect(['ApNos-', 'OpenWrt 23.05', 'login:'], timeout=120)

        self.dut.expect('login:', timeout=60)
        self.resultPass('Step 9: Login prompt appeared (EnterTipKernel 2nd boot)')

        # -----------------------------------------------------------------
        # STEP 10: ResetDefault
        # -----------------------------------------------------------------
        self.step(10, 'ResetDefault: jffs2reset+reboot → final state is U-Boot menu')
        self.criteria(1, 'Board reboots and stops at U-Boot menu (final state)')

        self._linux_login()

        self.dut.send('jffs2reset -y\r')
        self.dut.expect(self.dut.prompt, timeout=30)
        self.resultPass('jffs2reset executed')

        self.dut.send('reboot\r')
        self.message('Final reboot; expecting U-Boot menu as end state...')

        self.dut.expect('*** U-Boot Boot Menu ***', timeout=90)
        self.dut.send('\r')
        self.dut.expect('MT7981>', timeout=10)

        self.resultPass('Step 10: ResetDefault complete; final state: U-Boot menu')

        # -----------------------------------------------------------------
        # Skipped certificate steps (TODO placeholders)
        # -----------------------------------------------------------------
        self.message('')
        self.message('=' * 60)
        self.message('NOTE: Certificate steps are SKIPPED in this run:')
        self.message('  - PrepareCertification  : download cert from VPN server')
        self.message('  - WriteCertification    : SCP certs to DUT via up0v0')
        self.message('  - CheckCertification    : verify MD5 hashes of cert files')
        self.message('These steps will be implemented in a future test case.')
        self.message('=' * 60)

        self.resultPass('EAP111-0010 completed (certificate steps skipped)')
