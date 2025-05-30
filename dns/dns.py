import threading
import asyncio
import discord
from discord.ext import commands
import socket
from pythonrunner.worker import Worker

class DomainName(Worker):
    def __init__(self, config=None):
        super().__init__(config)
        self.config = config.get("dns", {})
        self.token = self.config.get("discord_token")
        self.prefix = self.config.get("discord_prefix", "!")

        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix=self.prefix, intents=intents)

        @self.bot.command()
        async def resolve(ctx, domain: str):
            try:
                ips = socket.gethostbyname_ex(domain)[2]
                if not ips:
                    await ctx.send(f"No IP found for {domain}.")
                else:
                    await ctx.send(f"IPs for **{domain}**:\n" + "\n".join(ips))
            except Exception as e:
                await ctx.send(f"Error resolving {domain}: {e}")

        @self.bot.command()
        async def reverse(ctx, ip: str):
            try:
                hostname = socket.gethostbyaddr(ip)[0]
                await ctx.send(f"Reverse DNS for **{ip}**:\n{hostname}")
            except Exception as e:
                await ctx.send(f"Error resolving reverse DNS for {ip}: {e}")

        @self.bot.event
        async def on_ready():
            self.debug(f"Bot connected as {self.bot.user}")

    def run(self):
        def start_bot():
            try:
                asyncio.run(self.bot.start(self.token))
            except Exception as e:
                self.error(f"Bot crashed: {e}")

        thread = threading.Thread(target=start_bot, daemon=True)
        thread.start()

    async def stop_bot(self):
        await self.bot.close()

    def stop(self):
        asyncio.run(self.stop_bot())
