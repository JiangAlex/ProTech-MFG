"""
EAP111-TP-002

Headline:
    Ethernet Throughput Test via SSH (eth1 → eth0)

Purpose:
    Verify EAP111 LAN-to-LAN forwarding throughput via iperf3.
    SSH to PC to run iperf3 server/client on separate interfaces.

Topology:
    PC eth1 (192.168.1.2) ── AP eth0 ── AP eth1 ── PC eth2 (192.168.2.2)
"""

import json
import time
import subprocess

from mfg.manufacturing_script import ManufacturingScript


class TestCase(ManufacturingScript):
    tc_id = "EAP111-TP-002"
    station = "FDL"
    headline = "Ethernet Throughput Test via SSH (eth1 → eth0)"
    purpose = "Verify LAN-to-LAN forwarding throughput >= 900 Mbps via SSH + iperf3."

    MIN_MBPS = 900
    DURATION = 10

    def run(self):
        pc = self.config["pc"]
        pc_ip = pc["ip"]
        pc_user = pc.get("user", "root")
        eth1_ip = pc["ports"]["eth1"]["ip"]
        eth2_ip = pc["ports"]["eth2"]["ip"]
        iperf_port = pc["iperf"]["server_port"]

        try:
            self.step(1, f"Start iperf3 server on PC eth1 ({eth1_ip}) via SSH")
            self._pc_ssh(pc_ip, pc_user,
                         f"iperf3 -s -p {iperf_port} -1 -D")
            time.sleep(1)

            self.step(2, f"Run iperf3 client from PC eth2 → {eth1_ip} ({self.DURATION}s)")
            out = self._pc_ssh(pc_ip, pc_user,
                               f"iperf3 -c {eth1_ip} -p {iperf_port} "
                               f"-t {self.DURATION} -B {eth2_ip} -J",
                               timeout=self.DURATION + 10)

            self.step(3, "Parse results")
            data = json.loads(out)
            bps = data["end"]["sum_received"]["bits_per_second"]
            mbps = bps / 1_000_000
            self.message(f"Throughput: {mbps:.1f} Mbps")

            self.step(4, f"Verify throughput >= {self.MIN_MBPS} Mbps")
            assert mbps >= self.MIN_MBPS, \
                f"Throughput {mbps:.1f} Mbps < {self.MIN_MBPS} Mbps"

            self.message(f"PASS — {mbps:.1f} Mbps >= {self.MIN_MBPS} Mbps")

        finally:
            self.cleanup()

    def _pc_ssh(self, ip, user, cmd, timeout=15):
        """SSH to PC and execute command."""
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no",
             "-o", "UserKnownHostsFile=/dev/null",
             f"{user}@{ip}", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
