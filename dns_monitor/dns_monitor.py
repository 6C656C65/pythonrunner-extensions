import socket
import time
import yaml
import os

from pythonrunner.worker import Worker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, ".dns_cache.yaml")

class DNSMonitor(Worker):
    def __init__(self, config=None):
        super().__init__(config)
        self.config = config.get("dns_monitor", {})
        self.interval = self.config.get("interval", 300)
        self.domains = self.config.get("domains", [])
        self.webhook = self.config.get("webhook")
        self.username = self.config.get("username")
        self.avatar_url = self.config.get("avatar_url")
        self.cache_file = CACHE_FILE

    def run(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r") as f:
                cache = yaml.safe_load(f) or {}
        else:
            cache = {}

        while True:
            for domain in self.domains:
                try:
                    current_ip = socket.gethostbyname(domain)
                except Exception as e:
                    self.error(f"DNS resolution error for {domain}: {e}")
                    continue

                old_ip = cache.get(domain)
                if old_ip != current_ip:
                    self.debug(f"IP change detected for {domain} : {old_ip} -> {current_ip}")
                    cache[domain] = current_ip

                    if self.webhook:
                        data = {
                            "username": self.username,
                            "avatar_url": self.avatar_url,
                            "embeds": [
                                {
                                    "title": f"IP Change detected for {domain}",
                                    "color": 0x00FF00,
                                    "fields": [
                                        {"name": "Old IP", "value": old_ip or "N/A", "inline": True},
                                        {"name": "New IP", "value": current_ip, "inline": True},
                                    ],
                                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                                }
                            ],
                        }
                        self.http_post(self.webhook, data)

            with open(self.cache_file, "w") as f:
                yaml.safe_dump(cache, f)

            time.sleep(self.interval)
