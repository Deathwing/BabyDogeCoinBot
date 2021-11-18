import json
import os
import pathlib
from datetime import datetime, timedelta
from enum import IntEnum

import discord
from bscscan import BscScan
from coinmarketcapapi import CoinMarketCapAPI
from pythonpancakes import PancakeSwapAPI
from currency_converter import CurrencyConverter
from dotenv import load_dotenv

load_dotenv()

class PriceSource(IntEnum):
    CoinMarketCap = 0
    PancakeSwap = 1

class CoinPriceBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.reactions = True

        self.initialized = False
        self.crypto_currency_cache = {}

        with open("ccr.json") as ccr_json_file:
            self.crypto_currency_register = json.load(ccr_json_file)

        super().__init__(intents=intents)

    async def on_ready(self):
        if self.initialized:
            return

        print(f"{self.user.name} has connected to {self.guilds}!")

        self.bsc = BscScan(os.getenv("BSC_SCAN_API_KEY"))
        self.cmc = CoinMarketCapAPI(os.getenv("COIN_MARKET_CAP_API_KEY"))
        self.ps = PancakeSwapAPI()
        self.cc = CurrencyConverter()

        self.initialized = True

    async def on_message(self, message):
        if message.author != self.user and (message.content.startswith("#") or message.content.startswith("$")):
            response = await self.handle_command(message)
            if response is not None:
                await message.channel.send(f"{response}")

    async def handle_command(self, message):
        lower_content = message.content.lower()
        if message.author.id == 231183500559122432:
            if lower_content.startswith("#remove ccr"):
                splitted_content = message.content.split()
                if len(splitted_content) != 3:
                    return f"Incorrect syntax. Usage: #remove ccr <symbol>"

                symbol = splitted_content[2]
                if symbol not in self.crypto_currency_register:
                    return f"{symbol} hasn't been removed as it wasn't even present."

                del self.crypto_currency_register[symbol]
                with open("ccr.json", "w") as ccr_json_file:
                    json.dump(self.crypto_currency_register, ccr_json_file, indent = 4) 
                return f"{symbol} has been removed."

            if lower_content.startswith("#update ccr"):
                splitted_content = message.content.split()
                if len(splitted_content) < 8 or len(splitted_content) > 9:
                    return f"Incorrect syntax. Usage: #update ccr <symbol> <id> <contract_address> <burn_address> <decimals> <use_big_numbers> [<supply>]"

                symbol = splitted_content[2]
                id = int(splitted_content[3])
                contract_address = splitted_content[4]
                burn_address = None if splitted_content[5] == "null" else splitted_content[5]
                decimals =  int(splitted_content[6])
                use_big_numbers = True if splitted_content[7] == "true" else False
                if len(splitted_content) == 9:
                    supply = splitted_content[8]

                self.crypto_currency_register[symbol] = {
                    "id": id,
                    "contract_address": contract_address,
                    "burn_address": burn_address,
                    "decimals": decimals,
                    "use_big_numbers": use_big_numbers,
                }
                if len(splitted_content) == 9:
                    self.crypto_currency_register[symbol]["supply"] = supply

                with open("ccr.json", "w") as ccr_json_file:
                    json.dump(self.crypto_currency_register, ccr_json_file, indent = 4) 

                return f"{symbol} has been updated."

        if lower_content.startswith("$coinpricebot help"):
            return self.get_help_string()

        for crypto_currency in self.crypto_currency_register:
            if lower_content.startswith(f"${crypto_currency.lower()} price"):
                return await self.get_crypto_currency_price_string(crypto_currency)

            if lower_content.startswith(f"${crypto_currency.lower()} balance"):
                splitted_content = message.content.split()
                if len(splitted_content) != 3:
                    return f"Incorrect syntax. Usage: ${crypto_currency.lower()} balance <address>"

                address = splitted_content[2]
                return await self.get_crypto_currency_balance_string(crypto_currency, address)

        return None

    def get_help_string(self):
        response = f"Coin Price Bot (Version: {get_version()})"

        response += "\n$<symbol> price - Returns the current pricing information"
        response += "\n$<symbol> balance <address> - Returns the current token balance for a specific address"

        return response

    async def get_crypto_currency_price_string(self, crypto_currency):
        try:
            data = await self.get_crypto_currency_data(crypto_currency)
            symbol = data['symbol']
            supply = data["max_supply"]
            usd_quota = data["quote"]["USD"]
            usd_price = usd_quota["price"]
            eur_quota = data["quote"]["EUR"]
            eur_price = eur_quota["price"]
            usd_market_cap = supply * usd_price
            last_updated = data["last_updated"]

            has_burn_data = False
            if self.crypto_currency_register[crypto_currency]["burn_address"] is not None:
                burn_balance = await self.get_crypto_currency_balance(crypto_currency, self.crypto_currency_register[crypto_currency]["burn_address"])
                burn_percentage = burn_balance / supply
                usd_burn_value = burn_balance * usd_price
                usd_market_cap -= usd_burn_value
                has_burn_data = True

            response = "Price (" + str(data["price_source"]) + "):"
            if self.crypto_currency_register[crypto_currency]["use_big_numbers"]:
                response += f"\n1B {symbol} = {'{:0,.3f}'.format(usd_price * 1000000000)} USD | {'{:0,.3f}'.format(eur_price * 1000000000)} EUR"
                response += f"\n1T {symbol} = {'{:0,.0f}'.format(usd_price * 1000000000000)} USD | {'{:0,.0f}'.format(eur_price * 1000000000000)} EUR"
            else:
                response += f"\n1 {symbol} = {'{:0,.3f}'.format(usd_price)} USD | {'{:0,.3f}'.format(eur_price)} EUR"

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
            #print (ex)
            return f"Something went wrong."

    async def get_crypto_currency_balance_string(self, crypto_currency, address):
        try:
            data = await self.get_crypto_currency_data(crypto_currency)
            symbol = data['symbol']
            balance = await self.get_crypto_currency_balance(crypto_currency, address)
            balance_in_usd = data["quote"]["USD"]["price"] * balance
            balance_in_eur = data["quote"]["EUR"]["price"] * balance

            response = f"The address {address} has:"
            response += f"\n{balance:0,.12f} {symbol} (${balance_in_usd:0,.2f} | {balance_in_eur:0,.2f}€)"
            if address == self.crypto_currency_register[crypto_currency]["burn_address"]:
                response += f"\n:fire: This address is the official burn address :fire:"

            return response
        except Exception as ex:
            #print (ex)
            return f"Something went wrong. Is the address correct?"

    async def get_crypto_currency_data(self, crypto_currency):
        if not crypto_currency in self.crypto_currency_register:
            raise Exception(f"The crypto currency {crypto_currency} is not yet supported.")

        if crypto_currency in self.crypto_currency_cache:
            cache = self.crypto_currency_cache[crypto_currency]
            if (cache["last_cached_at"] + timedelta(seconds=60) > datetime.utcnow()):
                return cache

        id = self.crypto_currency_register[crypto_currency]["id"]
        try:
            data = self.cmc.cryptocurrency_quotes_latest(id=id).data[str(id)]
            data["price_source"] = PriceSource.CoinMarketCap
        except Exception as ex:
            #print (ex)
            raw_data = self.ps.tokens(self.crypto_currency_register[crypto_currency]["contract_address"])
            data = raw_data["data"]
            data["quote"] = {
                "USD": {
                    "price": float(data["price"])
                }
            }
            data["max_supply"] = self.crypto_currency_register[crypto_currency]["supply"]
            data["last_updated"] = datetime.utcfromtimestamp(raw_data["updated_at"] / 1000).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            data["price_source"] = PriceSource.PancakeSwap

        data["quote"]["EUR"] = {
            "price": data["quote"]["USD"]["price"] * self.cc.convert(1, 'USD', 'EUR')
        }
        data["last_cached_at"] = datetime.utcnow()

        self.crypto_currency_cache[crypto_currency] = data
        return data

    async def get_crypto_currency_balance(self, crypto_currency, address):
        if not crypto_currency in self.crypto_currency_register:
            raise Exception(f"The crypto currency {crypto_currency} is not yet supported.")

        contract_address = self.crypto_currency_register[crypto_currency]["contract_address"]
        async with self.bsc as bsc:
            balance = await bsc.get_acc_balance_by_token_contract_address(contract_address=contract_address, address=address)
            return float(balance) / self.crypto_currency_register[crypto_currency]["decimals"]

def get_version():
    file_name = pathlib.Path(__file__)
    if file_name.exists():
        modification_time = datetime.fromtimestamp(file_name.stat().st_mtime)
        return modification_time.strftime("%Y-%m-%d %H:%M")

    return "?"

if __name__ == "__main__":
    client = CoinPriceBot()
    client.run(os.getenv("DISCORD_TOKEN"))