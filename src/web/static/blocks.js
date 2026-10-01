/**
 * WLAN Test GUI — Custom Blockly Block Definitions (5 Layers)
 * Layer 0: Band (blue)
 * Layer 1: Config (green)
 * Layer 2: Connect (yellow)
 * Layer 3: Traffic (orange)
 * Layer 4: Verify (red)
 */

// === Layer 0: Band (colour 210) ===

Blockly.Blocks['band_5g'] = {
  init: function() {
    this.appendDummyInput().appendField("📡 Band 5GHz");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(210);
    this.setTooltip("Set AP to 5GHz band");
  }
};

Blockly.Blocks['band_2g'] = {
  init: function() {
    this.appendDummyInput().appendField("📡 Band 2.4GHz");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(210);
    this.setTooltip("Set AP to 2.4GHz band");
  }
};

// === Layer 1: Config (colour 130) ===

Blockly.Blocks['mode_bridge'] = {
  init: function() {
    this.appendDummyInput().appendField("⚙️ Mode: Bridge");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(130);
    this.setTooltip("Set AP to bridge mode");
  }
};

Blockly.Blocks['mode_nat'] = {
  init: function() {
    this.appendDummyInput().appendField("⚙️ Mode: NAT");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(130);
    this.setTooltip("Set AP to NAT mode");
  }
};

Blockly.Blocks['mode_vlan'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("⚙️ Mode: VLAN")
        .appendField(new Blockly.FieldNumber(100, 1, 4094), "VID");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(130);
    this.setTooltip("Set AP to bridge mode with VLAN tagging");
  }
};

// === Layer 2: Connect (colour 60) ===

Blockly.Blocks['connect_open'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("📶 Connect Open")
        .appendField("SSID")
        .appendField(new Blockly.FieldTextInput("test_open"), "SSID");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(60);
    this.setTooltip("Connect WiFi client with open security");
  }
};

Blockly.Blocks['connect_wpa2'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("📶 Connect WPA2");
    this.appendDummyInput()
        .appendField("SSID")
        .appendField(new Blockly.FieldTextInput("test_wpa2"), "SSID");
    this.appendDummyInput()
        .appendField("Password")
        .appendField(new Blockly.FieldTextInput("12345678"), "PASSWORD");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(60);
    this.setTooltip("Connect WiFi client with WPA2 security");
  }
};

Blockly.Blocks['connect_wpa3'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("📶 Connect WPA3");
    this.appendDummyInput()
        .appendField("SSID")
        .appendField(new Blockly.FieldTextInput("test_wpa3"), "SSID");
    this.appendDummyInput()
        .appendField("Password")
        .appendField(new Blockly.FieldTextInput("12345678"), "PASSWORD");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(60);
    this.setTooltip("Connect WiFi client with WPA3 security");
  }
};

// === Layer 3: Traffic (colour 30) ===

Blockly.Blocks['traffic_c50'] = {
  init: function() {
    this.appendDummyInput().appendField("🚀 C50 Traffic");
    this.appendDummyInput()
        .appendField("duration")
        .appendField(new Blockly.FieldNumber(30, 1, 300), "DURATION")
        .appendField("sec");
    this.appendDummyInput()
        .appendField("rate")
        .appendField(new Blockly.FieldNumber(50000, 100, 1000000), "RATE_PPS")
        .appendField("pps");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(30);
    this.setTooltip("Run Spirent C50 traffic");
  }
};

Blockly.Blocks['traffic_iperf'] = {
  init: function() {
    this.appendDummyInput().appendField("🚀 iperf3 Traffic");
    this.appendDummyInput()
        .appendField("duration")
        .appendField(new Blockly.FieldNumber(30, 1, 300), "DURATION")
        .appendField("sec");
    this.appendDummyInput()
        .appendField("parallel")
        .appendField(new Blockly.FieldNumber(4, 1, 32), "PARALLEL");
    this.appendDummyInput()
        .appendField("UDP")
        .appendField(new Blockly.FieldCheckbox("FALSE"), "UDP");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(30);
    this.setTooltip("Run iperf3 traffic test");
  }
};

// === Layer 4: Verify (colour 0) ===

