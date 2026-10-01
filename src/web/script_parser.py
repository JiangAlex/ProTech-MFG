"""Parse existing test scripts into Blockly workspace JSON."""
import re
from pathlib import Path


# Mapping of method patterns to Blockly block types + field extraction
_PATTERNS = [
    # --- MFG (atlas_* / pdu) — self.xxx() bare statements. Order matters:
    #     enter_tip_kernel_2 BEFORE enter_tip_kernel; dcjack_power_cycle BEFORE
    #     dcjack_on/off substrings. ---
    (r'self\.dcjack_power_cycle\(', 'pdu_power_cycle', {'ACTION': 'CYCLE'}),
    (r'self\.dcjack_on\(', 'pdu_power_cycle', {'ACTION': 'ON'}),
    (r'self\.dcjack_off\(', 'pdu_power_cycle', {'ACTION': 'OFF'}),
    (r'self\.scan_barcode\(', 'atlas_scan_barcode', {}),
    (r'self\.enter_uboot_menu\(', 'atlas_enter_uboot_menu', {}),
    (r'self\.read_hw_version\(', 'atlas_read_hw_version', {}),
    (r'self\.update_flash_image\(', 'atlas_update_flash_image', {}),
    (r'self\.write_uboot_env_serial\(', 'atlas_write_uboot_env_serial', {}),
    (r'self\.write_manufacturing_data\(', 'atlas_write_manufacturing_data', {}),
    (r'self\.enter_tip_kernel_2\(', 'atlas_reboot_and_wait_login', {}),
    (r'self\.enter_tip_kernel\(', 'atlas_enter_tip_kernel', {}),
    (r'self\.check_tip_version\(', 'atlas_check_tip_version', {}),
    (r'self\.check_manufacturing_data\(', 'atlas_check_manufacturing_data', {}),
    (r'self\.reset_default\(', 'atlas_reset_default', {}),
    (r'self\.prepare_certification\(', 'atlas_prepare_certification', {}),
    (r'self\.write_certification\(', 'atlas_write_certification', {}),
    (r'self\.check_certification\(', 'atlas_check_certification', {}),
    # --- Pi7a (QCC74x) core subset — self.qcc_*() bare statements. Names are
    #     distinct up to '(' so order is not prefix-sensitive. ---
    (r'self\.qcc_connect\(', 'qcc_connect', {}),
    (r'self\.qcc_power_mode_test\(', 'qcc_power_mode_test', {}),
    (r'self\.qcc_battery_mode_test\(', 'qcc_battery_mode_test', {}),
    (r'self\.qcc_fuel_gauge_test\(', 'qcc_fuel_gauge_test', {}),
    (r'self\.qcc_check_versions\(', 'qcc_check_versions', {}),
    (r'self\.qcc_i2c_scan\(', 'qcc_i2c_scan', {}),
    (r'self\.qcc_factory_write\(', 'qcc_factory_write', {}),
    (r'self\.qcc_factory_check\(', 'qcc_factory_check', {}),
    (r'self\.qcc_led_test\(', 'qcc_led_test', {}),
    (r'self\.qcc_reset_button_test\(', 'qcc_reset_button_test', {}),
    (r'self\.qcc_wdt_test\(', 'qcc_wdt_test', {}),
    # Console / Manufacturing
    (r'\.console\.connect\(\)', 'console_connect', {}),
    (r'\.console\.send\(\s*[\'"]reset[\'"]\)', 'console_reset', {}),
    (r'\.console\.send_and_expect\(\s*f?[\'"]tftpboot\s+(0x\w+)\s+(.+?)[\'"],', 'console_tftp', {}),
    (r'\.console\.send_and_expect\(\s*f?[\'"]nmbm nmbm0 erase\s+(0x\w+)\s+(0x\w+)', 'console_nand_erase', {}),
    (r'\.console\.send_and_expect\(\s*f?[\'"]nmbm nmbm0 write\s+(0x\S+)\s+(0x\S+)\s+(\S+)', 'console_nand_write', {}),
    (r'\.console\.send_and_expect\(\s*f?[\'"](.+?)[\'"]\s*[,)]', 'console_send', {}),
    (r'\.ssh_cmd\(\s*f?[\'"](.+?)[\'"]', 'ssh_cmd', {}),
    (r'\.wait_ssh_ready\(', 'wait_ssh_ready', {}),
    # iperf3
    (r'subprocess\.Popen\(\s*\[.*?iperf3.*?-s', 'iperf_server', {}),
    (r'subprocess\.run\(\s*\[.*?iperf3.*?-c', 'iperf_client', {}),
    # Switch
    (r'\.setPortLinkStatus\(\[?\d+\]?,\s*[\'"]down[\'"]\)', 'sw_port_disable', {}),
    (r'\.setPortLinkStatus\(\[?\d+\]?,\s*[\'"]up[\'"]\)', 'sw_port_enable', {}),
    (r'\.setPortState\(.+?[\'"]no shutdown[\'"]\)', 'sw_port_enable', {}),
    (r'\.setPortState\(.+?[\'"]shutdown[\'"]\)', 'sw_port_disable', {}),
    (r'\.setPortLinkDetection\(', 'sw_send_cmd', {}),
    (r'\.chkPortStatus\(.+?[\'"]link[\'"]\s*,\s*[\'"]down[\'"]\)', 'verify_link_status', {'EXPECTED': 'down'}),
    (r'\.chkPortStatus\(.+?[\'"]link[\'"]\s*,\s*[\'"]up[\'"]\)', 'verify_link_status', {'EXPECTED': 'up'}),
    (r'\.chkSnmpTrap\(.+?linkDown', 'verify_snmp_trap', {'TRAP_TYPE': 'linkDown'}),
    (r'\.chkSnmpTrap\(.+?link', 'verify_snmp_trap', {'TRAP_TYPE': 'linkUp'}),
    (r'\.chkPortLinkDetection\(', 'verify_link_status', {'EXPECTED': 'up'}),
]

