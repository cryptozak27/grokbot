# grokbot

Chain-agnostic EVM port of the five-agent Grok memecoin pipeline (architecture from [@zostaff's "Five Grok Agents on Pump.fun"](https://github.com/zostaff/grokbot-pumpfun)). First live adapters: **pons** on Robinhood Chain and **InkyPump** on Ink. Default `EXECUTION_MODE=paper`: monitor, filter, score, log. **No live buys. No private keys.**

This does not beat the casino. Most launches never graduate (on the order of **1–2%**). Paper mode exists so you can watch the funnel without sending a transaction.

## Architecture

```
new logs (eth_getLogs, bounded chunks)
        │
        ▼
1. Launch monitor (code)     cheap filters: metadata, unique buyers, age, progress, risk
        │
        ▼
2. Token analyzer (code)     holders, trades, insider %, socials, curve/pool health
        │
        ▼
3. Auditor (LLM grok-4-fast) coordinated buys / wash / dump risk
                             parse error = pessimistic REJECT
        │
        ▼
4. Narrative (LLM grok-4-fast, temperature 0, JSON only)
5. Timing    (LLM grok-4-fast, cached 15–30 min, not per-token)
        │
        ▼
6. Scoring matrix (CODE)     weighted score; skip below threshold
        │
        ▼
7. Checker (LLM grok-4)      adversarial, reasons NOT to buy
                             parse error = approve false
        │
        ▼
8. Risk manager              max position, daily loss, max 10 trades/day, max 3 open,
                             size shrinks near the loss limit
        │
        ▼
9. Execution                 paper: log intended trade only (never eth_send*)
10. JSONL log                logs/pipeline.jsonl  — buy / skip / close + full context
```

`LaunchpadAdapter` is the plug-in surface (`stream_launches`, token/metadata/socials, holders/trades, progress, price, quote, buy/sell). Clanker (Base) and four.meme (BNB) are stubs: config + interface, no fake live data.

Normalized `Token` fields: `chain_id`, `launchpad`, `address`, `name`, `symbol`, `description`, `image`, `socials`, `creator`, `progress_pct`, `unique_buyers`, `age_minutes`, `has_metadata`, `risk_score`, `quote_token`, `pair`/`pool`.

## Setup

Python 3.12+.

```bash
cd /workspace/grokbot
python3 -m pip install -e ".[dev]"
cp .env.example .env   # add GROK_API_KEY for real LLM stages; never add a private key
```

Without `GROK_API_KEY` the CLI uses a dry scripted LLM (auditor/checker fail closed — you will only see filter/skip traffic, which is intended).

## Run paper mode

PONS (Robinhood) **and** InkyPump (Ink), one poll then exit:

```bash
make run-paper
# same as:
python3 -m grokbot run --mode paper --once
```

One launchpad:

```bash
python3 -m grokbot run --mode paper --launchpad pons --once
python3 -m grokbot run --mode paper --launchpad inkypump --once
```

Forever (Ctrl-C to stop):

```bash
python3 -m grokbot run --mode paper
```

JSONL: `logs/pipeline.jsonl`. Lint / tests:

```bash
make lint
make test
```

Live `buy`/`sell` is **not implemented**. `EXECUTION_MODE=live` is refused. JSON-RPC client rejects `eth_send*`.

## Verified chain facts

### pons / Robinhood Chain

From [docs.ponsfamily.com](https://docs.ponsfamily.com/) and [github.com/ponsdotdev/ponsfamily](https://github.com/ponsdotdev/ponsfamily):

| | |
| --- | --- |
| Chain ID | `4663` |
| RPC | `https://rpc.mainnet.chain.robinhood.com` |
| Explorer | `https://robinhoodchain.blockscout.com` |
| WETH | `0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73` |
| V1 factory (docs: "active") | `0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB` start block **8991118** |
| V1 locker | `0x736D76699C26D0d966744cAe304C000d471f7F35` |
| Legacy factory | `0x0c37a24F5D23A486FA692d1500881d698B1F77a4` start **8600612** |
| V2 factory (GitHub, live) | `0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e` |
| TokenLaunched topic0 (V1) | `0xdb51ea9ad51ab453a65a4cb7e60c3cb378c9501bb002609f8f97778fb6c4235a` |
| Swap topic0 (Uni V3) | `0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67` |

V1 tokens self-describe onchain (`name`, `symbol`, `logo`, `description`, `liquidityPool`, `socials`). Graduation ~**4.2 ETH** WETH paired, **same pool, no migrate**. Wide `eth_getLogs` times out — backfill is chunked.

V2 uses a bonding curve then Uniswap V4. Event layout differs (`TokenLaunched(address,address,address,address,uint256,uint256)`). The adapter parses both. V2 start block is **not** in official pons docs; paper mode uses head-lookback.

### InkyPump / Ink

From [docs.inkyswap.com](https://docs.inkyswap.com/):

| | |
| --- | --- |
| Chain ID | `57073` |
| RPC | `https://rpc-gel.inkonchain.com` |
| Explorer | `https://explorer.inkonchain.com` |
| V2 hook proxy (only entry) | `0x4cC8F6d5B7cE150CCC0A9B7664532B1283b96AC4` |
| LaunchViewModule | `0xce83E3659251116d114Ec1CA729ffB49B99403c3` |
| WETH | `0x4200000000000000000000000000000000000006` |
| PoolManager | `0x360E68faCcca8cA495c1B759Fd9EEe466db9FB32` |
| Universal Router | `0x551134e92e537cEAa217c2ef63210Af3CE96a065` |

Linear bonding curve, target **1–5 ETH**, then Uniswap V4. Stream `LaunchCreated` + `LaunchMetadata`; trades from `Trade`. Hook start block is unpublished; paper mode uses head-lookback.

## Add a chain

1. Implement `LaunchpadAdapter` in `src/grokbot/adapters/` (see `pons.py` / `inkypump.py`).
2. Add a block under `launchpads:` in `config.yaml` (chain_id, rpc, factory/hook, start_block if known).
3. Register it in `adapters/__init__.py` `build_adapters`.
4. Cover event parsing with a fixture log (see `tests/test_events.py`).
5. Keep `buy`/`sell` paper no-ops until you have a signed-tx path you actually want — and never commit keys.

Clanker (Base, factory `0xE85A59c628F7d27878ACeB4bf3b35733630083a9` v4.0.0) and four.meme (BNB) are already stubbed so you can fill them in without changing the pipeline.

## Honest risk

Memecoin launchpads are negative-EV for most wallets. Graduation is rare. Filters and Grok agents drop the obvious garbage; they do not create edge. Paper mode is the product. If you turn this into live size, assume you can lose the entire hot wallet.
