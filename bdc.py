import os
import pathlib
import asyncio

from bscscan import BscScan

from coinmarketcapapi import CoinMarketCapAPI, CoinMarketCapAPIError

from datetime import datetime

import discord

from dotenv import load_dotenv

load_dotenv()

BABY_DOGE_COIN_TOKEN = "0xc748673057861a797275cd8a068abb95a902e8de"
BABY_DOGE_COIN_BURN_ADDRESS = "0x000000000000000000000000000000000000dead"
BABY_DOGE_COIN_ID = 10407
BABY_DOGE_COIN_SYMBOL = "BabyDoge"
BABY_DOGE_COIN_DECIMALS = 1000000000

class BabyDogeCoinBot(discord.Client):
    def __init__(self):
        # intents to send messages to users
        intents = discord.Intents.default()
        intents.members = True
        intents.reactions = True
        super().__init__(intents=intents)
        self.initialized = False
        self.loop.create_task(self.update_pricing_info_task())

    async def on_ready(self):
        if self.initialized:
            return

        print(f"{self.user.name} has connected to {self.guilds}!")
    
        self.bsc_key = os.getenv("BSC_SCAN_API_KEY")
        self.cmc_key = os.getenv("COIN_MARKET_CAP_API_KEY")
        self.cmc = CoinMarketCapAPI(self.cmc_key)

        self.initialized = True

    async def update_pricing_info_task(self):
        await self.wait_until_ready()

        while not hasattr(self, 'cmc'):
            await asyncio.sleep(1)

        while not self.is_closed():
            self.pricing_info = await self.update_pricing_info()
            await asyncio.sleep(30)

    async def on_message(self, message):
        if message.author == client.user:
            return

        msg = message.content.lower()
        if msg.startswith("$"):
            response = await self.handle_command(msg, message)
            if response is not None:
                await message.channel.send(f"{response}")
            return

    async def handle_command(self, msg, full_message):
        response = None

        if msg.startswith("$babydogecoin help"):
            response = self.handle_help()
        elif msg.startswith("$babydogecoin price"):
            response = self.pricing_info

        return response

    def handle_help(self):
        response = f"Baby Doge Coin Bot (Version: {get_version()})"

        response += "\n$babydogecoin price - Returns the current pricing information"

        return response

    async def update_pricing_info(self):
        try:
            cmc_data = self.cmc.cryptocurrency_quotes_latest(id=BABY_DOGE_COIN_ID).data
            baby_doge_coin_quota = cmc_data[str(BABY_DOGE_COIN_ID)]
            supply = baby_doge_coin_quota["total_supply"]
            usd_quota = baby_doge_coin_quota["quote"]["USD"]
            price = usd_quota["price"]
            market_cap = supply * price
            last_updated = baby_doge_coin_quota["last_updated"]

            async with BscScan(self.bsc_key) as bsc:
                burn_raw = float(await bsc.get_acc_balance_by_token_contract_address(contract_address=BABY_DOGE_COIN_TOKEN, address=BABY_DOGE_COIN_BURN_ADDRESS))
                burn = float(burn_raw) / BABY_DOGE_COIN_DECIMALS
                burn_percentage = burn / supply
                burn_value = burn * price
                market_cap_after_burn = market_cap - burn_value

            response = f"1 {BABY_DOGE_COIN_SYMBOL} = {'{:0,.12f}'.format(price)} USD"
            
            intervals = ""
            values = ""
            for key in usd_quota:
                if key.startswith("percent_change_") and usd_quota[key] != 0:
                    interval = key.replace("percent_change_", "")
                    value = usd_quota[key]

                    interval_str = f"{interval}"
                    if value > 0:
                        value_length = len(f"{'{:0,.2f}'.format(value)}%") + 12 + 3
                        value_str = f":arrow_up: {'{:0,.2f}'.format(value)}%   "
                    elif value < 0:
                        value_length = len(f"{'{:0,.2f}'.format(value)}%") + 12 + 3
                        value_str = f":arrow_down: {'{:0,.2f}'.format(value)}%   "
                    else:
                        value_length = len(f"{value}") + 1 + 3
                        value_str = f"{value}   "

                    at_end = True
                    while len(value_str) < len(interval_str):
                        value_str += " "

                    while len(interval_str) < value_length:
                        if at_end:
                            interval_str += " "
                        else:
                            interval_str = " " + interval_str
                        at_end = not at_end

                    intervals += interval_str
                    values += value_str

            if (len(intervals) > 0 and len(values) > 0):   
                response += f"\n"
                response += f"\n:rocket: Price changes :rocket:"
                response += f"\n{intervals}"
                response += f"\n{values}"

            response += f"\n"
            response += f"\n:moneybag:MarketCap: ${'{:0,.2f}'.format(market_cap_after_burn)} :moneybag:"
            response += f"\n"
            response += f"\n:fire:Burned: {'{:0,.2f}'.format(burn)} | {'{:0,.2f}'.format(burn_percentage * 100)}% :fire:"
            response += f"\n"
            response += f"\n*data last updated at: {last_updated}"

            return response
        except Exception as ex:
            print (ex)
            return "Something went wrong. Please try again later."

def get_version():
    fname = pathlib.Path(__file__)
    if fname.exists():
        mtime = datetime.fromtimestamp(fname.stat().st_mtime)
        return mtime.strftime("%Y-%m-%d %H:%M")
    else:
        return "?"

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    client = BabyDogeCoinBot()
    client.run(token)
