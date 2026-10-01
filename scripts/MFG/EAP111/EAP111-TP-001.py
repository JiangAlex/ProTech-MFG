"""
EAP111-TP-001

Headline:
    Ethernet Throughput Test (eth1 → eth0)

Purpose:
    Verify EAP111 LAN-to-LAN forwarding throughput via iperf3.
    PC eth2 sends traffic to PC eth1 through AP (eth1 → eth0).

Topology:
    PC eth1 (192.168.1.2) ── AP eth0 ── AP eth1 ── PC eth2 (192.168.2.2)
"""

import subprocess
import json
import time

from mfg.manufacturing_script import ManufacturingScript


class TestCase(ManufacturingScript):
    tc_id = "EAP111-TP-001"
    station = "FDL"
    headline = "Ethernet Throughput Test (eth1 → eth0)"
    purpose = "Verify LAN-to-LAN forwarding throughput >= 900 Mbps via iperf3."

    MIN_MBPS = 900
    DURATION = 10

    def run(self):
        pc = self.config["pc"]
        eth1_ip = pc["ports"]["eth1"]["ip"]
        eth2_ip = pc["ports"]["eth2"]["ip"]
        iperf_port = pc["iperf"]["server_port"]

        # Initialize so the finally block never hits a NameError (which would
        # mask the real failure, e.g. iperf3 missing or IP not configured).
        server = None
        try:
            self.step(1, f"Start iperf3 server on PC eth1 ({eth1_ip})")
            try:
                server = subprocess.Popen(
                    ["iperf3", "-s", "-p", str(iperf_port), "-1"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except FileNotFoundError:
                raise RuntimeError(
                    "iperf3 not found — install it on the test PC "
                    "(e.g. `sudo apt-get install -y iperf3`)."
                )
            time.sleep(1)

            self.step(2, f"Run iperf3 client from PC eth2 → {eth1_ip} ({self.DURATION}s)")
            result = subprocess.run(
                ["iperf3", "-c", eth1_ip, "-p", str(iperf_port),
                 "-t", str(self.DURATION), "-B", eth2_ip, "-J"],
                capture_output=True, text=True, timeout=self.DURATION + 10
            )
            server.wait(timeout=5)

            self.step(3, "Parse results")
            data = json.loads(result.stdout)
            bps = data["end"]["sum_received"]["bits_per_second"]
            mbps = bps / 1_000_000
            self.message(f"Throughput: {mbps:.1f} Mbps")

            self.step(4, f"Verify throughput >= {self.MIN_MBPS} Mbps")
            assert mbps >= self.MIN_MBPS, \
                f"Throughput {mbps:.1f} Mbps < {self.MIN_MBPS} Mbps"

            self.message(f"PASS — {mbps:.1f} Mbps >= {self.MIN_MBPS} Mbps")

        finally:
            if server is not None:
                server.terminate()
            self.cleanup()
