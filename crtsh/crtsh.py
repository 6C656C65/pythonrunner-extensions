import threading
import asyncio
import discord
from discord.ext import commands
import aiohttp
from pythonrunner.worker import Worker

class Crtsh(Worker):
    def __init__(self, config=None):
        super().__init__(config)
        self.config = config.get("crtsh", {})
        self.token = self.config.get("discord_token")
        self.prefix = self.config.get("discord_prefix", "!")

        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix=self.prefix, intents=intents)

        @self.bot.command()
        async def crtsh(ctx, domain: str):
            url = f"https://crt.sh/?q={domain}&output=json"
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(url) as response:
                        if response.status != 200:
                            await ctx.send(f"Error retrieving data for {domain}.")
                            return
                        data = await response.json()
                        if not data:
                            await ctx.send(f"No certificate found for {domain}.")
                            return

                        message = f"📜 Certificates for **{domain}** :\n"
                        for cert in data[:5]:
                            message += f"- Issuer CA ID: {cert.get('issuer_ca_id')} - Issuer Name: {cert.get('issuer_name')} - CN: {cert.get('common_name')} - From: {cert.get('not_before')} - To: {cert.get('not_after')}\n"

                        await ctx.send(message)
                except Exception as e:
                    await ctx.send(f"An error has occurred : {e}")

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