# Extract port number from common patterns
_PORT_RE = re.compile(r"DUT\d*\['P([A-Z])'\]|port\s*(\d+)|\[(\d+)\]")


def _extract_port(line: str) -> int:
    """Try to extract port number from a line."""
    m = _PORT_RE.search(line)
    if m:
        if m.group(1):  # PA=1, PB=2, ...
            return ord(m.group(1)) - ord('A') + 1
        return int(m.group(2) or m.group(3) or 1)
    return 1


def _make_block(block_type: str, fields: dict, block_id: str) -> dict:
    """Create a Blockly block JSON structure."""
    block = {"type": block_type, "id": block_id, "fields": {}}
    for k, v in fields.items():
        block["fields"][k] = v
    return block


def _block_to_xml(block: dict) -> str:
    """Convert a block dict to Blockly XML string."""
    btype = block["type"]
    bid = block["id"]
    xml = f'<block type="{btype}" id="{bid}">'
    for fname, fval in block.get("fields", {}).items():
        xml += f'<field name="{fname}">{fval}</field>'
    if "next" in block:
        xml += '<next>' + _block_to_xml(block["next"]["block"]) + '</next>'
    xml += '</block>'
    return xml


def parse_script_to_blocks(script_path: Path) -> dict:
    """Parse a .py test script and return Blockly XML for workspace loading."""
    source = script_path.read_text(encoding="utf-8")

    blocks = []
    block_id = 0

    # Find the run() method body
    run_match = re.search(r'def run\(self\):(.*)', source, re.DOTALL)
    if not run_match:
        return {"type": "blockly", "xml": "<xml></xml>"}

    run_body = run_match.group(1)
    # Join multi-line statements (lines ending with open paren or backslash)
    raw_lines = run_body.splitlines()
    lines = []
    buf = ""
    for raw in raw_lines:
        stripped = raw.strip()
        if buf:
            buf += " " + stripped
            if stripped.endswith(")") or (buf.count("(") <= buf.count(")")):
                lines.append(buf)
                buf = ""
        elif stripped.endswith("(") or (stripped.count("(") > stripped.count(")")):
            buf = stripped
        else:
            lines.append(stripped)
    if buf:
        lines.append(buf)

    for stripped in lines:
        if not stripped or stripped.startswith('#') or stripped.startswith('"""'):
            continue

        # Check for wait/sleep
        sleep_m = re.search(r'sleep\((\d+)\)', stripped)
        if sleep_m:
            block_id += 1
            blocks.append(_make_block('wait_seconds', {'SECONDS': int(sleep_m.group(1))}, f'b{block_id}'))
            continue

        # Check for self.step — add as message block
        step_m = re.search(r"self\.step\(\s*[\d.'\"]+\s*,\s*['\"](.+?)['\"]", stripped)
        if step_m:
            block_id += 1
            text = step_m.group(1)[:50]
            # Escape XML special chars
            text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            blocks.append(_make_block('message', {'TEXT': text}, f'b{block_id}'))
            continue

        # Match known patterns
        for pattern, btype, extra_fields in _PATTERNS:
            m = re.search(pattern, stripped)
            if m:
                block_id += 1
                fields = dict(extra_fields)
                # Extract fields from regex groups
                # --- MFG blocks: pull kwargs from the self.xxx(...) call ---
                if btype == 'atlas_scan_barcode':
                    mm = re.search(r'source\s*=\s*[\'"]([^\'"]+)[\'"]', stripped)
                    if mm:
                        fields['SOURCE'] = mm.group(1)
                    mm = re.search(r'timeout\s*=\s*(\d+)', stripped)
                    if mm:
                        fields['TIMEOUT'] = int(mm.group(1))
                    mm = re.search(r'expected_len\s*=\s*(\d+)', stripped)
                    if mm:
                        fields['EXPECTED_LEN'] = int(mm.group(1))
                elif btype == 'pdu_power_cycle' and fields.get('ACTION') == 'CYCLE':
                    mm = re.search(r'off_delay\s*=\s*([\d.]+)', stripped)
                    if mm:
                        fields['DELAY'] = mm.group(1)
                elif btype == 'atlas_enter_tip_kernel':
                    mm = re.search(r'username\s*=\s*[\'"]([^\'"]*)[\'"]', stripped)
                    if mm:
                        fields['USERNAME'] = mm.group(1)
                    mm = re.search(r'password\s*=\s*[\'"]([^\'"]*)[\'"]', stripped)
                    if mm:
                        fields['PASSWORD'] = mm.group(1)
                elif btype == 'atlas_prepare_certification':
                    mm = re.search(r'cert_server\s*=\s*[\'"]([^\'"]+)[\'"]', stripped)
                    if mm:
                        fields['CERT_SERVER'] = mm.group(1)
                elif btype == 'qcc_check_versions':
                    mm = re.search(r'mm_expected\s*=\s*[\'"]([^\'"]*)[\'"]', stripped)
                    if mm:
                        fields['MM_EXPECTED'] = mm.group(1)
                elif btype == 'atlas_write_certification':
                    mm = re.search(r'dut_ip\s*=\s*[\'"]([^\'"]+)[\'"]', stripped)
                    if mm:
                        fields['DUT_IP'] = mm.group(1)
                elif btype == 'console_tftp' and m.lastindex and m.lastindex >= 2:
                    fields['ADDR'] = m.group(1)
                    raw_file = m.group(2)
                    # Resolve f-string variable to readable name
                    fvar = re.search(r"\{.*?(\w+)'\]?\}", raw_file)
                    fields['FILE'] = fvar.group(1) if fvar else raw_file
                    if m.lastindex >= 3:
                        fields['TIMEOUT'] = int(m.group(3))
                elif btype == 'console_nand_erase' and m.lastindex and m.lastindex >= 2:
                    fields['OFFSET'] = m.group(1)
                    fields['SIZE'] = m.group(2)
                elif btype == 'console_nand_write' and m.lastindex and m.lastindex >= 3:
                    fields['SRC'] = m.group(1)
                    fields['DEST'] = m.group(2)
                    fields['SIZE'] = m.group(3)
                elif btype == 'console_send' and m.lastindex:
                    fields['CMD'] = m.group(1)
                elif btype == 'ssh_cmd' and m.lastindex:
                    fields['CMD'] = m.group(1)
                elif btype == 'wait_ssh_ready':
                    timeout_m = re.search(r'timeout=(\d+)', stripped)
                    if timeout_m:
                        fields['TIMEOUT'] = int(timeout_m.group(1))
                elif btype == 'iperf_server':
                    port_m = re.search(r'"-p",\s*"(\d+)"', stripped)
                    if port_m:
                        fields['PORT'] = int(port_m.group(1))
                elif btype == 'iperf_client':
                    tgt_m = re.search(r'"-c",\s*"([^"]+)"', stripped)
                    if tgt_m:
                        fields['TARGET'] = tgt_m.group(1)
                    port_m = re.search(r'"-p",\s*"(\d+)"', stripped)
                    if port_m:
                        fields['PORT'] = int(port_m.group(1))
                    dur_m = re.search(r'"-t",\s*"(\d+)"', stripped)
                    if dur_m:
                        fields['DURATION'] = int(dur_m.group(1))
                    bind_m = re.search(r'"-B",\s*"([^"]+)"', stripped)
                    if bind_m:
                        fields['BIND'] = bind_m.group(1)
                else:
                    port = _extract_port(stripped)
                    if 'PORT' not in fields and btype in ('sw_port_enable', 'sw_port_disable', 'verify_link_status'):
                        fields['PORT'] = port
                    if btype == 'sw_send_cmd':
                        cmd_m = re.search(r"['\"]([^'\"]+)['\"]", stripped)
                        val = cmd_m.group(1) if cmd_m else stripped[:40]
                        fields['CMD'] = val.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                blocks.append(_make_block(btype, fields, f'b{block_id}'))
                break

    if not blocks:
        return {"type": "blockly", "xml": "<xml></xml>"}

    # Chain blocks via next
    for i in range(len(blocks) - 1):
        blocks[i]["next"] = {"block": blocks[i + 1]}

    # Build XML
    xml = '<xml xmlns="https://developers.google.com/blockly/xml">'
    xml += _block_to_xml(blocks[0])
    xml += '</xml>'

    return {"type": "blockly", "xml": xml}
