import asyncio
import ssl
from datetime import datetime, timezone
import aiohttp
import backoff
from collections import defaultdict
from typing import Optional, List, Dict, Tuple, Any, Union
from Config import HELIUS_API_KEY
from Logs import log_error, log_debug, log_warning, log_info
from PumpFun import get_bonding_curve_address

# Singleton instance
_client = None


async def get_client():
    global _client
    if _client is None:
        _client = HeliusClient()
    return _client


class HeliusClient:
    def __init__(self, api_key: str = HELIUS_API_KEY):
        self.api_key = api_key
        self.base_url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"
        self.parse_url = f"https://api.helius.xyz/v0/transactions?api-key={self.api_key}"
        self._session: Optional[aiohttp.ClientSession] = None
        self.ssl_context = self._create_ssl_context()

    @staticmethod
    def _create_ssl_context() -> ssl.SSLContext:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    async def _ensure_session(self):
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=self.ssl_context)
            )

    def _get_headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json"}

    @staticmethod
    def _validate_address(address: str, address_type: str = "address") -> bool:
        if not address:
            log_error(f"Invalid {address_type}: {address}")
            return False
        return True

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientResponseError, aiohttp.ClientError, asyncio.TimeoutError),
        jitter=backoff.full_jitter,
        max_time=10,
    )
    async def _make_request(self, url: str, payload: Dict) -> Optional[Dict]:
        log_debug(f"Making POST request to {url} with payload: {payload}")
        await self._ensure_session()

        max_retries = 10
        retry_count = 0

        while retry_count < max_retries:
            try:
                async with self._session.post(url, json=payload, headers=self._get_headers()) as response:
                    log_debug(f"Response Status Code: {response.status}")

                    if response.status in {429, 503}:
                        # Use retry-after from headers if available, otherwise use exponential backoff
                        retry_after = int(response.headers.get("retry-after", 2 ** (retry_count + 1)))
                        log_warning(f"Rate limited. Retry attempt {retry_count + 1}. Waiting {retry_after} seconds...")
                        await asyncio.sleep(retry_after)
                        retry_count += 1
                        continue

                    if response.status != 200:
                        error_text = await response.text()
                        log_error(f"Request failed with status {response.status}: {error_text}")
                        return None

                    data = await response.json()
                    if "error" in data:
                        log_error(f"API error: {data['error'].get('message', 'Unknown error')}")
                        return None

                    return data

            except Exception as e:
                log_error(f"Request failed: {str(e)}")
                retry_count += 1
                if retry_count >= max_retries:
                    print("ahhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh")
                    return None
                await asyncio.sleep(2 ** retry_count)
        print("ahhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh")
        return None

    async def get_asset(self, token_address: str) -> Optional[Dict]:
        if not self._validate_address(token_address, "token address"):
            return None

        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "getAsset",
            "params": {"id": token_address}
        }
        return await self._make_request(self.base_url, payload)

    async def get_account_info(self, account_address: str) -> Optional[str]:
        if not self._validate_address(account_address):
            return None

        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "getAccountInfo",
            "params": [account_address, {"encoding": "base58"}]
        }

        data = await self._make_request(self.base_url, payload)
        if not data:
            return None

        owner = data.get('result', {}).get('value', {}).get('owner')
        if owner == "11111111111111111111111111111111":
            return None
        return account_address

    async def get_token_largest_accounts(self, token_address: str) -> Optional[List[Tuple[str, int]]]:
        log_info(f"Fetching top wallets for token: {token_address}")
        if not self._validate_address(token_address, "token address"):
            return None

        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "getTokenLargestAccounts",
            "params": [token_address]
        }

        data = await self._make_request(self.base_url, payload)
        if not data:
            return None

        token_accounts = data.get("result", {}).get("value", [])
        if not token_accounts:
            log_warning(f"No token holders found for token address: {token_address}")
            return None

        bonding_curve_address = await get_bonding_curve_address(token_address)

        wallet_balances = [
            (account["address"], int(account["uiAmount"]))
            for account in token_accounts
            if account["address"] != bonding_curve_address
        ]

        log_info(f"Retrieved {len(wallet_balances)} wallets for token: {token_address}")
        return wallet_balances[:10]

    async def get_token_supply(self, token_address: str) -> Optional[float]:
        if not self._validate_address(token_address, "token address"):
            return None

        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "getTokenSupply",
            "params": [token_address]
        }

        data = await self._make_request(self.base_url, payload)
        if data:
            return data.get("result", {}).get("value", {}).get("uiAmount")
        return None

    async def get_token_accounts_by_owner(
            self,
            owner: str,
            token_address: Optional[str] = None
    ) -> Optional[Union[float, List[Dict[str, Any]]]]:
        if not self._validate_address(owner, "owner address"):
            return None

        filter_param = (
            {"mint": token_address} if token_address
            else {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}
        )

        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "getTokenAccountsByOwner",
            "params": [
                owner,
                filter_param,
                {"encoding": "jsonParsed"}
            ]
        }

        data = await self._make_request(self.base_url, payload)
        if not data:
            return None

        result_value = data.get("result", {}).get("value", [])

        if token_address:
            if not result_value:
                log_error(f"No token account found for token address {token_address} and owner {owner}")
                return None
            return float(result_value[0].get("account", {})
                         .get("data", {})
                         .get("parsed", {})
                         .get("info", {})
                         .get("tokenAmount", {})
                         .get("uiAmount", 0))

        assets = [
            {
                "mint": acc.get("account", {})
                .get("data", {})
                .get("parsed", {})
                .get("info", {})
                .get("mint", "Unknown Mint"),
                "balance": int(acc.get("account", {})
                               .get("data", {})
                               .get("parsed", {})
                               .get("info", {})
                               .get("tokenAmount", {})
                               .get("uiAmount", 0))
            }
            for acc in result_value
        ]

        log_info(f"Fetched {len(assets)} assets for wallet {owner}.")
        return sorted(assets, key=lambda x: x["balance"], reverse=True)

    async def get_signatures_for_address(self, address: str, limit: int = 1000) -> Optional[List[str]]:
        log_info(f"Fetching signatures for address: {address}")
        if not self._validate_address(address):
            return None

        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "getSignaturesForAddress",
            "params": [address, {"limit": limit}]
        }

        data = await self._make_request(self.base_url, payload)
        if data:
            return [entry["signature"] for entry in data.get("result", [])]
        return None

    async def parse_transactions(
            self,
            signatures: List[str],
            token_address: Optional[str] = None,
            time_filter: Optional[float] = None,
            get_user_account: bool = False,
            user_account: Optional[str] = None,
            native: bool = False
    ) -> Optional[Union[str, Tuple[List[Dict], Dict[str, int]]]]:
        payload = {"transactions": signatures}

        data = await self._make_request(self.parse_url, payload)
        if not data:
            return None

        if native == True:
            transaction = data[0]
            native_transfers = transaction.get('nativeTransfers', [])
            if native_transfers:
                for transfer in native_transfers:
                    transfer["timestamp"] = transaction.get("timestamp", None)
                return native_transfers
            return None

        transfers = []
        address_frequency = defaultdict(int)

        for tx in data:
            token_transfers = tx.get("tokenTransfers", [])
            if not token_transfers:
                continue

            for transfer in token_transfers:
                if get_user_account:
                    if transfer["fromTokenAccount"] == token_address and transfer["fromTokenAccount"] is not None:
                        return transfer["fromUserAccount"]
                    if transfer["toTokenAccount"] == token_address and transfer["toTokenAccount"] is not None:
                        return transfer["toUserAccount"]
                elif token_address:
                    if transfer.get("mint") == token_address:
                        transfer["timestamp"] = tx.get("timestamp")
                        address_frequency[transfer["toUserAccount"]] += 1
                        transfers.append(transfer)
                        break
                elif user_account and (
                        transfer["toUserAccount"] == user_account or
                        transfer["fromUserAccount"] == user_account
                ):
                    transfer["timestamp"] = tx.get("timestamp")
                    current_date = datetime.now(timezone.utc).date()
                    timestamp_date = datetime.fromtimestamp(transfer["timestamp"], tz=timezone.utc).date()
                    if time_filter is None or (transfer["timestamp"] > time_filter and current_date != timestamp_date):
                        transfers.append(transfer)
                        break

        return (transfers, address_frequency) if not get_user_account else None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session and not self._session.closed:
            await self._session.close()