Blockly.Blocks['verify_throughput'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("✅ Verify Throughput ≥")
        .appendField(new Blockly.FieldNumber(300, 1, 10000), "MIN_MBPS")
        .appendField("Mbps");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(0);
    this.setTooltip("Assert throughput meets minimum");
  }
};

Blockly.Blocks['verify_no_loss'] = {
  init: function() {
    this.appendDummyInput().appendField("✅ Verify No Packet Loss");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(0);
    this.setTooltip("Assert zero packet loss (<1%)");
  }
};

Blockly.Blocks['verify_ping'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("✅ Verify Ping")
        .appendField(new Blockly.FieldTextInput(""), "TARGET");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(0);
    this.setTooltip("Ping target IP (empty = AP IP)");
  }
};

Blockly.Blocks['verify_connected'] = {
  init: function() {
    this.appendDummyInput().appendField("✅ Verify Connected");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(0);
    this.setTooltip("Assert WiFi client is connected");
  }
};

Blockly.Blocks['verify_latency'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("✅ Verify Latency ≤")
        .appendField(new Blockly.FieldNumber(10, 1, 1000), "MAX_MS")
        .appendField("ms");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(0);
    this.setTooltip("Assert latency/jitter below threshold");
  }
};

// === SW Config (colour 160) ===

Blockly.Blocks['sw_vlan_create'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("🔧 SW VLAN Create")
        .appendField(new Blockly.FieldNumber(100, 1, 4094), "VID");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Create VLAN on switch");
  }
};

Blockly.Blocks['sw_port_vlan'] = {
  init: function() {
    this.appendDummyInput().appendField("🔧 SW Port VLAN");
    this.appendDummyInput()
        .appendField("port")
        .appendField(new Blockly.FieldNumber(1, 1, 54), "PORT");
    this.appendDummyInput()
        .appendField("VLAN")
        .appendField(new Blockly.FieldNumber(100, 1, 4094), "VID");
    this.appendDummyInput()
        .appendField("tagged")
        .appendField(new Blockly.FieldCheckbox("FALSE"), "TAGGED");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Assign VLAN to switch port");
  }
};

Blockly.Blocks['sw_port_enable'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("🔧 SW Port Enable")
        .appendField("port")
        .appendField(new Blockly.FieldNumber(1, 1, 54), "PORT");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Enable (no shut) switch port");
  }
};

Blockly.Blocks['sw_port_disable'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("🔧 SW Port Disable")
        .appendField("port")
        .appendField(new Blockly.FieldNumber(1, 1, 54), "PORT");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Disable (shut) switch port");
  }
};

Blockly.Blocks['sw_send_cmd'] = {
  init: function() {
    this.appendDummyInput().appendField("🔧 SW Command");
    this.appendDummyInput()
        .appendField(new Blockly.FieldTextInput("show vlan"), "CMD");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Send CLI command to switch");
  }
};

// === Verify (new blocks) ===

Blockly.Blocks['verify_link_status'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("✅ Verify Link Status")
        .appendField("port")
        .appendField(new Blockly.FieldNumber(1, 1, 54), "PORT");
    this.appendDummyInput()
        .appendField("expected")
        .appendField(new Blockly.FieldDropdown([["up","up"],["down","down"]]), "EXPECTED");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(0);
    this.setTooltip("Verify switch port link status");
  }
};

Blockly.Blocks['verify_snmp_trap'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("✅ Verify SNMP Trap")
        .appendField(new Blockly.FieldDropdown([["linkDown","linkDown"],["linkUp","linkUp"]]), "TRAP_TYPE");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(0);
    this.setTooltip("Verify SNMP trap received");
  }
};

// === Utility (colour 290) ===

Blockly.Blocks['wait_seconds'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("⏱️ Wait")
        .appendField(new Blockly.FieldNumber(5, 1, 300), "SECONDS")
        .appendField("sec");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(290);
    this.setTooltip("Wait N seconds");
  }
};

Blockly.Blocks['message'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("💬 Message");
    this.appendDummyInput()
        .appendField(new Blockly.FieldTextInput("step info"), "TEXT");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(290);
    this.setTooltip("Log a message");
  }
};

// === Layer 5: Console / Manufacturing (colour 180) ===

Blockly.Blocks['console_connect'] = {
  init: function() {
    this.appendDummyInput().appendField("🔌 Console Connect");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(180);
    this.setTooltip("Connect to DUT serial console");
  }
};

