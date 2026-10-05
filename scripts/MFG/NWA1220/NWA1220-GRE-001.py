"""
NWA1220-GRE-001

Model / SKU / Station:
    NWA1220 (IPQ5332 + RTL8251B-CG) / WW / FDL

Headline:
    GRE packet-size / fragmentation CPU test (baseline vs jumbo)

Purpose:
    Reproduce the [SPF12.5 CSU1] GRE packet size issue (Accton #77) and verify
    the jumbo frame fix. Builds a symmetric GRE tunnel between the Test PC and
    the DUT, confirms the MTU fragmentation threshold, drives iperf3 UDP load
    through the tunnel, and checks that enabling jumbo frame (underlay 9018 /
    tunnel 8994) restores throughput collapsed by single-core fragment
    reassembly.

Background (see ~/GRE-Test/reports/2026-10-05_5G_CPU100_repro.md):
    - GRE overhead = 24 B -> tunnel MTU = underlay MTU - 24.
    - Baseline (underlay 1500 / tunnel 1476): payload > 1448 B must fragment;
      DUT fragment reassembly softirq concentrates on a single core (cpu0),
      saturating it; throughput attainment collapses (~1.6% measured at 5G).
    - Jumbo (underlay 9018 / tunnel 8994): large packets no longer fragment;
      load spreads across cores; throughput attainment ~99%.
    - "Attainment" = receiver bits/s ÷ sender bits/s (loss rate is misleading
      because the fragmented case barely sends any packets at all).

Topology (IPs read from testbed; GRE endpoints = underlay IPs):
    PC eno2 (pc.ip) <== 5G underlay ==> DUT eth0 (ap.ssh.ip)
    PC gre1 (10.0.0.1) ====== GRE tunnel ====== DUT gre1 (10.0.0.2)

Prerequisites:
    - DUT reachable via SSH (ap.ssh.ip), has iperf3, is Linux/OpenWrt.
    - Test PC reachable via SSH (pc.ip / pc.user), has iperf3 and `ip`.
    - PC-side GRE/MTU changes need root: set testbed pc.sudo to "sudo"
      (NOPASSWD required for unattended runs) or "" if the SSH user is root.
    - All `ip` settings are temporary (lost on reboot).
"""

import json
import time
import subprocess

from mfg.manufacturing_script import ManufacturingScript


