import os
import time
import subprocess
from pythonrunner.worker import Worker

class PingMonitor(Worker):
    def __init__(self, config=None):
        super().__init__(config)
        self.config = config.get("ping_monitor", {})
        self.interval = self.config.get("interval", 60)
        self.ips = self.config.get("ips", [])
        self.webhook = self.config.get("webhook")
        self.username = self.config.get("username")
        self.avatar_url = self.config.get("avatar_url")

        self.down_ips = set()

    def ping_ip(self, ip):
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return result.returncode == 0
        except Exception as e:
            self.error(f"Exception while pinging {ip}: {e}")
            return False

    def run(self):
        while True:
            for ip in self.ips:
                is_up = self.ping_ip(ip)

                if not is_up and ip not in self.down_ips:
                    self.debug(f"IP {ip} is down! Sending notification.")
                    self.down_ips.add(ip)
                    if self.webhook:
                        data = {
                            "username": self.username,
                            "avatar_url": self.avatar_url,
                            "embeds": [
                                {
                                    "title": f"Ping alert for {ip}",
                                    "description": f"The IP {ip} is not reachable.",
                                    "color": 0xFF0000,
                                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                                }
                            ],
                        }
                        self.http_post(self.webhook, data)
                elif is_up and ip in self.down_ips:
                    self.debug(f"IP {ip} is back up.")
                    self.down_ips.remove(ip)
                    if self.webhook:
                        data = {
                            "username": self.username,
                            "avatar_url": self.avatar_url,
                            "embeds": [
                                {
                                    "title": f"Ping alert resolved for {ip}",
                                    "description": f"The IP {ip} is now reachable again.",
                                    "color": 0x00FF00,
                                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                                }
                            ],
                        }
                        self.http_post(self.webhook, data)

            time.sleep(self.interval)