Blockly.Blocks['console_send'] = {
  init: function() {
    this.appendDummyInput().appendField("⌨️ Console Send");
    this.appendDummyInput()
        .appendField(new Blockly.FieldTextInput("help"), "CMD");
    this.appendDummyInput()
        .appendField("timeout")
        .appendField(new Blockly.FieldNumber(30, 1, 300), "TIMEOUT")
        .appendField("sec");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(180);
    this.setTooltip("Send command to console and wait for prompt");
  }
};

Blockly.Blocks['console_tftp'] = {
  init: function() {
    this.appendDummyInput().appendField("📥 TFTP Download");
    this.appendDummyInput()
        .appendField("file")
        .appendField(new Blockly.FieldTextInput("fip.bin"), "FILE");
    this.appendDummyInput()
        .appendField("addr")
        .appendField(new Blockly.FieldTextInput("0x46000000"), "ADDR");
    this.appendDummyInput()
        .appendField("timeout")
        .appendField(new Blockly.FieldNumber(60, 10, 300), "TIMEOUT")
        .appendField("sec");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(180);
    this.setTooltip("TFTP download file to memory address");
  }
};

Blockly.Blocks['console_nand_erase'] = {
  init: function() {
    this.appendDummyInput().appendField("🗑️ NAND Erase");
    this.appendDummyInput()
        .appendField("offset")
        .appendField(new Blockly.FieldTextInput("0x00380000"), "OFFSET");
    this.appendDummyInput()
        .appendField("size")
        .appendField(new Blockly.FieldTextInput("0x00200000"), "SIZE");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(180);
    this.setTooltip("Erase NAND region via nmbm");
  }
};

Blockly.Blocks['console_nand_write'] = {
  init: function() {
    this.appendDummyInput().appendField("💾 NAND Write");
    this.appendDummyInput()
        .appendField("src")
        .appendField(new Blockly.FieldTextInput("0x46000000"), "SRC");
    this.appendDummyInput()
        .appendField("dest")
        .appendField(new Blockly.FieldTextInput("0x00580000"), "DEST");
    this.appendDummyInput()
        .appendField("size")
        .appendField(new Blockly.FieldTextInput("${filesize}"), "SIZE");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(180);
    this.setTooltip("Write data from memory to NAND via nmbm");
  }
};

Blockly.Blocks['console_reset'] = {
  init: function() {
    this.appendDummyInput().appendField("🔄 Reset DUT");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(180);
    this.setTooltip("Send reset command to reboot DUT");
  }
};

Blockly.Blocks['ssh_cmd'] = {
  init: function() {
    this.appendDummyInput().appendField("🖥️ SSH Command");
    this.appendDummyInput()
        .appendField(new Blockly.FieldTextInput("cat /etc/openwrt_release"), "CMD");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(180);
    this.setTooltip("Execute command on AP via SSH");
  }
};

Blockly.Blocks['verify_version'] = {
  init: function() {
    this.appendDummyInput().appendField("✅ Verify FW Version");
    this.appendDummyInput()
        .appendField(new Blockly.FieldTextInput("Shasta-AP-NOS Rel 3.4 build 23"), "EXPECTED");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(0);
    this.setTooltip("Verify firmware version string via SSH");
  }
};

Blockly.Blocks['wait_ssh_ready'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("⏱️ Wait SSH Ready")
        .appendField("timeout")
        .appendField(new Blockly.FieldNumber(120, 10, 600), "TIMEOUT")
        .appendField("sec");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(290);
    this.setTooltip("Wait until AP is reachable via SSH");
  }
};

// === iperf3 (colour 30) ===

Blockly.Blocks['iperf_server'] = {
  init: function() {
    this.appendDummyInput().appendField("🚀 iperf3 Server");
    this.appendDummyInput()
        .appendField("port")
        .appendField(new Blockly.FieldNumber(5201, 1024, 65535), "PORT");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(30);
    this.setTooltip("Start iperf3 server (single run)");
  }
};

