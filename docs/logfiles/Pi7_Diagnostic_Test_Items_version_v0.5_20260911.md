# Diagnostic Test Items Specification

**Pi7**

*Revision v0.5*

Sep. 11 ,2026

Accton Technology Corporation

No. 1, Creation Rd. III, Science-Based Industrial Park,

Hsinchu 300, Taiwan, R.O.C.

**Copyright © 2026 Accton Technology Corporation. All rights reserved.**

**Contents**

1 Introduction 4

1.1 Purpose 4

1.2 Scope 4

1.3 Software Requirements 4

1.4 Hardware Requirements 4

1.5 Reference Documents 4

2 Accton Diag Function Description 6

2.1 Commands for function test 7

2.1.1 DIAG VERSION 7

2.1.2 POWER MODE TEST 7

2.1.3 BATTERY MODE TEST 8

2.1.4 FUEL GAUGE TEST 8

2.1.5 LED TEST 8

2.1.6 WDT TEST 9

2.1.7 Writing to GPIO output pins 9

2.1.8 Reading GPIO pins 10

2.1.9 I2C SCAN TEST 10

2.1.10 I2C GET TEST 10

2.1.11 I2C SET TEST 11

2.1.12 I2C DUMP TEST 11

2.1.13 MFG TEST 11

2.1.14 MM TEST 12

2.1.15 MM SCAN TEST 12

2.1.16 MM SCAN STOP 13

2.1.17 BLE TEST 13

2.1.18 WiFi TEST 15

2.1.19 Check Version 16

2.1.20 MAC/SN/MODEL/HWVER WRITE 16

2.1.21 MAC/SN/MODEL/HWVER READ 17

## Revision History

| Revision | Date | Author | Description |
| --- | --- | --- | --- |
| 0.1 | 2025/10/2 | Brian Lin | Add Diag code CLI command |
| 0.2 | 2026/01/21 | Brian Lin | Set default country code to JP |
| 0.3 | 2026/04/08 | Brian Lin | Change MP2720A_OTP battery charger init value<br>Support fuel gauge new chip : SY6410 on i2c0, i2c1 |
| 0.4 | 2026/08/27 | Lanqly Chou | Add version check |
| 0.5 | 2026/09/11 | Brian Lin | Add MAC/SN/MODEL/HWVER read/write command |

---

# 1 Introduction

## 1.1 Purpose

This document provides the functional specification for the Accton Diagnostic.

User can get information about what functions provided by Accton Diagnostic and it also how to use that to test the condition and stability of Pi7 hardware. Also describes the detail of the function test item and result for User to use.

## 1.2 Scope

The scope of this document is to present the complete functional test description of Pi7 products. The intended audience for this document includes the Hardware Engineering Design Team, Manufacture Automation Team, Development Team, Quality Assurance and the Technical Writing Team responsible for developing the user documentation.

## 1.3 Software Requirements

The software requirements for the diagnostic programs to bring up CPU Qualcomm_QCC748 , the software provide a minimal operation system and additional drivers and the diagnostic program. The message of the diagnostic program is provided via a host computer with hyper-terminal tool.

## 1.4 Hardware Requirements

The Hardware requirements for the diagnostic programs consist of the unit under test, a hyper-Terminal connect, USB type -C cable.

## 1.5 Reference Documents

For more information, please see the following documentation:

1. Portable IoT_Pi7 Series_product requirement document_20250625

---

# 2 Accton Diag Function Description

This section contains the full description on functions which provided by Accton Diag to the user. Each command is shown by a simple description, command syntax description and usage example.

**Commands for function test**

This section details the test commands that comprise the CPU, all memory devices and its peripheral test. Each utility can cover the hardware signal and quality. Those commands are only for RD engineer debug usage.

The user can easy to use and it favors to H/W functional performance test.

All the items will base on H/W spec, the CPU command to write the script files into our diagnostic, that can very easy to let Quality Assurance to use and quick to perform. We also provide the PASS/FAIL criteria, that can reduce QA tasks. Once has the problem that can let diagnostic programmer to know which device has problem.