# Backward-compatible function interfaces
async def getAsset(token_address: str) -> Optional[Dict]:
    client = await get_client()
    return await client.get_asset(token_address)


async def getAccountInfo(account_address: str) -> Optional[str]:
    client = await get_client()
    return await client.get_account_info(account_address)


async def getTokenLargestAccounts(token_address: str) -> Optional[List[Tuple[str, int]]]:
    client = await get_client()
    return await client.get_token_largest_accounts(token_address)


async def getTokenSupply(token_address: str) -> Optional[float]:
    client = await get_client()
    return await client.get_token_supply(token_address)


async def getTokenAccountsByOwner(
        owner: str,
        token_address: Optional[str] = None
) -> Optional[Union[float, List[Dict[str, Any]]]]:
    client = await get_client()
    return await client.get_token_accounts_by_owner(owner, token_address)


async def getSignaturesForAddress(address: str, limit: int = 1000) -> Optional[List[str]]:
    client = await get_client()
    return await client.get_signatures_for_address(address, limit)


async def parseTransactions(
        signatures: List[str],
        token_address: Optional[str] = None,
        time_filter: Optional[float] = None,
        get_user_account: bool = False,
        user_account: Optional[str] = None,
        native: bool = False
) -> Optional[Union[str, Tuple[List[Dict], Dict[str, int]]]]:
    client = await get_client()
    return await client.parse_transactions(
        signatures, token_address, time_filter, get_user_account, user_account, native
    )