Blockly.Blocks['iperf_client'] = {
  init: function() {
    this.appendDummyInput().appendField("🚀 iperf3 Client");
    this.appendDummyInput()
        .appendField("target")
        .appendField(new Blockly.FieldTextInput("192.168.1.2"), "TARGET");
    this.appendDummyInput()
        .appendField("port")
        .appendField(new Blockly.FieldNumber(5201, 1024, 65535), "PORT");
    this.appendDummyInput()
        .appendField("duration")
        .appendField(new Blockly.FieldNumber(10, 1, 300), "DURATION")
        .appendField("sec");
    this.appendDummyInput()
        .appendField("bind")
        .appendField(new Blockly.FieldTextInput(""), "BIND");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(30);
    this.setTooltip("Run iperf3 client and measure throughput");
  }
};

// ─────────────────────────────────────────────────────────────
// EAP111 Manufacturing (MFG) Blocks
// ─────────────────────────────────────────────────────────────

Blockly.Blocks['atlas_scan_barcode'] = {
  init: function() {
    this.appendDummyInput().appendField("🏭 Scan SN + MAC (2 scans)");
    this.appendDummyInput()
        .appendField("source")
        .appendField(new Blockly.FieldDropdown([
          ["USB HID keyboard", "usb_hid"],
          ["Serial console", "serial"],
        ]), "SOURCE");
    this.appendDummyInput()
        .appendField("timeout")
        .appendField(new Blockly.FieldNumber(30, 1, 300), "TIMEOUT")
        .appendField(" sec");
    this.appendDummyInput()
        .appendField("SN expected length (0=off)")
        .appendField(new Blockly.FieldNumber(12, 0, 64), "EXPECTED_LEN");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("Scan two barcodes in any order; auto-detect SN (starts with a letter) and MAC (12 hex). Compared against hardware values in Read HW Version.");
  }
};

Blockly.Blocks['atlas_write_manufacturing_data'] = {
  init: function() {
    this.appendDummyInput().appendField("🏭 Write MAC & SN");
    this.appendDummyInput()
        .appendField("MAC & SN from Scan SN + MAC");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("Write MAC address and serial number (from the scanned SN & MAC) to U-Boot env");
  }
};

Blockly.Blocks['atlas_enter_uboot_menu'] = {
  init: function() {
    this.appendDummyInput().appendField("🏭 Enter U-Boot Menu");
    this.appendDummyInput()
        .appendField("timeout")
        .appendField(new Blockly.FieldNumber(90, 1, 300), "TIMEOUT")
        .appendField(" sec");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("Power cycle (DC OFF→ON), wait for U-Boot menu, interrupt autoboot");
  }
};

Blockly.Blocks['atlas_read_hw_version'] = {
  init: function() {
    this.appendDummyInput().appendField("🏭 Read HW Version");
    this.appendDummyInput()
        .appendField("compare SN & MAC from Scan SN + MAC");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("Read MAC/SN from factory MTD and compare against the scanned SN & MAC (from Scan SN + MAC). Model/HW Rev are read for logging only.");
  }
};

Blockly.Blocks['atlas_update_flash_image'] = {
  init: function() {
    this.appendDummyInput().appendField("🏭 Update Flash Image");
    this.appendDummyInput()
        .appendField("TFTP server")
        .appendField(new Blockly.FieldTextInput("192.168.1.100"), "TFTP_SERVER");
    this.appendDummyInput()
        .appendField("DUT IP")
        .appendField(new Blockly.FieldTextInput("192.168.1.10"), "DUT_IP");
    this.appendDummyInput()
        .appendField("FIP image")
        .appendField(new Blockly.FieldTextInput("tip_fip.bin"), "FIP_IMAGE");
    this.appendDummyInput()
        .appendField("FW image")
        .appendField(new Blockly.FieldTextInput("openwrt-mediatek-mt7981-edgecore_eap111-squashfs-factory.bin"), "FW_IMAGE");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("TFTP download FIP + OpenWrt image and flash to NAND");
  }
};

Blockly.Blocks['atlas_write_uboot_env_serial'] = {
  init: function() {
    this.appendDummyInput().appendField("🏭 Write U-Boot Env (Serial)");
    this.appendDummyInput()
        .appendField("serial number")
        .appendField(new Blockly.FieldTextInput(""), "SERIAL_NUMBER");
    this.appendDummyInput()
        .appendField("bootcount")
        .appendField(new Blockly.FieldNumber(0, 0, 10), "BOOTCOUNT");
    this.appendDummyInput()
        .appendField("active")
        .appendField(new Blockly.FieldNumber(1, 0, 1), "ACTIVE");
    this.appendDummyInput()
        .appendField("upgrade_available")
        .appendField(new Blockly.FieldNumber(1, 0, 1), "UPGRADE_AVAILABLE");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("Write U-Boot env vars: bootcount, active, upgrade_available, SN");
  }
};

