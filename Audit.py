from Helius import getAsset, getTokenLargestAccounts, getTokenAccountsByOwner
from Logs import log_info


async def get_audit(token_address):
    """Perform an audit for the specified token mint address."""
    log_info(f"Starting audit for token mint address: {token_address}")
    data = await getAsset(token_address)

    if data is None:
        return None

    # Parse the valid response
    ownership = data.get('result', {}).get('ownership', {})
    mintable = data.get('result', {}).get('token_info', {}).get('mint_authority', None)
    authorities = data.get('result', {}).get('authorities', [])
    supply_data = data.get('result', {}).get('token_info', {}).get('supply', 0)
    supply_decimal = data.get('result', {}).get('token_info', {}).get('decimals', 0)
    supply = supply_data / (10 ** supply_decimal)

    authority_address = authorities[0].get('address', 'N/A') if authorities else 'N/A'
    owner_balance = 0
    if authority_address != 'N/A':
        owner_balance = await getTokenAccountsByOwner(authority_address, token_address)
        owner_balance = await format_number(owner_balance)

    top_wallets = await getTokenLargestAccounts(token_address)
    top_wallet_balance = 0
    if top_wallets:
        top_wallet_balance = sum(balance for _, balance in top_wallets)
    log_info(f"Total balance of top 10 wallets: {top_wallet_balance}")

    top_holder_percentage = (top_wallet_balance / int(supply)) * 100 if supply else 0

    metrics = {
        "🪙 Token Attributes:": {
            "Mintable:": "✅ Yes" if mintable else "❌ No",
            "Token Data Mutable:": "❌ No" if not data.get('result', {}).get('mutable', False) else "✅ Yes",
            "Freezable:": "❌ No" if not ownership.get('frozen', False) else "✅ Yes"
        },
        "🔑 Key Ownership Details:": {
            "🛠️ Update Authority:": authority_address,
            "👛 Owner Balance:": owner_balance if owner_balance else "0",
            "🔥 LP Burned:": "❌ No" if not data.get('result', {}).get('burnt', False) else "✅ Yes"
        },
        "📊 Holder Distribution:": {
            "🏆 Top 10 Holders:": f"{top_holder_percentage:.2f}% of supply" if supply > 0 else "NA"
        }
    }

    audit_result = "\n\n".join(
        f"{category}\n" + "\n".join(f"{metric} {value}" for metric, value in details.items())
        for category, details in metrics.items()
    )

    log_info("Audit completed successfully.")
    return audit_result


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