## 2.1 Commands for function test

The test commands of this section contain its peripheral devices.

### 2.1.1 DIAG VERSION

|  |  |
| --- | --- |
| **Command** | **diag_version** |
| **Description** | display diag version information |
| **Syntax** | diag_version |
| **Test Result** | qcc74x /> diag_version<br>Pi7 diag software version :Pi7_V0.3 |

|  |  |
| --- | --- |
| **Command** | **mm_version** |
| **Description** | display Morse micro software version information |
| **Syntax** | mm_version |
| **Test Result** | qcc74x /> mm_version<br>Morse Micro V1.4 |

### 2.1.2 POWER MODE TEST

|  |  |
| --- | --- |
| **Command** | **power_mode** |
| **Description** | To check the power supply source type. |
| **Syntax** | power_mode |
| **Test Result** | **#PASS LOG:** <br>qcc74x /> power_mode 0<br>Read Charger power mode from I2C0<br>Power Mode: USB power (OK)<br>or<br>Power Mode: Battery power (OK)<br>**#FAIL LOG:**<br>qcc74x /> power_mode 1<br>I2C read error<br>Failed to get power mode status (FAILED) |

### 2.1.3 BATTERY MODE TEST

| **Command** | **battery_mode** |
| --- | --- |
| **Description** | To check the power supply source type in battery charging process |
| **Syntax** | battery_mode \<i2c bus 0,1> |
| **Test Result** | **#PASS LOG:**<br>qcc74x /> battery_mode 0<br>Read Charger battery mode from I2C0<br>Reg13 raw: 0xA0<br>Reg11 raw: 0x80<br>Battery Discharging => OK<br>**#FAIL LOG:**<br>qcc74x /> battery_mode 0<br>I2C read error => FAILED<br>Battery Missing! => FAILED |

### 2.1.4 FUEL GAUGE TEST

|  |  |
| --- | --- |
| **Command** | **fuel_gauge** |
| **Description** | To display battery status from SY62510 fuel gauge IC |
| **Syntax** | Fuel_gauge |
| **Test Result** | qcc74x /> fuel_gauge 0<br>I2C0 SY6410 FUEL GAUGE STATUS:<br>Fail to read from I2C0 0x30 register 0x02.<br>qcc74x /> fuel_gauge 1<br>I2C1 SY6410 FUEL GAUGE STATUS:<br>Fail to read from I2C1 0x30 register 0x02. |

### 2.1.5 LED TEST

| **Command** | **led** |
| --- | --- |
| **Description** | Pi7 LED on/off command |
| **Syntax** | usage: led \[1-4\|all] \[on\|off\|flash] \[on time in 100ms unit (default:1)] \[off time in 100ms unit (default:1)] |
| **Test Result** | qcc74x />led all on<br>Pi7 LED all on<br>qcc74x />led 1 flash 5 5<br>Pi7 LED 1 flash on 500ms off 500ms<br>qcc74x /> |

### 2.1.6 WDT TEST

|  |  |
| --- | --- |
| **Command** | **wdt_reboot** |
| **Description** | Stop the External WDT trigger task then force Ext. WDT to reboot the system |
| **Syntax** | wdt_reboot |
| **Test Result** | qcc74x />wdt_reboot<br>Force WDT reboot after 6 seconds |

### 2.1.7 Writing to GPIO output pins

| **Command** | **gpioset** |
| --- | --- |
| **Description** | Set GPIO to High/Low |
| **Syntax** | usage: gpioset \<gpio_number> <0\|1> |
| **Test Result** | **#Set GPIO port 3 pin to High**:<br>qcc74x />gpioset 3 1<br>GPIO_3=1<br>qcc74x /><br>**#Set GPIO port 3 pin to Low**:<br>qcc74x />gpioset 3 0<br>GPIO_3=0 |

### 2.1.8 Reading GPIO pins

| **Command** | **gpioget** |
| --- | --- |
| **Description** | Read GPIO status |
| **Syntax** | usage: gpioget \<gpio_number> |
| **Test Result** | **#Get GPIO port 3 pin status**<br>qcc74x />gpioget 3<br>GPIO_3=1 |