class TestCase(ManufacturingScript):
    tc_id = "NWA1220-GRE-001"
    station = "FDL"
    model = "NWA1220"
    headline = "GRE packet-size / fragmentation CPU test (baseline vs jumbo)"
    purpose = "Reproduce GRE fragmentation single-core bottleneck and verify jumbo fix."

    # --- GRE / MTU plan ---
    GRE_OVERHEAD = 24          # outer IP 20 + GRE header 4
    STD_UNDERLAY_MTU = 1500    # baseline (reproduce issue)
    JUMBO_UNDERLAY_MTU = 9018  # fix (jumbo frame)
    GRE_IFACE = "gre1"
    PC_GRE_IP = "10.0.0.1"
    DUT_GRE_IP = "10.0.0.2"
    GRE_PREFIX = 24
    GRE_TTL = 255

    # --- Load / pass criteria ---
    IPERF_LEN = 4000           # UDP datagram > tunnel MTU -> forces fragmentation at baseline
    IPERF_BW = "400M"
    IPERF_PARALLEL = 4
    IPERF_TIME = 6
    MIN_JUMBO_ATTAINMENT = 0.80     # jumbo receiver/sender ratio must be >= 80%
    MAX_BASELINE_ATTAINMENT = 0.30  # baseline is expected to collapse (< 30%)

    def tunnel_mtu(self, underlay_mtu):
        return underlay_mtu - self.GRE_OVERHEAD

    def run(self):
        pc = self.config["pc"]
        pc_ip = pc["ip"]
        pc_user = pc.get("user", "root")
        self._pc_sudo = pc.get("sudo", "sudo")  # "" if SSH user is root
        dut_ip = self.config["ap"]["ssh"]["ip"]
        pc_underlay_ip = pc_ip

        try:
            self.step(1, "Create symmetric GRE tunnel (DUT + PC)")
            self._setup_tunnel(pc_ip, pc_user, pc_underlay_ip, dut_ip,
                               self.tunnel_mtu(self.STD_UNDERLAY_MTU))

            self.step(2, "Verify GRE connectivity (small ping)")
            out = self._pc_ssh(pc_ip, pc_user,
                               f"ping -c 3 -s 64 -W 1 {self.DUT_GRE_IP}")
            assert "0% packet loss" in out or " 0%" in out, \
                f"GRE tunnel not reachable:\n{out}"
            self.message("GRE tunnel up (0% loss)")

            self.step(3, "Confirm MTU fragmentation threshold (baseline tunnel 1476)")
            ok1448 = self._pc_ssh(pc_ip, pc_user,
                                  f"ping -M do -c 2 -W 1 -s 1448 {self.DUT_GRE_IP}; echo RC=$?")
            fail1449 = self._pc_ssh(pc_ip, pc_user,
                                    f"ping -M do -c 2 -W 1 -s 1449 {self.DUT_GRE_IP}; echo RC=$?")
            self.message(f"DF ping 1448 -> {'pass' if 'RC=0' in ok1448 else 'fail'}; "
                         f"1449 -> {'pass' if 'RC=0' in fail1449 else 'fail (expected)'}")

            self.step(4, "Baseline load (fragmentation): measure throughput attainment")
            base = self._run_load(pc_ip, pc_user)
            self.message(f"Baseline: sender {base['sender_mbps']:.0f} Mbps / "
                         f"receiver {base['recv_mbps']:.0f} Mbps / "
                         f"attainment {base['attainment']*100:.1f}%")

            self.step(5, "Apply jumbo frame (underlay 9018 / tunnel 8994)")
            self._apply_jumbo(pc_ip, pc_user)

            self.step(6, "Verify large packet no longer fragments (DF 8000)")
            jping = self._pc_ssh(pc_ip, pc_user,
                                 f"ping -M do -c 2 -W 1 -s 8000 {self.DUT_GRE_IP}; echo RC=$?")
            assert "RC=0" in jping, f"Jumbo path failed large DF ping:\n{jping}"
            self.message("Jumbo path OK (DF 8000 passes, no fragmentation)")

            self.step(7, "Jumbo load: measure throughput attainment")
            jumbo = self._run_load(pc_ip, pc_user)
            self.message(f"Jumbo: sender {jumbo['sender_mbps']:.0f} Mbps / "
                         f"receiver {jumbo['recv_mbps']:.0f} Mbps / "
                         f"attainment {jumbo['attainment']*100:.1f}%")

            self.step(8, "Verify jumbo fixes the fragmentation bottleneck")
            assert base["attainment"] <= self.MAX_BASELINE_ATTAINMENT, (
                f"Baseline attainment {base['attainment']*100:.1f}% unexpectedly high "
                f"(expected <= {self.MAX_BASELINE_ATTAINMENT*100:.0f}%); "
                f"fragmentation issue not reproduced")
            assert jumbo["attainment"] >= self.MIN_JUMBO_ATTAINMENT, (
                f"Jumbo attainment {jumbo['attainment']*100:.1f}% < "
                f"{self.MIN_JUMBO_ATTAINMENT*100:.0f}%; jumbo fix did not restore throughput")

            self.message(
                f"PASS — jumbo fixes GRE fragmentation bottleneck "
                f"(baseline {base['attainment']*100:.1f}% -> jumbo {jumbo['attainment']*100:.1f}%)")

        finally:
            self._teardown(pc_ip, pc_user)
            self.cleanup()

    # ------------------------------------------------------------------ helpers

    def _setup_tunnel(self, pc_ip, pc_user, pc_underlay_ip, dut_ip, tun_mtu):
        s = self._pc_sudo + (" " if self._pc_sudo else "")
        # DUT side (base-class SSH to ap.ssh.ip, already root)
        self.ssh_cmd(
            f"ip link del {self.GRE_IFACE} 2>/dev/null; "
            f"ip tunnel add {self.GRE_IFACE} mode gre local {dut_ip} "
            f"remote {pc_underlay_ip} ttl {self.GRE_TTL}; "
            f"ip addr add {self.DUT_GRE_IP}/{self.GRE_PREFIX} dev {self.GRE_IFACE}; "
            f"ip link set {self.GRE_IFACE} up",
            timeout=15,
        )
        # PC side (needs root)
        self._pc_ssh(pc_ip, pc_user,
                     f"{s}ip link del {self.GRE_IFACE} 2>/dev/null; "
                     f"{s}ip tunnel add {self.GRE_IFACE} mode gre local {pc_underlay_ip} "
                     f"remote {dut_ip} ttl {self.GRE_TTL}; "
                     f"{s}ip addr add {self.PC_GRE_IP}/{self.GRE_PREFIX} dev {self.GRE_IFACE}; "
                     f"{s}ip link set {self.GRE_IFACE} mtu {tun_mtu} up")
        time.sleep(1)

    def _apply_jumbo(self, pc_ip, pc_user):
        s = self._pc_sudo + (" " if self._pc_sudo else "")
        jumbo_tun = self.tunnel_mtu(self.JUMBO_UNDERLAY_MTU)
        dut_iface = self.config["ap"].get("gre_underlay_iface", "eth0")
        dut_bridge = self.config["ap"].get("gre_bridge", "br-lan")
        pc_iface = self.config["pc"].get("gre_underlay_iface", "eno2")
        self.ssh_cmd(
            f"ip link set {dut_iface} mtu {self.JUMBO_UNDERLAY_MTU}; "
            f"ip link set {dut_bridge} mtu {self.JUMBO_UNDERLAY_MTU}; "
            f"ip link set {self.GRE_IFACE} mtu {jumbo_tun}",
            timeout=15,
        )
        self._pc_ssh(pc_ip, pc_user,
                     f"{s}ip link set {pc_iface} mtu {self.JUMBO_UNDERLAY_MTU}; "
                     f"{s}ip link set {self.GRE_IFACE} mtu {jumbo_tun}")
        time.sleep(1)

    def _run_load(self, pc_ip, pc_user):
        self.ssh_cmd(
            f"killall iperf3 2>/dev/null; sleep 1; "
            f"setsid iperf3 -s -B {self.DUT_GRE_IP} >/tmp/iperf3_srv.log 2>&1 </dev/null &",
            timeout=10,
        )
        time.sleep(1)
        out = self._pc_ssh(
            pc_ip, pc_user,
            f"iperf3 -c {self.DUT_GRE_IP} -B {self.PC_GRE_IP} -u "
            f"-l {self.IPERF_LEN} -b {self.IPERF_BW} -P {self.IPERF_PARALLEL} "
            f"-t {self.IPERF_TIME} -J",
            timeout=self.IPERF_TIME + 15,
        )
        data = json.loads(out)
        sender_bps = data["end"]["sum"]["bits_per_second"]
        recv = data["end"].get("sum_received") or data["end"]["sum"]
        recv_bps = recv["bits_per_second"]
        attainment = (recv_bps / sender_bps) if sender_bps > 0 else 0.0
        return {"sender_mbps": sender_bps / 1_000_000,
                "recv_mbps": recv_bps / 1_000_000,
                "attainment": attainment}

    def _teardown(self, pc_ip, pc_user):
        s = self._pc_sudo + (" " if self._pc_sudo else "")
        try:
            self.ssh_cmd(f"killall iperf3 2>/dev/null; "
                         f"ip link del {self.GRE_IFACE} 2>/dev/null", timeout=10)
        except Exception:
            pass
        try:
            self._pc_ssh(pc_ip, pc_user, f"{s}ip link del {self.GRE_IFACE} 2>/dev/null")
        except Exception:
            pass

    def _pc_ssh(self, ip, user, cmd, timeout=15):
        """SSH to the Test PC and execute a command (mirrors EAP111-TP-002)."""
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no",
             "-o", "UserKnownHostsFile=/dev/null",
             f"{user}@{ip}", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip()
