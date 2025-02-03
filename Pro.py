import time
from collections import defaultdict
from Database import add_new_user
from Helius import getSignaturesForAddress, parseTransactions

HOME_WALLET = "63GVNyEedLgvhgoGXypLhvBMGLP2hkFryLo3cp9CHa6W"

database = defaultdict(tuple)
temp_wallets = defaultdict(tuple)

def set_active_users(active_users):
    global database
    for user_id, user_data in active_users.items():
        database[user_id] = user_data  # Set user_id as key and the tuple (transaction_sig, amount, expiry_date) as value
    print(f"Active users set in the database: {list(database.keys())}")

async def run_setWallet(wallet_address, telegram_user_id):
    telegram_user_id = str(telegram_user_id)
    current_timestamp = int(time.time())  # Current time in seconds since epoch

    # Iterate over the dictionary and remove expired wallets in place
    for key in list(temp_wallets.keys()):  # Convert to list to safely modify the dict during iteration
        if temp_wallets[key][1] < current_timestamp:
            del temp_wallets[key]

    if telegram_user_id in database:
        return "This Telegram account is already being used by a premium user"

    if telegram_user_id in temp_wallets:
        # Fetch the expiration time from temp_wallets and calculate the remaining time
        expiration_timestamp = temp_wallets[telegram_user_id][1]
        remaining_time = expiration_timestamp - current_timestamp
        return f"Wallet address already being used. Expires in {remaining_time} seconds."

    # set the wallet in hot storage with a timestamp
    expiration_timestamp = current_timestamp + (60 * 30)  # Expiration time

    # Store the user_id and expiration_timestamp as a tuple
    temp_wallets[telegram_user_id] = (wallet_address, expiration_timestamp)

    return (
        f"💰 Wallet is set for the next 30 minutes! 💰\n"
        f"⏳ You can now proceed with the payment."
    )


async def run_pro(transaction_sig, telegram_user_id):
    telegram_user_id = str(telegram_user_id)

    # Remove expired wallets from temp
    current_timestamp = int(time.time())  # Current time in seconds since epoch
    # Iterate over the dictionary and remove expired wallets in place
    for key in list(temp_wallets.keys()):  # Convert to list to safely modify the dict during iteration
        if temp_wallets[key][1] < current_timestamp:
            del temp_wallets[key]

    if telegram_user_id in database:
        return "This Telegram account is already being used by a premium user"

    if telegram_user_id not in temp_wallets:
        return (
            "No set wallet found for your Telegram account.\nPlease set the wallet you wish to send from.\n"
            "Please ensure you call /setwallet and /pro from the same Telegram account"
        )

    signatures = await getSignaturesForAddress(HOME_WALLET)
    matching_signature = next((sig for sig in signatures if sig == transaction_sig), None)

    if not matching_signature:
        return (
            "Signature provided is not found in our wallet.\n"
            "Try again after the transaction signature is confirmed."
        )

    native_transactions_details = await parseTransactions([matching_signature], None, None, None, None, True)

    if not native_transactions_details:
        return (
            "Signature not found in our wallet.\n"
            "Please ensure you're sending from the correct wallet and within 30 minutes of setting it.\n"
            "If the issue persists, try again after the transaction signature is confirmed."
        )

    for transfer in native_transactions_details:
        if transfer.get("timestamp") < (temp_wallets.get(telegram_user_id)[1] - (60 * 30)):
            return "This transaction occured before setting account"

        fromUserAccount = transfer.get("fromUserAccount", None)
        toUserAccount = transfer.get("toUserAccount", None)
        lamport = transfer.get("amount", None)

        if not fromUserAccount or not toUserAccount or not lamport:
            break

        if fromUserAccount == temp_wallets.get(telegram_user_id)[0] and toUserAccount == HOME_WALLET:
            amount = lamport / 1_000_000_000
            rounded_amount = round(amount, 3)
            rounded_amount = int(rounded_amount)

            if rounded_amount < 1:
                return ("Please send a minimum of 1 sol\n"
                        "1 sol per month\n"
                )

            expiry_duration_seconds = float(rounded_amount) * 30 * 24 * 60 * 60
            expiry_timestamp = current_timestamp + expiry_duration_seconds

            # Remove from temp storage and add to database
            database[telegram_user_id] = (transaction_sig, str(rounded_amount), str(expiry_timestamp), fromUserAccount)
            await add_new_user(telegram_user_id, transaction_sig, str(rounded_amount), str(expiry_timestamp), fromUserAccount)
            del temp_wallets[telegram_user_id]

            return ("💎 Welcome to Premium 💎")
    return "Something went wrong"


async def isPremiumUser(telegram_user_id):
    telegram_user_id = str(telegram_user_id)
    # Remove expired users
    current_timestamp = int(time.time())
    for user_id, (transaction_sig, rounded_amount, expiry_timestamp, fromUserAccount) in list(database.items()):
        if int(expiry_timestamp) < current_timestamp:
            del database[user_id]

    if telegram_user_id in database:
        return True
    else:
        return False