Blockly.Blocks['atlas_enter_tip_kernel'] = {
  init: function() {
    this.appendDummyInput().appendField("🏭 Enter TIP Kernel (Login)");
    this.appendDummyInput()
        .appendField("timeout")
        .appendField(new Blockly.FieldNumber(90, 1, 300), "TIMEOUT")
        .appendField(" sec");
    this.appendDummyInput()
        .appendField("user")
        .appendField(new Blockly.FieldTextInput("root"), "USERNAME");
    this.appendDummyInput()
        .appendField("password")
        .appendField(new Blockly.FieldTextInput(""), "PASSWORD");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("Wait for Linux login prompt, then log in with the given user/password (blank password = just Enter)");
  }
};

Blockly.Blocks['atlas_check_tip_version'] = {
  init: function() {
    this.appendDummyInput().appendField("🏭 Check TIP Version");
    this.appendDummyInput()
        .appendField("expected version")
        .appendField(new Blockly.FieldTextInput("v4.1.1"), "EXPECTED_VERSION");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("Verify TIP/OpenWrt version matches expected (login already done by Enter TIP Kernel)");
  }
};

Blockly.Blocks['atlas_check_manufacturing_data'] = {
  init: function() {
    this.appendDummyInput().appendField("🏭 Check Manufacturing Data");
    this.appendDummyInput()
        .appendField("verify SN")
        .appendField(new Blockly.FieldCheckbox("TRUE"), "VERIFY_SN");
    this.appendDummyInput()
        .appendField("verify MAC")
        .appendField(new Blockly.FieldCheckbox("TRUE"), "VERIFY_MAC");
    this.appendDummyInput()
        .appendField("verify Model")
        .appendField(new Blockly.FieldCheckbox("TRUE"), "VERIFY_MODEL");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("Run jffs2reset + reboot, then check manufacturing data in U-Boot");
  }
};

Blockly.Blocks['atlas_reboot_and_wait_login'] = {
  init: function() {
    this.appendDummyInput().appendField("🏭 Reboot & Wait Login");
    this.appendDummyInput()
        .appendField("timeout")
        .appendField(new Blockly.FieldNumber(90, 1, 300), "TIMEOUT")
        .appendField(" sec");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("Execute reboot and wait for login prompt (second Linux entry)");
  }
};

Blockly.Blocks['atlas_reset_default'] = {
  init: function() {
    this.appendDummyInput().appendField("🏭 Reset to Default");
    this.appendDummyInput()
        .appendField("timeout")
        .appendField(new Blockly.FieldNumber(90, 1, 300), "TIMEOUT")
        .appendField(" sec");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("jffs2reset + reboot, final stop at U-Boot menu (end of MFG flow)");
  }
};

// ── PDU power control (FT232H C0/C1 relay) ──
Blockly.Blocks['pdu_power_cycle'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("⚡ DUT Power")
        .appendField(new Blockly.FieldDropdown([
          ["ON (通電)", "ON"],
          ["OFF (斷電)", "OFF"],
          ["Power-Cycle (OFF→ON)", "CYCLE"]
        ]), "ACTION");
    this.appendDummyInput()
        .appendField("OFF delay")
        .appendField(new Blockly.FieldNumber(2, 0, 60, 0.1), "DELAY")
        .appendField("sec (cycle only)");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("Control DUT power via FT232H relay (C0/C1): ON, OFF, or power-cycle (OFF then ON). DELAY = seconds to stay OFF during power-cycle.");
  }
};

// ── Certification (STUB blocks; backend methods are placeholders) ──
Blockly.Blocks['atlas_prepare_certification'] = {
  init: function() {
    this.appendDummyInput().appendField("🔐 Prepare Certification");
    this.appendDummyInput()
        .appendField("cert server")
        .appendField(new Blockly.FieldTextInput("prod-cert.accton.com"), "CERT_SERVER");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("[STUB] Ping cert server, login, generate + download cert bundle");
  }
};

