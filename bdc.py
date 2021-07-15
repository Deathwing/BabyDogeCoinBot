import os
import pathlib
from datetime import datetime, timedelta
from enum import IntEnum

import discord
from bscscan import BscScan
from coinmarketcapapi import CoinMarketCapAPI
from currency_converter import CurrencyConverter
from dotenv import load_dotenv

load_dotenv()

#BABY_DOGE_ROLE_NAME = "Baby Doge"

class CryptoCurrency(IntEnum):
    WBNB = 7192
    BabyDoge = 10407

    #This is not the correct Symbol, but we keep it for backward compatibility on discord :)
    BabyDogeCoin = 10407

CRYPTO_CURRENCY_REGISTER = {
    CryptoCurrency.WBNB: {
        "contract_address": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "burn_address": None,
        "decimals": 1000000000000000000
    },
    CryptoCurrency.BabyDoge: {
        "contract_address": "0xc748673057861a797275cd8a068abb95a902e8de",
        "burn_address": "0x000000000000000000000000000000000000dead",
        "decimals": 1000000000
    }
}

class BabyDogeCoinBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.reactions = True

        self.initialized = False
        self.crypto_currency_cache = {}

        super().__init__(intents=intents)

    async def on_ready(self):
        if self.initialized:
            return

        print(f"{self.user.name} has connected to {self.guilds}!")

#        for guild in self.guilds:
#            baby_doge_role = discord.utils.get(guild.roles, name=BABY_DOGE_ROLE_NAME)
#            if baby_doge_role is not None:
#                added_baby_doge_roles = 0
#                for member in guild.members:
#                    if not member.bot and baby_doge_role not in member.roles:
#                        await member.add_roles(baby_doge_role)
#                        added_baby_doge_roles += 1
#                print(f"Added {baby_doge_role} to {added_baby_doge_roles} members of {guild}")
    
        self.bsc = BscScan(os.getenv("BSC_SCAN_API_KEY"))
        self.cmc = CoinMarketCapAPI(os.getenv("COIN_MARKET_CAP_API_KEY"))
        self.cc = CurrencyConverter()

        self.initialized = True

