import asyncio
import logging
import os
from decimal import Decimal
from dotenv import load_dotenv
from web3 import AsyncWeb3, AsyncHTTPProvider

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dex-arb-scanner")

# Base Mainnet Configuration
RPC_URL = os.getenv("BASE_RPC_URL", "https://base-rpc.publicnode.com")


WETH_ADDRESS = AsyncWeb3.to_checksum_address("0x4200000000000000000000000000000000000006")
USDC_ADDRESS = AsyncWeb3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")

# DEX Contracts on Base
UNISWAP_QUOTER_V2 = AsyncWeb3.to_checksum_address("0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a")
AERODROME_ROUTER = AsyncWeb3.to_checksum_address("0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43")
AERODROME_FACTORY = AsyncWeb3.to_checksum_address("0x420DD381b31aEf6683db6B902084cB0FFECe40Da")

UNISWAP_QUOTER_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
                "internalType": "struct IQuoterV2.QuoteExactInputSingleParams",
                "name": "params",
                "type": "tuple",
            }
        ],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceX96After", "type": "uint160"},
            {"internalType": "uint32", "name": "initializedTicksCrossed", "type": "uint32"},
            {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

AERODROME_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {
                "components": [
                    {"internalType": "address", "name": "from", "type": "address"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "bool", "name": "stable", "type": "bool"},
                    {"internalType": "address", "name": "factory", "type": "address"},
                ],
                "internalType": "struct IRouter.Route[]",
                "name": "routes",
                "type": "tuple[]",
            },
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function",
    }
]


class BaseDexScanner:
    def __init__(self, rpc_url: str, trade_size_eth: float = 1.0, min_spread_pct: float = 0.15):
        self.w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
        self.amount_in_wei = self.w3.to_wei(trade_size_eth, "ether")
        self.trade_size_eth = trade_size_eth
        self.min_spread_pct = Decimal(str(min_spread_pct))

        self.uni_quoter = self.w3.eth.contract(address=UNISWAP_QUOTER_V2, abi=UNISWAP_QUOTER_ABI)
        self.aero_router = self.w3.eth.contract(address=AERODROME_ROUTER, abi=AERODROME_ROUTER_ABI)

    async def get_uniswap_quote(self, fee_tier: int = 500) -> Decimal:
        params = (WETH_ADDRESS, USDC_ADDRESS, self.amount_in_wei, fee_tier, 0)
        result = await self.uni_quoter.functions.quoteExactInputSingle(params).call()
        return Decimal(result[0]) / Decimal(10**6)

    async def get_aerodrome_quote(self) -> Decimal:
        routes = [(WETH_ADDRESS, USDC_ADDRESS, False, AERODROME_FACTORY)]
        amounts = await self.aero_router.functions.getAmountsOut(self.amount_in_wei, routes).call()
        return Decimal(amounts[-1]) / Decimal(10**6)

    async def scan_once(self) -> None:
        try:
            block_num, uni_usdc, aero_usdc = await asyncio.gather(
                self.w3.eth.block_number,
                self.get_uniswap_quote(fee_tier=500),
                self.get_aerodrome_quote(),
            )

            diff = abs(uni_usdc - aero_usdc)
            low_price = min(uni_usdc, aero_usdc)
            spread_pct = (diff / low_price) * Decimal(100)

            direction = (
                "Buy Aerodrome -> Sell Uniswap V3"
                if aero_usdc < uni_usdc
                else "Buy Uniswap V3 -> Sell Aerodrome"
            )

            logger.info(
                f"Block #{block_num} | Size: {self.trade_size_eth} ETH | "
                f"UniV3: ${uni_usdc:,.2f} | Aero: ${aero_usdc:,.2f} | "
                f"Spread: {spread_pct:.4f}%"
            )

            if spread_pct >= self.min_spread_pct:
                logger.warning(
                    f"ARB OPPORTUNITY DETECTED | Gross Profit: ${diff:,.2f} USDC | Route: {direction}"
                )

        except Exception as exc:
            logger.error(f"RPC/Quote fetch error: {exc}")

    async def run(self, poll_interval: float = 2.0) -> None:
        if not await self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {RPC_URL}")

        logger.info(f"Connected to Base Mainnet | Scanning every {poll_interval}s...")
        while True:
            await self.scan_once()
            await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    scanner = BaseDexScanner(rpc_url=RPC_URL, trade_size_eth=1.0, min_spread_pct=0.10)
    try:
        asyncio.run(scanner.run(poll_interval=2.0))
    except KeyboardInterrupt:
        logger.info("Scanner stopped gracefully.")