Blockly.Blocks['atlas_write_certification'] = {
  init: function() {
    this.appendDummyInput().appendField("🔐 Write Certification");
    this.appendDummyInput()
        .appendField("DUT IP")
        .appendField(new Blockly.FieldTextInput("192.168.1.20"), "DUT_IP");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("[STUB] Upload cert bundle to DUT /certificates/ and md5 verify");
  }
};

Blockly.Blocks['atlas_check_certification'] = {
  init: function() {
    this.appendDummyInput().appendField("🔐 Check Certification");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("[STUB] Mount certificates volume on DUT and verify cert md5");
  }
};


// ---------------------------------------------------------------------------
// Pi7a (Qualcomm QCC744 / QCC74x) manufacturing core-subset blocks.
// Parameters (CLI commands / expected strings / thresholds) come from the
// testbed ap.mfg block, so these blocks have NO fields. Colour 160 (teal)
// distinguishes them from EAP111/OAP101 (atlas_*, colour 200).
// ---------------------------------------------------------------------------
Blockly.Blocks['qcc_connect'] = {
  init: function() {
    this.appendDummyInput().appendField("📶 Pi7a: Connect (power on + qcc74x /> )");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("DC Jack power on and wait for the QCC74x firmware CLI prompt");
  }
};

Blockly.Blocks['qcc_power_mode_test'] = {
  init: function() {
    this.appendDummyInput().appendField("📶 Pi7a: Power Mode Test (power_mode 0/1)");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Read charger power mode on both I2C buses (Battery/USB power)");
  }
};

Blockly.Blocks['qcc_battery_mode_test'] = {
  init: function() {
    this.appendDummyInput().appendField("📶 Pi7a: Battery Mode Test (battery_mode 0)");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Read charger battery mode (Battery Discharging/Charging)");
  }
};

Blockly.Blocks['qcc_fuel_gauge_test'] = {
  init: function() {
    this.appendDummyInput().appendField("📶 Pi7a: Fuel Gauge Test (fuel_gauge 0/1)");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Read SY6410 fuel gauge voltage; verify within ap.mfg limits");
  }
};

Blockly.Blocks['qcc_check_versions'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("📶 Pi7a: Check Versions (diag + mm)");
    this.appendDummyInput()
        .appendField("mm_version 期望(留空=只記錄)")
        .appendField(new Blockly.FieldTextInput(""), "MM_EXPECTED");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Check diag_version (vs ap.mfg.diag_version_expected) and mm_version. mm_version: 填期望字串則需包含否則 FAIL；留空只記錄。可只填主版本如 1.5.0 做前綴比對。");
  }
};

Blockly.Blocks['qcc_i2c_scan'] = {
  init: function() {
    this.appendDummyInput().appendField("📶 Pi7a: I2C Scan (i2c_scan 0/1)");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Scan both I2C buses; verify expected addresses present");
  }
};

Blockly.Blocks['qcc_factory_write'] = {
  init: function() {
    this.appendDummyInput().appendField("📶 Pi7a: Factory Write (factory w MAC SN Model HWver)");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Write SN/MAC (from Scan) + Model/HWver (from ap.mfg) to factory");
  }
};

Blockly.Blocks['qcc_factory_check'] = {
  init: function() {
    this.appendDummyInput().appendField("📶 Pi7a: Factory Check (factory r)");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Read back factory and verify 6 fields (halow/wifi/ble MAC, SN, Model, HWver)");
  }
};

Blockly.Blocks['qcc_led_test'] = {
  init: function() {
    this.appendDummyInput().appendField("📶 Pi7a: LED Test (led all on/off)");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Turn all LEDs on then off (visual check)");
  }
};

Blockly.Blocks['qcc_reset_button_test'] = {
  init: function() {
    this.appendDummyInput().appendField("📶 Pi7a: Reset Button Test (hold >=5s)");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Operator holds reset >=5s; verify defaults reset and factory preserved");
  }
};

Blockly.Blocks['qcc_wdt_test'] = {
  init: function() {
    this.appendDummyInput().appendField("📶 Pi7a: Watchdog Test (wdt_reboot)");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Trigger WDT reboot (wdt_reboot) and verify DUT comes back");
  }
};
