# evm-dex-arb-scanner

Asynchronous EVM DEX price scanner built with Python and `web3.py`. Concurrently queries on-chain liquidity pools across **Uniswap V3** and **Aerodrome** on **Base Mainnet** to detect cross-DEX price discrepancies in real time.

## Architecture & Features
- **Concurrent RPC Execution:** Uses `asyncio.gather` to fetch block state and multi-DEX quotes simultaneously with minimal latency.
- **Direct Smart Contract Quoting:** Interacts directly with Uniswap V3 `QuoterV2` and Aerodrome `Router` contracts via `eth_call` (zero third-party aggregator dependencies).
- **Configurable Thresholds:** Adjustable trade size (`ETH`) and minimum spread percentage alerts.

## Quickstart

```bash
git clone https://github.com
cd evm-dex-arb-scanner
pip install -r requirements.txt
python scanner.py
```

*(Optional)* Set a custom low-latency RPC endpoint via `.env`:
```env
BASE_RPC_URL=https://alchemy.com
```

## Example Output

```text
17:48:12 | INFO | Connected to Base Mainnet | Scanning every 2.0s...
17:48:13 | INFO | Block #60014576 | Size: 1.0 ETH | UniV3: \$1,638.73 | Aero: \$1,632.38 | Spread: 0.3894%
17:48:13 | WARNING | ARB OPPORTUNITY DETECTED | Gross Profit: \$6.36 USDC | Route: Buy Aerodrome -> Sell Uniswap V3
17:48:15 | INFO | Block #60014587 | Size: 1.0 ETH | UniV3: \$1,638.06 | Aero: \$1,632.38 | Spread: 0.3484%
```
