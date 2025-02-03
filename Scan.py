import asyncio
from Helius import getTokenLargestAccounts, getTokenSupply, getAsset, getTokenAccountsByOwner, getSignaturesForAddress, parseTransactions
from Logs import log_info, log_warning

# Fetch token symbol with batch support
async def get_token_symbol(token_address):
    data = await getAsset(token_address)
    result = data.get("result", {}).get("content", {}).get("metadata", {})
    symbol = result.get("symbol", "Symbol not found")
    return symbol


async def format_number(num):
    if num < 1000:
        return str(num)
    elif num < 1_000_000:
        return f"{num / 1_000:.1f}K".rstrip('0').rstrip('.')
    elif num < 1_000_000_000:
        return f"{num / 1_000_000:.1f}M".rstrip('0').rstrip('.')
    elif num < 1_000_000_000_000:
        return f"{num / 1_000_000_000:.1f}B".rstrip('0').rstrip('.')
    else:
        return f"{num / 1_000_000_000_000:.1f}T".rstrip('0').rstrip('.')


async def run_scan(token_address):
    log_info(f"Starting scan for token: {token_address}")
    top_wallets = await getTokenLargestAccounts(token_address)
    supply = await getTokenSupply(token_address)
    output = []

    if not top_wallets:
        log_warning("No wallets found or an error occurred.")
        return None

    userAccounts = []

    for tokenAccount, _ in top_wallets:
        signature_data_tokenAccount = await getSignaturesForAddress(tokenAccount, 10)
        userAccount = await parseTransactions(signature_data_tokenAccount, tokenAccount, None, True, None)
        userAccounts.append(userAccount)

    # Fetch wallet assets in parallel
    wallet_tasks = [getTokenAccountsByOwner(address, None) for address in userAccounts]
    wallet_results = await asyncio.gather(*wallet_tasks, return_exceptions=True)

    for idx, (wallet, balance) in enumerate(top_wallets, 1):
        percentage = (balance / supply) * 100 if supply else 0
        format_num = await format_number(balance)
        icon = "🐋" if percentage > 5 else "🐬" if percentage > 3 else "🐟"
        if userAccounts[idx-1]:
            output.append(f"#{idx} {userAccounts[idx-1][:3]}...{userAccounts[idx-1][-3:]} | Balance: {format_num} | ({percentage:.2f}%) {icon}")

            # Handle cases where no assets are found
            wallet_assets = wallet_results[idx - 1]
            if not isinstance(wallet_assets, list) or not wallet_assets:
                log_warning(f"No other assets for account {wallet}.")
                output.append("└ No other assets for this account.\n")
                continue

            # Fetch token symbols for assets
            assets = wallet_assets[:5]
            symbol_tasks = [get_token_symbol(asset["mint"]) for asset in assets]
            symbols = await asyncio.gather(*symbol_tasks, return_exceptions=True)

            for asset, symbol in zip(assets, symbols):
                if isinstance(symbol, Exception):
                    symbol = "Unknown"
                asset_formatted_balance = await format_number(asset['balance'])
                output.append(f"├ {symbol}: {asset_formatted_balance}")
            output.append("")


    log_info("Scan completed successfully.")
    return "\n".join(output)


