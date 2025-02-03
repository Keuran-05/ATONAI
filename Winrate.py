import asyncio
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, TypedDict, Set
from Ai import find_price_for_date
from Helius import (getAsset, getSignaturesForAddress, getTokenAccountsByOwner, getTokenLargestAccounts, getTokenSupply, parseTransactions)
from Logs import log_info, log_warning
from Solscan import get_price


class TradeResult(TypedDict):
    winrate: float
    total_pnl: float
    total_trades: int
    total_wins: int
    previous_coins: Dict[str, float]


class Transfer(TypedDict):
    mint: str
    timestamp: int
    tokenAmount: float
    toUserAccount: str
    fromUserAccount: str


class TokenSymbolCache:
    def __init__(self):
        self.cache: Dict[str, str] = {}
        self.lock = asyncio.Lock()

    async def get(self, token_address: str) -> str:
        if token_address in self.cache:
            return self.cache[token_address]

        async with self.lock:
            # Double-check pattern
            if token_address in self.cache:
                return self.cache[token_address]

            try:
                data = await getAsset(token_address)
                symbol = data.get("result", {}).get("content", {}).get("metadata", {}).get("symbol", "Unknown")
                self.cache[token_address] = symbol
                return symbol
            except Exception as e:
                log_warning(f"Error fetching token symbol: {e}")
                return "Unknown"


# Global cache instance
token_symbol_cache = TokenSymbolCache()


def format_number(num: float) -> str:
    if num >= 1e12: return f"{int(num / 1e12)}T"
    if num >= 1e9: return f"{int(num / 1e9)}B"
    if num >= 1e6: return f"{int(num / 1e6)}M"
    if num >= 1e3: return f"{int(num / 1e3)}K"
    return str(int(num))


async def process_wallet_data(wallet: str, balance: float, supply: float, idx: int,
                              userAccount: str, last_week: int) -> Tuple[List[str], Optional[Dict[str, float]]]:
    try:
        percentage = (balance / supply) * 100 if supply else 0
        icon = "🐋" if percentage > 5 else "🐬" if percentage > 3 else "🐟"

        output = [f"#{idx} {userAccount[:3]}...{userAccount[-3:]} | ({percentage:.2f}%) {icon}"]

        signature_data = await getSignaturesForAddress(userAccount, 100)
        if not signature_data:
            return output, None

        account_transactions = await parseTransactions(signature_data, None, last_week, False, userAccount)
        if not account_transactions:
            return output, None

        transfers, _ = account_transactions[:20]
        account_results = await get_winrate(transfers, userAccount)

        if account_results['total_trades'] > 0:
            output.extend([
                f"├ PNL: {account_results['total_pnl']:.2f}",
                f"├ Winrate: {account_results['winrate']:.2f}%"
            ])
            return output, account_results['previous_coins']

        return output, None
    except Exception as e:
        log_warning(f"Error in process_wallet_data: {e}")
        return [f"#{idx} Error processing wallet"], None


async def process_assets(wallet_assets: List[Dict], previous_coins: Dict[str, float]) -> List[str]:
    if not previous_coins:
        return ["└ No other assets for this account.\n"]

    try:
        wallet_mints: Set[str] = {asset['mint'] for asset in wallet_assets}
        relevant_mints = [
            (mint, value)
            for mint, value in sorted(previous_coins.items(), key=lambda x: x[1], reverse=True)[:3]
            if mint in wallet_mints
        ]

        if not relevant_mints:
            return ["└ No matching assets found.\n"]

        symbols = await asyncio.gather(*[
            token_symbol_cache.get(mint) for mint, _ in relevant_mints
        ])

        formatted_assets = [
            f"{symbol} ({format_number(value)})"
            for (_, value), symbol in zip(relevant_mints, symbols)
        ]

        return ["├ Assets: " + ", ".join(formatted_assets)]
    except Exception as e:
        log_warning(f"Error in process_assets: {e}")
        return ["└ Error processing assets\n"]


