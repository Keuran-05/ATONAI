import asyncio
from collections import defaultdict
from Helius import getSignaturesForAddress, getAccountInfo, getTokenSupply, parseTransactions
from Logs import log_info, log_debug

time_threshold = 60  # seconds
min_transfer_amount_percentage = 0.01  # 1% of total supply
chunk_size = 100
retry_limit = 3


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


async def get_bundle_sniping_insights(token_address):
    """Generate bundle sniping insights for a given token mint address."""
    log_info(f"Generating bundle sniping insights for mint address: {token_address}")
    signatures = await getSignaturesForAddress(token_address)
    total_supply = await getTokenSupply(token_address)
    min_transfer_threshold = total_supply * min_transfer_amount_percentage

    log_debug(f"Total supply: {total_supply}, Minimum transfer threshold: {min_transfer_threshold}")

    # Process chunks concurrently
    chunk_tasks = [
        parseTransactions(signatures[i:i + chunk_size], token_address, None, False, None)
        for i in range(0, len(signatures), chunk_size)
    ]
    results = await asyncio.gather(*chunk_tasks)

    # Aggregate results
    all_transfers = []
    address_frequency = defaultdict(int)
    for transfers, freq in results:
        all_transfers.extend(transfers)
        for address, count in freq.items():
            address_frequency[address] += count
    log_info("Transfers processed. Analyzing data...")

    most_frequent_address = max(address_frequency, key=address_frequency.get, default=None)
    if most_frequent_address:
        owner = await getAccountInfo(most_frequent_address)

    grouped_transfers = []
    current_group = []
    current_balance = 0
    unique_addresses = set()
    last_timestamp = None
    total_tokens = 0

    for transfer in all_transfers:
        if transfer["tokenAmount"] > min_transfer_threshold and (owner is None or transfer["toUserAccount"] != owner):
            if last_timestamp is None or (transfer["timestamp"] - last_timestamp) > time_threshold:
                if current_group:
                    grouped_transfers.append({
                        "group": current_group,
                        "totalBalance": current_balance,
                        "uniqueAddressesCount": len(unique_addresses)
                    })
                current_group = [transfer]
                current_balance = transfer["tokenAmount"]
                unique_addresses = {transfer["toUserAccount"]}
            else:
                current_group.append(transfer)
                current_balance += transfer["tokenAmount"]
                unique_addresses.add(transfer["toUserAccount"])

            total_tokens += transfer["tokenAmount"]
            last_timestamp = transfer["timestamp"]

    if current_group:
        grouped_transfers.append({
            "group": current_group,
            "totalBalance": current_balance,
            "uniqueAddressesCount": len(unique_addresses)
        })

    grouped_transfers_sorted = sorted(grouped_transfers, key=lambda g: g["totalBalance"], reverse=True)
    total_percent_bundled = (total_tokens / total_supply) * 100 if total_supply > 0 else 0
    total_tokens_formatted = await format_number(total_tokens)

    insights = [f"🌟 **Bundle Sniping Insights**",
                f"📊 **Total Percent Bundled:** {total_percent_bundled:.2f}% of total supply",
                f"🔢 **Total Bundles:** {len(grouped_transfers)}", f"🪙 **Total Tokens Bundled:** {total_tokens_formatted}\n",
                "🏆 **Top Bundles:**"]

    for i, group in enumerate(grouped_transfers_sorted[:5]):  # Show top 5 bundles
        percent_bundled = (group["totalBalance"] / total_supply) * 100 if total_supply > 0 else 0
        tokens_bought_formatted = await format_number(group['totalBalance'])
        insights.append(f"{i + 1}️⃣ **Bundle #{i + 1}:**")
        insights.append(f"📊 **Percent Bundled:** {percent_bundled:.2f}%")
        insights.append(f"👛 **Wallets:** {group['uniqueAddressesCount']}")
        insights.append(f"🪙 **Tokens Bought:** {tokens_bought_formatted}\n")

    log_info("Bundle sniping insights generation completed")
    return "\n".join(insights)
