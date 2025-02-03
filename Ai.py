from collections import defaultdict
from datetime import datetime, timezone
from Helius import getSignaturesForAddress, getTokenLargestAccounts, parseTransactions, getAsset
from Logs import log_warning
from Solscan import get_price
import time
import asyncio

async def run_ai(token_address):
    now = int(time.time())
    last_week = now - (7 * 24 * 60 * 60)

    # Fetch top ten accounts in parallel
    top_ten = await getTokenLargestAccounts(token_address)

    # Fetch signatures and parse transactions concurrently
    signature_tasks = [getSignaturesForAddress(token, 10) for token, _ in top_ten]
    signatures_data = await asyncio.gather(*signature_tasks)

    # Process user accounts in parallel
    user_accounts_tasks = [
        parseTransactions(sig_data, token, last_week, True, None)
        for sig_data, (token, _) in zip(signatures_data, top_ten)
    ]
    user_accounts = [ua for ua in await asyncio.gather(*user_accounts_tasks) if ua]

    formatted_results, confidence_pack, overall_winrate = [], [], 0.0
    wallet_index = 1  # Start counting valid wallets

    # Fetch transactions for user accounts concurrently
    signature_tasks = [getSignaturesForAddress(account, 100) for account in user_accounts]
    signatures_data = await asyncio.gather(*signature_tasks)

    transaction_tasks = [
        parseTransactions(sig_data, None, last_week, False, account)
        for sig_data, account in zip(signatures_data, user_accounts)
    ]
    transaction_results = await asyncio.gather(*transaction_tasks)

    # Process each account's transactions
    for account, transactions in zip(user_accounts, transaction_results):
        if not transactions:
            continue

        transfers, _ = transactions[:2]
        account_results = await get_winrate(transfers, account)

        if account_results['total_trades'] > 0:
            overall_winrate += account_results['winrate']

            # Fetch token symbols concurrently for previous trades
            previous_trades = account_results['previous_coins'][:3]
            token_symbols = await asyncio.gather(*[get_token_symbol(trade[0]) for trade in previous_trades])

            formatted_trades = "\n".join([
                f"{symbol}: {'✅ Profit' if trade[1] > 0 else '❌ Loss'} (${trade[1]:.2f})"
                for symbol, trade in zip(token_symbols, previous_trades)
            ])

            formatted_results.append(
                f"{wallet_index}️⃣ Wallet #{wallet_index}\n"
                f"💼 Previous Coins:\n{formatted_trades}\n"
                f"📈 Win Rate: {account_results['winrate']:.2f}%\n"
                f"Total PnL: {account_results['total_pnl']:.2f}\n\n"
            )

            confidence_pack.append((
                account_results['winrate'],
                account_results['total_pnl'],
                account_results['total_trades']
            ))

            wallet_index += 1  # Increment only for valid wallets

    # Compute overall win rate safely
    avg_winrate = (overall_winrate / len(confidence_pack)) if confidence_pack else 0

    # Get AI confidence level
    confidence_level = await get_confidence_level(confidence_pack)

    overall_results = (
        f"🤖 AI Prediction Score Analysis\n"
        f"🎯 Overall Win Rate: 🌟 {avg_winrate:.2f}%\n"
        f"🔍 AI Confidence Level: {confidence_level}\n\n"
    )

    return overall_results + ''.join(formatted_results) if formatted_results else "No trading data available for analysis."


async def get_winrate(transfers, account):
    all_buy = [t for t in transfers if t.get("toUserAccount") == account]
    all_sell = defaultdict(list)
    for t in transfers:
        if t.get("fromUserAccount") == account:
            all_sell[t.get("mint")].append(t)

    previous_coins = []
    total_pnl, total_trades, total_wins = 0, 0, 0

    # Batch price lookups
    mints = list(set(buy.get("mint") for buy in all_buy))
    prices_map = {
        mint: await get_price(mint, all_buy[0].get("timestamp"))
        for mint in mints
    }

    for buy in all_buy:
        mint = buy.get("mint")
        price_buy_array = prices_map.get(mint, [])

        if not price_buy_array:
            log_warning(f"Price data unavailable for mint {mint}")
            continue

        buy_amount = buy.get("tokenAmount")
        pnl_for_trade = 0
        sell_trades = all_sell.get(mint, [])[:]

        for sell_trade in sell_trades:
            if buy_amount <= 0:
                break

            if await check_older(buy.get("timestamp"), sell_trade.get("timestamp")):
                price_sell = await find_price_for_date(price_buy_array, sell_trade.get("timestamp"))
                price_buy = price_buy_array[0].get("price")

                if not price_sell:
                    break

                sell_amount = sell_trade.get("tokenAmount")
                traded_amount = min(buy_amount, sell_amount)

                buy_usd = traded_amount * price_buy
                sell_usd = traded_amount * price_sell
                pnl = sell_usd - buy_usd

                pnl_for_trade += pnl
                total_pnl += pnl
                total_trades += 1

                if pnl > 0:
                    total_wins += 1

                buy_amount -= traded_amount
                sell_trade["tokenAmount"] -= traded_amount

                if sell_trade["tokenAmount"] == 0:
                    sell_trades.remove(sell_trade)

        # Handle unrealized profits
        if buy_amount > 0:
            end_price = price_buy_array[-1].get("price")
            start_price = price_buy_array[0].get("price")
            unrealized_pnl = (end_price - start_price) * buy_amount

            if unrealized_pnl > 0:
                total_wins += 1

            total_pnl += unrealized_pnl
            pnl_for_trade += unrealized_pnl
            total_trades += 1

        previous_coins.append((mint, pnl_for_trade))

    return {
        "winrate": (total_wins / total_trades) * 100 if total_trades > 0 else 0,
        "total_pnl": total_pnl,
        "total_trades": total_trades,
        "total_wins": total_wins,
        "previous_coins": previous_coins,
    }


# Remaining functions stay the same
async def get_confidence_level(confidence_pack):
    if len(confidence_pack) == 0:
        avg_winrate = 0
        avg_pnl = 0
        avg_trades = 0
    else:
        avg_winrate = sum(account[0] for account in confidence_pack) / len(confidence_pack)
        avg_pnl = sum(account[1] for account in confidence_pack) / len(confidence_pack)
        avg_trades = sum(account[2] for account in confidence_pack) / len(confidence_pack)



    if avg_winrate >= 70 and avg_pnl >= 1000 and avg_trades >= 15:
        confidence_level = "High"
    elif avg_winrate >= 50 and avg_pnl >= 500 and avg_trades >= 10:
        confidence_level = "Medium"
    else:
        confidence_level = "Low"

    return confidence_level


async def get_token_symbol(token_address):
    data = await getAsset(token_address)
    result = data.get("result", {}).get("content", {}).get("metadata", {})
    return result.get("symbol", "Symbol not found")


async def find_price_for_date(price_buy_array, date):
    return next((day.get("price") for day in price_buy_array if day.get("date") == date), None)


async def check_current_date(timestamp):
    timestamp_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
    current_date = datetime.now(timezone.utc).date()
    return timestamp_date != current_date


async def check_older(buy_time, sell_time):
    buy_date = datetime.fromtimestamp(buy_time, tz=timezone.utc).date()
    sell_date = datetime.fromtimestamp(sell_time, tz=timezone.utc).date()
    return buy_date < sell_date