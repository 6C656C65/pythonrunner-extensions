import threading
import asyncio
import requests
import discord
import json
from discord.ext import commands

from pythonrunner.worker import Worker

class RootMe(Worker):
    def __init__(self, config=None):
        super().__init__(config)
        self.config = config.get("rootme", {})
        self.api_key = self.config.get("api_key")
        self.users_uid = self.config.get("users_uid", [])
        self.token = self.config.get("discord_token")
        self.prefix = self.config.get("discord_prefix", "!")
        self.challs_file = "./rootme/challs.json"
        self.rubriques = self.config.get("rubriques", [])

        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix=self.prefix, intents=intents)

        @self.bot.command()
        async def rank(ctx):
            try:
                user_data_list = []

                for user in self.users_uid:
                    data = self.get_user(user['uid'])
                    data['pseudo'] = user['pseudo']
                    user_data_list.append(data)

                sorted_users = sorted(user_data_list, key=lambda u: u.get("position", float("inf")))

                embed = discord.Embed(
                    title="🏆 User Rankings",
                    color=discord.Color.gold()
                )

                for user in sorted_users:
                    name = user.get("pseudo", "Unknown")
                    position = user.get("position", "N/A")
                    score = user.get("score", "N/A")
                    embed.add_field(
                        name=f"{name}",
                        value=f"Position: #{position}\nScore: {score}",
                        inline=False
                    )

                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"Unexpected error while retrieving rankings: {e}")

        @self.bot.command()
        async def getuser(ctx, pseudo: str = None):
            if pseudo is None:
                await ctx.send("Usage: `!getuser <username>` - Please provide a username.")
                return

            try:
                user = next((u for u in self.users_uid if u["pseudo"].lower() == pseudo.lower()), None)
                if user:
                    data = self.get_user(user['uid'])

                    embed = discord.Embed(
                        title=f"User: {user['pseudo']}",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="UID", value=user['uid'], inline=True)
                    embed.add_field(name="Score", value=data.get('score', 'N/A'), inline=True)
                    embed.add_field(name="Position", value=data.get('position', 'N/A'), inline=True)

                    validations = data.get('validations', [])
                    validation_list = validations[:5]
                    if validation_list:
                        embed.add_field(
                            name="Recent Validations",
                            value="\n".join(f"- {v['titre']}" for v in validation_list),
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="Recent Validations",
                            value="No validations found.",
                            inline=False
                        )

                    embed.add_field(
                        name="Total Validations",
                        value=str(len(validations)),
                        inline=True
                    )

                    await ctx.send(embed=embed)

                else:
                    await ctx.send(f"No user found with the username: {pseudo}")
            except Exception as e:
                await ctx.send(f"Error while searching: {e}")

        @self.bot.command()
        async def check(ctx, pseudo: str = None, *, challenge: str = None):
            if pseudo is None:
                await ctx.send("Usage: `!check <username> <challenge>` - Please provide a username.")
                return
            if challenge is None:
                await ctx.send("Usage: `!check <username> <challenge>` - Please provide a challenge.")
                return

            try:
                user = next((u for u in self.users_uid if u["pseudo"].lower() == pseudo.lower()), None)
                if user:
                    challenge_data = self.get_chall_by_title(challenge)
                    if challenge_data:
                        user_data = self.get_user(user['uid'])
                        validations = user_data.get('validations', [])
                        if any(v['id_challenge'] == challenge_data['id_challenge'] for v in validations):
                            await ctx.send(f"{pseudo} has completed the challenge {challenge}")
                        else:
                            await ctx.send(f"{pseudo} did not complete the challenge {challenge}")
                    else:
                        await ctx.send(f"No challenge found with the title: {challenge}")
                else:
                    await ctx.send(f"No user found with the username: {pseudo}")
            except Exception as e:
                await ctx.send(f"Error while searching: {e}")

        @self.bot.command()
        async def todo(ctx, pseudo: str = None, category: str = None):
            if pseudo is None:
                await ctx.send("Usage: `!todo <username> <category>` - Please provide a username.")
                return
            if category is None:
                await ctx.send("Usage: `!todo <username> <category>` - Please provide a category (!getcat).")
                return

            try:
                user = next((u for u in self.users_uid if u["pseudo"].lower() == pseudo.lower()), None)
                if user:
                    user_data = self.get_user(user['uid'])
                    category_list = self.get_chall_by_rubrique(category)
                    if category_list and user_data:
                        validations = user_data.get('validations', [])
                        validated_ids = {v['id_challenge'] for v in validations}
                        remaining_challs = [c for c in category_list if c['id_challenge'] not in validated_ids]

                        if remaining_challs:
                            msg = f"Challenges not yet completed by {pseudo} in category {category}:\n"
                            for c in remaining_challs:
                                msg += f"- {c['titre']}\n"
                            await ctx.send(msg[:2000])
                        else:
                            await ctx.send(f"{pseudo} has completed all challenges in category {category}!")
                    else:
                        await ctx.send(f"No category found with this id : {category}")
                else:
                    await ctx.send(f"No user found with the username: {pseudo}")
            except Exception as e:
                await ctx.send(f"Error while searching: {e}")

        @self.bot.command()
        async def getcat(ctx):
            msg = "List of categories:"
            for rubrique in self.rubriques:
                msg += f"\n{rubrique['label']} = {rubrique['id']}"
            await ctx.send(msg)

        @self.bot.event
        async def on_ready():
            self.debug(f"Bot connected as {self.bot.user}")

    def get_user(self, uid):
        r = requests.get("https://api.www.root-me.org/auteurs/" + str(uid), cookies={"api_key": self.api_key})
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            raise Exception("Too many API requests. Please try again later.")
        else:
            self.error(f"Error fetching data {r.status_code}")
            return

    def get_chall_by_title(self, title):
        with open(self.challs_file, 'r', encoding='utf-8') as f:
            challs = json.load(f)
        for chall in challs:
            if chall.get('titre') == title:
                return chall
        return None

    def get_chall_by_rubrique(self, id_rubrique):
        with open(self.challs_file, 'r', encoding='utf-8') as f:
            challs = json.load(f)
        return [chall for chall in challs if chall.get('id_rubrique') == id_rubrique]

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