async def process_trade(buy: Transfer, sells: Dict[str, List[Transfer]],
                        price_data: List[Dict]) -> Tuple[float, float, int, int]:
    if not price_data:
        return 0, 0, 0, 0

    try:
        price_buy = price_data[0]["price"]
        end_price = price_data[-1]["price"]
        remaining_amount = buy["tokenAmount"]
        total_pnl = pnl_for_trade = trades = wins = 0

        sell_list = sells.get(buy["mint"], [])
        valid_sells = [
            (sell, price) for sell in sell_list
            if buy["timestamp"] < sell["timestamp"]
               and (price := await find_price_for_date(price_data, sell["timestamp"]))
        ]

        for sell, price_sell in valid_sells:
            if remaining_amount <= 0:
                break

            trade_amount = min(remaining_amount, sell["tokenAmount"])
            pnl = trade_amount * (price_sell - price_buy)

            pnl_for_trade += pnl
            total_pnl += pnl
            trades += 1
            wins += int(pnl > 0)
            remaining_amount -= trade_amount

        if remaining_amount > 0:
            unrealized_pnl = remaining_amount * (end_price - price_buy)
            pnl_for_trade += unrealized_pnl
            total_pnl += unrealized_pnl
            trades += 1
            wins += int(unrealized_pnl > 0)

        return total_pnl, pnl_for_trade, trades, wins
    except Exception as e:
        log_warning(f"Error in process_trade: {e}")
        return 0, 0, 0, 0


async def get_winrate(transfers: List[Transfer], account: str) -> TradeResult:
    buys: List[Transfer] = []
    sells: Dict[str, List[Transfer]] = defaultdict(list)
    previous_coins: Dict[str, float] = defaultdict(float)

    for transfer in transfers:
        if transfer["toUserAccount"] == account:
            buys.append(transfer)
        else:
            sells[transfer["mint"]].append(transfer)

    async def process_single_buy(buy: Transfer) -> Optional[Tuple[float, int, int]]:
        price_data = await get_price(buy["mint"], buy["timestamp"])
        if not price_data:
            return None

        total_pnl, pnl_for_trade, trades, wins = await process_trade(buy, sells, price_data)
        previous_coins[buy["mint"]] += pnl_for_trade
        return total_pnl, trades, wins

    results = await asyncio.gather(*[
        process_single_buy(buy) for buy in buys
    ])

    total_pnl = total_trades = total_wins = 0
    for result in results:
        if result:
            pnl, trades, wins = result
            total_pnl += pnl
            total_trades += trades
            total_wins += wins

    return {
        "winrate": (total_wins / total_trades * 100) if total_trades > 0 else 0,
        "total_pnl": total_pnl,
        "total_trades": total_trades,
        "total_wins": total_wins,
        "previous_coins": dict(previous_coins)
    }


async def run_winrate(token_address: str) -> Optional[str]:
    try:
        log_info(f"Starting scan for token: {token_address}")

        top_wallets, supply = await asyncio.gather(
            getTokenLargestAccounts(token_address),
            getTokenSupply(token_address)
        )

        if not top_wallets:
            return None

        async def process_token_account(token_data: Tuple[str, float]) -> Optional[Tuple[str, str, float]]:
            token_account, balance = token_data
            try:
                signatures = await getSignaturesForAddress(token_account, 10)
                owner = await parseTransactions(signatures, token_account, None, True, None)
                if owner:
                    return token_account, owner, balance
            except Exception as e:
                log_warning(f"Error processing token account {token_account}: {e}")
            return None

        wallet_data = await asyncio.gather(*[
            process_token_account(wallet) for wallet in top_wallets
        ])

        valid_wallets = [data for data in wallet_data if data]
        if not valid_wallets:
            return None

        wallet_assets = await asyncio.gather(*[
            getTokenAccountsByOwner(owner, None) for _, owner, _ in valid_wallets
        ])

        now = int(time.time())
        last_week = now - (7 * 24 * 60 * 60)

        wallet_outputs = await asyncio.gather(*[
            process_wallet_data(token_account, balance, supply, idx, owner, last_week)
            for idx, (token_account, owner, balance) in enumerate(valid_wallets, 1)
        ])

        asset_outputs = await asyncio.gather(*[
            process_assets(assets, coins)
            for (_, coins), assets in zip(wallet_outputs, wallet_assets)
            if coins and not isinstance(assets, Exception)
        ])

        # Formatting for Telegram output
        output_lines = []
        output_lines.append("🏆 *Top Wallet Holders & Trade Performance:*")
        output_lines.append("━━━━━━━━━━━━━━━━━━━━━━\n")

        for (wallet_output, _), asset_output in zip(wallet_outputs, asset_outputs):
            output_lines.extend(wallet_output)
            output_lines.extend(asset_output)
            output_lines.append("━━━━━━━━━━━━━━━━━━━━━━\n")

        return "\n".join(output_lines)

    except Exception as e:
        log_warning(f"Error in run_winrate: {e}")
        return "❌ *An error occurred while processing the data.*"


    except Exception as e:
        log_warning(f"Error in run_winrate: {e}")
        return None


async def check_date(timestamp: int, reference_timestamp: Optional[int] = None) -> bool:
    dt1 = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
    dt2 = (datetime.fromtimestamp(reference_timestamp, tz=timezone.utc) if reference_timestamp
           else datetime.now(timezone.utc)).date()
    return dt1 != dt2