import threading
import time
import requests
import ssl
import socket
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timezone
import urllib3
from urllib.parse import urlparse

from pythonrunner.worker import Worker

class SSLMonitor(Worker):
    def __init__(self, config=None):
        super().__init__(config)
        self.config = config.get("ssl_monitor", {})
        self.urls = self.config.get("urls", [])
        self.webhook = self.config.get("webhook")
        self.interval = self.config.get("interval", 60)
        self.username = self.config.get("username")
        self.avatar_url = self.config.get("avatar_url")
        self.expiry_threshold = self.config.get("cert_expiry_threshold", 10)
        self.allow_self_signed = self.config.get("allow_self_signed", False)

    def get_cert_expiry(self, url):
        if not url.startswith("https"):
            return None, None

        try:
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname
            port = parsed_url.port or 443

            context = ssl.create_default_context()
            if self.allow_self_signed:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE

            with socket.create_connection((hostname, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    der_cert = ssock.getpeercert(binary_form=True)
                    pem_cert = ssl.DER_cert_to_PEM_cert(der_cert)

                    cert = x509.load_pem_x509_certificate(pem_cert.encode(), default_backend())
                    expiry_date = cert.not_valid_after_utc

                    now = datetime.now(timezone.utc)
                    days_left = (expiry_date - now).days
                    return expiry_date.strftime("%Y-%m-%d"), days_left
        except Exception as e:
            self.error(f"get_cert_expiry failed for {url}: {e}")
            return None, None

    def monitor_all(self):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        while True:
            embeds = []

            for url in self.urls:
                try:
                    self.debug(f"Pinging {url}")
                    start = time.time()
                    response = requests.get(url, timeout=10, verify=not self.allow_self_signed)
                    duration = time.time() - start
                    status = response.status_code
                    expiry, days_left = self.get_cert_expiry(url)

                    self.debug(f"{url} | Status: {status}, Time: {duration:.2f}s, Expiry: {expiry}, Days Left: {days_left}")

                    if status != 200 or (days_left is not None and days_left < self.expiry_threshold):
                        embed = {
                            "title": url,
                            "color": 0xff0000 if days_left is not None and days_left < 5 else 0xffa500,
                            "fields": [
                                {"name": "Status", "value": f"`{status}`", "inline": True},
                                {"name": "Response Time", "value": f"`{duration:.2f}s`", "inline": True},
                                {"name": "SSL Expiry", "value": f"`{expiry}`", "inline": True},
                                {"name": "Days Left", "value": f"`{days_left} days`", "inline": True},
                            ],
                        }
                        embeds.append(embed)

                except Exception as e:
                    self.error(f"Error pinging {url}: {e}")
                    embed = {
                        "title": url,
                        "color": 0xff0000,
                        "description": f"Error: `{e}`"
                    }
                    embeds.append(embed)

            if embeds:
                payload = {
                    "username": self.username,
                    "avatar_url": self.avatar_url,
                    "embeds": embeds,
                }
                self.http_post(self.webhook, payload)

            time.sleep(self.interval)

    def run(self):
        thread = threading.Thread(target=self.monitor_all, daemon=True)
        thread.start()