#    async def on_member_join(self, member):
#        if not member.bot:
#            baby_doge_role = discord.utils.get(member.guild.roles, name=BABY_DOGE_ROLE_NAME)
#            if baby_doge_role is not None:
#                await member.add_roles(baby_doge_role)

    async def on_message(self, message):
        if message.author != self.user and message.content.startswith("$"):
            response = await self.handle_command(message)
            if response is not None:
                await message.channel.send(f"{response}")

    async def handle_command(self, message):
        lower_content = message.content.lower()
        if lower_content.startswith("$babydogecoin help"):
            return self.get_help_string()

        for crypto_currency_name, crypto_currency in CryptoCurrency.__members__.items():
            if lower_content.startswith(f"${crypto_currency_name.lower()} price"):
                return await self.get_crypto_currency_price_string(crypto_currency)

            if lower_content.startswith(f"${crypto_currency_name.lower()} balance"):
                splitted_content = message.content.split()
                if len(splitted_content) != 3:
                    return f"Incorrect syntax. Usage: ${crypto_currency_name.lower()} balance <address>"

                address = splitted_content[2]
                return await self.get_crypto_currency_balance_string(crypto_currency, address)

        return None

    def get_help_string(self):
        response = f"Baby Doge Coin Bot (Version: {get_version()})"

        response += "\n$babydogecoin price - Returns the current pricing information"
        response += "\n$babydogecoin balance <address> - Returns the current token balance for a specific address"

        return response

    async def get_crypto_currency_price_string(self, crypto_currency):
        try:
            data = await self.get_crypto_currency_data(crypto_currency)
            supply = data["total_supply"]
            usd_quota = data["quote"]["USD"]
            usd_price = usd_quota["price"]
            eur_quota = data["quote"]["EUR"]
            eur_price = eur_quota["price"]
            usd_market_cap = supply * usd_price
            last_updated = data["last_updated"]

            has_burn_data = False
            if CRYPTO_CURRENCY_REGISTER[crypto_currency]["burn_address"] is not None:
                burn_balance = await self.get_crypto_currency_balance(crypto_currency, CRYPTO_CURRENCY_REGISTER[crypto_currency]["burn_address"])
                burn_percentage = burn_balance / supply
                usd_burn_value = burn_balance * usd_price
                usd_market_cap -= usd_burn_value
                has_burn_data = True

            response = "Price (CoinMarketCap):"
            if crypto_currency == CryptoCurrency.BabyDoge:
                response += f"\n1B {data['symbol']} = {'{:0,.3f}'.format(usd_price * 1000000000)} USD | {'{:0,.3f}'.format(eur_price * 1000000000)} EUR"
                response += f"\n1T {data['symbol']} = {'{:0,.0f}'.format(usd_price * 1000000000000)} USD | {'{:0,.0f}'.format(eur_price * 1000000000000)} EUR"
            else:
                response += f"\n1 {data['symbol']} = {'{:0,.3f}'.format(usd_price)} USD | {'{:0,.3f}'.format(eur_price)} EUR"

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
            response += f"\n:moneybag:MarketCap: **${'{:0,.2f}'.format(usd_market_cap)}** :moneybag:"
            if has_burn_data:
                response += f"\n"
                response += f"\n:fire:Burned: {'{:0,.2f}'.format(burn_balance)} | {'{:0,.2f}'.format(burn_percentage * 100)}% :fire:"
            response += f"\n"
            response += f"\n*data last updated at: {last_updated}"

            return response
        except Exception as ex:
            print (ex)
            return f"Something went wrong."

    async def get_crypto_currency_balance_string(self, crypto_currency, address):
        try:
            data = await self.get_crypto_currency_data(crypto_currency)
            balance = await self.get_crypto_currency_balance(crypto_currency, address)
            balance_in_usd = data["quote"]["USD"]["price"] * balance
            balance_in_eur = data["quote"]["EUR"]["price"] * balance

            response = f"The address {address} has:"
            response += f"\n{balance:0,.12f} {data['symbol']} (${balance_in_usd:0,.2f} | {balance_in_eur:0,.2f}€)"
            if address == CRYPTO_CURRENCY_REGISTER[crypto_currency]["burn_address"]:
                response += f"\n:fire: This address is the official burn address :fire:"

            return response
        except Exception as ex:
            print (ex)
            return f"Something went wrong. Is the address correct?"

    async def get_crypto_currency_data(self, crypto_currency):
        if not crypto_currency in CRYPTO_CURRENCY_REGISTER:
            raise Exception(f"The crypto currency {crypto_currency} is not yet supported.")

        if crypto_currency in self.crypto_currency_cache:
            cache = self.crypto_currency_cache[crypto_currency]
            if (cache["last_cached_at"] + timedelta(seconds=60) > datetime.utcnow()):
                return cache

        id = int(crypto_currency)
        data = self.cmc.cryptocurrency_quotes_latest(id=id).data[str(id)]
        data["quote"]["EUR"] = {
            "price": data["quote"]["USD"]["price"] * self.cc.convert(1, 'USD', 'EUR')
        }
        data["last_cached_at"] = datetime.utcnow()

        self.crypto_currency_cache[crypto_currency] = data
        return data

    async def get_crypto_currency_balance(self, crypto_currency, address):
        if not crypto_currency in CRYPTO_CURRENCY_REGISTER:
            raise Exception(f"The crypto currency {crypto_currency} is not yet supported.")

        contract_address = CRYPTO_CURRENCY_REGISTER[crypto_currency]["contract_address"]
        async with self.bsc as bsc:
            balance = await bsc.get_acc_balance_by_token_contract_address(contract_address=contract_address, address=address)
            return float(balance) / CRYPTO_CURRENCY_REGISTER[crypto_currency]["decimals"]

def get_version():
    file_name = pathlib.Path(__file__)
    if file_name.exists():
        modification_time = datetime.fromtimestamp(file_name.stat().st_mtime)
        return modification_time.strftime("%Y-%m-%d %H:%M")

    return "?"

if __name__ == "__main__":
    client = BabyDogeCoinBot()
    client.run(os.getenv("DISCORD_TOKEN"))