### 2.1.9 I2C SCAN TEST

| **Command** | **i2c_scan,i2c_scan1** |
| --- | --- |
| **Description** | Scanning I2C device from I2C bus 0, 1 |
| **Syntax** | usage:i2c_scan |
| **Test Result** | qcc74x />i2c_scan<br>Scanning I2C bus 0:<br>...............................................................................<br>.0x3F<br>.0x55<br>.0x60<br>.........................................<br>qcc74x />i2c_scan1<br>Scanning I2C bus 1:<br>................................................................ |

### 2.1.10 I2C GET TEST

| **Command** | **i2cget** |
| --- | --- |
| **Description** | Read data from I2C device |
| **Syntax** | usage: i2cget \<slave_address> \<register_address> |
| **Test Result** | qcc74x />i2cget 50 00<br>I2C get 0x50 register 0x00 = 0xDF:<br>i2cget 0 30 00 |

### 2.1.11 I2C SET TEST

| **Command** | **i2cset** |
| --- | --- |
| **Description** | Write data to I2C device |
| **Syntax** | usage: i2cset \<slave_address> \<register_address> \<value> |
| **Test Result** | qcc74x />i2cset 50 00 01<br>I2C set 0x50 register 0x00 = 0x01 |

### 2.1.12 I2C DUMP TEST

| **Command** | **i2cdump** |
| --- | --- |
| **Description** | Dump data from I2C device |
| **Syntax** | usage: i2cdump i2c_bus slave_address dump_data_length |
| **Test Result** | qcc74x />i2cdump 0 0x50 0x2f<br>I2C0 Dump from device 0x50<br>00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F<br>00 DF 54 DF 54 DF 54 DF 54 DF 54 DF FF FF DF FF DF<br>10 50 F0 00 03 00 FF 00 FF FF FF FF FF FF FF FF FF<br>20 00 FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF |

### 2.1.13 MFG TEST

|  |  |
| --- | --- |
| **Command** | **mfg** |
| **Description** | QCC74x mfg test |
| **Syntax** | mfg |
| **Test Result** | (empty) |

### 2.1.14 MM TEST

|  |  |
| --- | --- |
| **Command** | **mm_test** |
| **Description** | Morse micro Porting Assistant |
| **Syntax** | mm_test |
| **Test Result** | qcc74x />mm_test<br>MM-IoT-SDK Porting Assistant<br>----------------------------<br>Memory allocation                                            [ PASS ]<br>Memory reallocation                                          [ PASS ]<br>Passage of time                                              [ PASS ]<br>Task creation and preemption                                 [ PASS ]<br>WLAN HAL initialisation                                      Succesful init<br>Hard reset device                                            Succesful reset<br>SDIO/SPI Startup                                             [ PASS ]<br>Read chip id from the MM chip                                Chip read<br>Chip read successful                                         [ PASS ]<br>Verify BUSY pin                                              [ PASS ]<br>Bulk write/read into the MM chip                             [ PASS ]<br>Raw throughput test                                          [ PASS ]<br>Note: This will not be the final WLAN TPUT. See test step for more info.<br>Time spent (ms):   2502<br>Transaction count: 1795<br>Bytes xferred:     5370640<br>Raw TPUT (kbit/s): 17172<br>Validate MM firmware                                         [ PASS ]<br>Validate BCF                                                 [ PASS ]<br>13 total test steps. 11 passed, 0 failed, 2 no result, 0 skipped |

### 2.1.15 MM SCAN TEST

