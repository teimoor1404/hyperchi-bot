import aiohttp
from config import HYPERLIQUID_API_URL

async def get_user_fills(address: str):
    payload = {"type": "userFills", "user": address}
    headers = {"Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(HYPERLIQUID_API_URL, json=payload, headers=headers, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                return []
    except Exception as e:
        print(f"Error fetching fills for {address}: {e}")
        return []

async def get_clearinghouse_state(address: str):
    payload = {"type": "clearinghouseState", "user": address}
    headers = {"Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(HYPERLIQUID_API_URL, json=payload, headers=headers, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                return None
    except Exception as e:
        print(f"Error fetching state for {address}: {e}")
        return None