|  |  |
| --- | --- |
| **Command** | **mm_scan** |
| **Description** | The command line utility mm_scan porting from Morse Micro V1.4.<br>If you want to launch mm_scan command, you should use mm_scan_stop command to stop the previous mm_scan process to prevent from failed at function qcc74x_malloc. |
| **Syntax** | mm_scan |
| **Test Result** | qcc74x />mm_scan<br>Morse Scan Demo (Built Sep 26 2025 10:45:40)<br>Morse firmware version 1.16.0, morselib version 2.9.4-nfp-qcc74x, Morse chip ID 0x809<br>Scan started on AU channels, Waiting for results...<br>qcc74x /><br>qcc74x />MorseMicro<br>Operating BW: 8 MHz<br>BSSID: 0c:bf:74:06:96:0a<br>RSSI: -85<br>Beacon Interval(TUs): 100<br>Capability Info: 0x0031<br>Security: SAE<br>S1G Operation:<br>Operating class: 25<br>Primary channel: 42<br>Primary channel width: 2 MHz<br>Operating channel: 44<br>Operating channel width: 8 MHz<br>Scanning completed.<br>qcc74x /> |

### 2.1.16 MM SCAN STOP

|  |  |
| --- | --- |
| **Command** | **mm_scan_stop** |
| **Description** | The command mm_scan_stop is used to stop the previous mm_scan process to prevent from out of memory situation. |
| **Syntax** | mm_scan_stop |
| **Test Result** | qcc74x />mm_scan_stop<br>done!!!!<br>qcc74x /> |

### 2.1.17 BLE TEST

**2.1.17.1 BLE SCAN TEST**

|  |  |
| --- | --- |
| **Command** | **ble_start_scan**<br>**ble_stop_scan** |
| **Description** | BLE scan commands. |
| **Test Result** | (empty) |

**2.1.17.2 BLE PERIPHERAL TEST**

|  |  |
| --- | --- |
| **Command** | **ble_init**<br>**ble_auth**<br>**ble_unpair**<br>**ble_set_adv_channel**<br>**ble_set_device_name**<br>**ble_start_adv**<br>**ble_stop_adv** |
| **Description** | BLE peripheral test commands |
| **Test Result** | 使用iphone LightBlue app抓取到的畫面。<br>Iphone app url path:<br>https://apps.apple.com/tw/app/lightblue/id557428110<br>Google app url path:<br>https://play.google.com/store/apps/details?id=com.punchthrough.lightblueexplorer&hl=zh_TW |

### 2.1.18 WiFi TEST

|  |  |
| --- | --- |
| **Command** | **wifi_scan**<br>**wifi_sta_connect**<br>**wifi_sta_info**<br>**wifi_sta_rssi**<br>**set_ipv4**<br>**ping**<br>**iperf**<br>**wifi_sta_info**<br>**wifi_sta_rssi** |
| **Description** | WiFi test commands. |
| **Test Result** | (empty) |

### 2.1.19 Check Version

|  |  |
| --- | --- |
| **Command** | **qcc74x />mm_version**<br>**1.5.0-295**<br>**Verify the shopfloor software version is 1.5.0-295** |
| **Description** | Check the software version |
| **Test Result** | (empty) |

### 2.1.20 MAC/SN/MODEL/HWVER WRITE

| **Command** | **factory w** |
| --- | --- |
| **Description** | Write MAC,SN, MODEL,HWVER |
| **Syntax** | usage: factory w \<MAC> \<SN> \<MODEL> \<HWVER> |
| **Test Result** | qcc74x />factory w 02:00:0a:0b:0c:ff ECSN11225678 Pi7 R0C<br>erase flash 0x7f8000<br>Pi7 Factory info:<br>halow_mac: 02:00:0A:0B:0C:FF<br>wifi_mac: 02:00:0A:0B:0D:00<br>ble_mac: 02:00:0A:0B:0D:01<br>S/N : ECSN11225678<br>Model: Pi7<br>HWver: R0C |

### 2.1.21 MAC/SN/MODEL/HWVER READ

| **Command** | **factory r** |
| --- | --- |
| **Description** | Read MAC,SN, MODEL,HWVER |
| **Syntax** | usage: factory r |
| **Test Result** | qcc74x />factory r<br>Pi7 Factory info:<br>halow_mac: 00:11:22:33:44:55<br>wifi_mac: 00:11:22:33:44:66<br>ble_mac: 00:11:22:33:44:77<br>S/N : ECSN012345678<br>Model: Pi7a<br>HWver: R0B |
