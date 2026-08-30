from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from grokbot.abi import (
    PONS_V1_TOKEN_LAUNCHED,
    PONS_V2_CURVE_BUY,
    PONS_V2_CURVE_SELL,
    PONS_V2_TOKEN_LAUNCHED,
    UNISWAP_V3_SWAP,
    decode_abi_strings,
    decode_address,
    decode_uint,
    words,
)
from grokbot.adapters.base import LaunchpadAdapter, LiveTradingDisabled
from grokbot.events import (
    parse_pons_token_launched,
    parse_pons_v2_curve_trade,
    parse_uniswap_v3_swap,
)
from grokbot.models import Holder, PriceQuote, Progress, Socials, SwapQuote, Token, Trade
from grokbot.rpc import JsonRpc, RpcError, read_string


class PonsAdapter(LaunchpadAdapter):
    name = "pons"
    stub = False

    def __init__(
        self,
        rpc: JsonRpc,
        config: dict[str, Any],
        *,
        paper: bool = True,
        poll: dict[str, Any] | None = None,
    ) -> None:
        self.rpc = rpc
        self.config = config
        self.paper = paper
        self.chain_id = int(config.get("chain_id", 4663))
        self.factory = config["factory"]
        self.legacy_factory = config.get("legacy_factory")
        self.v2_factory = config.get("v2_factory")
        self.weth = config.get("weth", "")
        self.locker = config.get("locker", "")
        self.poll = poll or {}
        self._seen: set[str] = set()
        self._cursor: int | None = None

    def _factories(self) -> list[str]:
        out = [self.factory]
        if self.legacy_factory:
            out.append(self.legacy_factory)
        if self.v2_factory:
            out.append(self.v2_factory)
        return out

    async def _window(self) -> tuple[int, int]:
        head = await self.rpc.block_number()
        lookback = int(self.poll.get("lookback_blocks", 4000))
        if self._cursor is None:
            start = max(0, head - lookback)
        else:
            start = self._cursor + 1
        self._cursor = head
        return start, head

    async def stream_launches(self) -> AsyncIterator[Token]:
        start, head = await self._window()
        if start > head:
            return
        logs = await self.rpc.get_logs_chunked(
            address=self._factories(),
            topics=[[PONS_V1_TOKEN_LAUNCHED, PONS_V2_TOKEN_LAUNCHED]],
            from_block=start,
            to_block=head,
            chunk=int(self.poll.get("log_chunk_blocks", 1500)),
            min_chunk=int(self.poll.get("min_chunk_blocks", 50)),
        )
        now_ts = int(time.time())
        try:
            now_ts = await self.rpc.get_block_timestamp(head)
        except RpcError:
            pass
        for log in logs:
            try:
                launch = parse_pons_token_launched(log)
            except ValueError:
                continue
            key = launch.token.lower()
            if key in self._seen:
                continue
            self._seen.add(key)
            token = await self._hydrate(launch, now_ts=now_ts)
            yield token

    async def _hydrate(self, launch, now_ts: int) -> Token:
        meta = await self.get_metadata(launch.token)
        socials_d = await self.get_socials(launch.token)
        socials = Socials(
            twitter=socials_d.get("twitter", ""),
            telegram=socials_d.get("telegram", ""),
            discord=socials_d.get("discord", ""),
            website=socials_d.get("website", ""),
            farcaster=socials_d.get("farcaster", ""),
        )
        progress = Progress(progress_pct=0.0)
        try:
            progress = await self.get_progress(launch.token)
        except RpcError:
            pass
        trades: list[Trade] = []
        try:
            trades = await self.get_trades(launch.token)
        except RpcError:
            pass
        unique_buyers = len({t.trader.lower() for t in trades if t.side == "buy"})
        age = 0.0
        if launch.block_number:
            try:
                ts = await self.rpc.get_block_timestamp(launch.block_number)
                if ts:
                    age = max(0.0, (now_ts - ts) / 60.0)
            except RpcError:
                pass
        pool = launch.pool or meta.get("liquidity_pool", "")
        name = meta.get("name") or ""
        symbol = meta.get("symbol") or ""
        desc = meta.get("description") or ""
        image = meta.get("logo") or ""
        has_meta = bool(name and symbol)
        risk = 0.0
        if not has_meta:
            risk += 0.3
        if not socials.any():
            risk += 0.1
        return Token(
            chain_id=self.chain_id,
            launchpad=self.name,
            address=launch.token,
            name=name,
            symbol=symbol,
            description=desc,
            image=image,
            socials=socials,
            creator=launch.deployer,
            progress_pct=progress.progress_pct,
            unique_buyers=unique_buyers,
            age_minutes=age,
            has_metadata=has_meta,
            risk_score=min(1.0, risk),
            quote_token=launch.pair_token or self.weth,
            pair=pool,
            pool=pool,
            factory=launch.factory,
            block_number=launch.block_number,
            tx_hash=launch.tx_hash,
            extra={
                "version": launch.version,
                "curve": launch.curve,
                "dex_factory": launch.dex_factory,
                "graduation_threshold": launch.graduation_threshold,
                "initial_buy_amount": launch.initial_buy_amount,
                "graduated": progress.graduated,
            },
        )

    async def get_token(self, address: str) -> Token:
        meta = await self.get_metadata(address)
        socials_d = await self.get_socials(address)
        progress = await self.get_progress(address)
        return Token(
            chain_id=self.chain_id,
            launchpad=self.name,
            address=address,
            name=meta.get("name", ""),
            symbol=meta.get("symbol", ""),
            description=meta.get("description", ""),
            image=meta.get("logo", ""),
            socials=Socials(
                **{
                    k: socials_d.get(k, "")
                    for k in ("twitter", "telegram", "discord", "website", "farcaster")
                }
            ),
            progress_pct=progress.progress_pct,
            has_metadata=bool(meta.get("name") and meta.get("symbol")),
            quote_token=self.weth,
            pair=meta.get("liquidity_pool", ""),
            pool=meta.get("liquidity_pool", ""),
        )

    async def get_metadata(self, address: str) -> dict[str, Any]:
        name = await read_string(self.rpc, address, "name()")
        symbol = await read_string(self.rpc, address, "symbol()")
        logo = await read_string(self.rpc, address, "logo()")
        description = await read_string(self.rpc, address, "description()")
        pool = ""
        try:
            raw = await self.rpc.call_fn(address, "liquidityPool()")
            if raw:
                pool = decode_address(raw[-32:] if len(raw) >= 32 else raw)
        except RpcError:
            pass
        return {
            "name": name,
            "symbol": symbol,
            "logo": logo,
            "description": description,
            "liquidity_pool": pool,
        }

    async def get_socials(self, address: str) -> dict[str, str]:
        keys = ["twitter", "telegram", "discord", "website", "farcaster"]
        try:
            raw = await self.rpc.call_fn(address, "socials()")
            values = decode_abi_strings(raw, 5) if raw else []
        except RpcError:
            values = []
        values += [""] * 5
        return dict(zip(keys, values[:5], strict=False))

    async def get_holders(self, address: str) -> list[Holder]:
        """Approximate holders from recent Transfer logs (bounded). Not a full index."""
        try:
            head = await self.rpc.block_number()
        except RpcError:
            return []
        lookback = int(self.poll.get("trade_lookback_blocks", 8000))
        from grokbot.abi import ERC20_TRANSFER

        try:
            logs = await self.rpc.get_logs_chunked(
                address=address,
                topics=[ERC20_TRANSFER],
                from_block=max(0, head - lookback),
                to_block=head,
                chunk=int(self.poll.get("log_chunk_blocks", 1500)),
            )
        except RpcError:
            return []
        balances: dict[str, int] = {}
        from grokbot.abi import hex_to_bytes

        for log in logs:
            topics = log.get("topics") or []
            if len(topics) < 3:
                continue
            src = decode_address(topics[1])
            dst = decode_address(topics[2])
            data_words = words(hex_to_bytes(log.get("data") or "0x"))
            amount = decode_uint(data_words[0]) if data_words else 0
            if src != "0x0000000000000000000000000000000000000000":
                balances[src] = balances.get(src, 0) - amount
            balances[dst] = balances.get(dst, 0) + amount
        positive = [(a, b) for a, b in balances.items() if b > 0]
        total = sum(b for _, b in positive) or 1
        positive.sort(key=lambda x: x[1], reverse=True)
        return [Holder(address=a, balance=b, pct=b / total) for a, b in positive[:50]]

    async def get_trades(self, address: str) -> list[Trade]:
        token = address
        try:
            meta = await self.get_metadata(address)
            pool = meta.get("liquidity_pool") or ""
        except RpcError:
            pool = ""
        head = await self.rpc.block_number()
        lookback = int(self.poll.get("trade_lookback_blocks", 8000))
        start = max(0, head - lookback)
        trades: list[Trade] = []
        if pool:
            try:
                logs = await self.rpc.get_logs_chunked(
                    address=pool,
                    topics=[UNISWAP_V3_SWAP],
                    from_block=start,
                    to_block=head,
                    chunk=int(self.poll.get("log_chunk_blocks", 1500)),
                )
                pair = self.weth
                for log in logs:
                    try:
                        swap = parse_uniswap_v3_swap(log)
                    except ValueError:
                        continue
                    side = swap.side_for_token(token, pair)
                    quote_amt = abs(
                        swap.amount1 if int(token, 16) < int(pair, 16) else swap.amount0
                    )
                    token_amt = abs(
                        swap.amount0 if int(token, 16) < int(pair, 16) else swap.amount1
                    )
                    trades.append(
                        Trade(
                            tx_hash=swap.tx_hash,
                            block_number=swap.block_number,
                            trader=swap.recipient,
                            side=side,
                            quote_amount=quote_amt,
                            token_amount=token_amt,
                        )
                    )
            except RpcError:
                pass
        # V2 curve: TokenLaunched.curve stored as pool for v2; also scan CurveBuy/Sell
        try:
            logs = (
                await self.rpc.get_logs_chunked(
                    address=pool or None,
                    topics=[[PONS_V2_CURVE_BUY, PONS_V2_CURVE_SELL]],
                    from_block=start,
                    to_block=head,
                    chunk=int(self.poll.get("log_chunk_blocks", 1500)),
                )
                if pool
                else []
            )
            for log in logs:
                try:
                    ct = parse_pons_v2_curve_trade(log)
                except ValueError:
                    continue
                trades.append(
                    Trade(
                        tx_hash=ct.tx_hash,
                        block_number=ct.block_number,
                        trader=ct.trader,
                        side=ct.side,
                        quote_amount=ct.quote_amount,
                        token_amount=ct.token_amount,
                    )
                )
        except RpcError:
            pass
        return trades

    async def get_progress(self, address: str) -> Progress:
        """graduationStatus(token) on the factory that launched it. Same pool, no migrate."""
        for factory in self._factories():
            try:
                raw = await self.rpc.call_fn(factory, "graduationStatus(address)", address)
            except RpcError:
                continue
            ws = words(raw)
            if len(ws) < 3:
                continue
            paired = decode_uint(ws[0])
            threshold = decode_uint(ws[1])
            graduated = decode_uint(ws[2]) != 0
            pct = (paired / threshold * 100.0) if threshold else 0.0
            return Progress(
                progress_pct=min(100.0, pct),
                paired_principal=paired,
                threshold=threshold,
                graduated=graduated,
            )
        return Progress(progress_pct=0.0)

    async def get_price(self, address: str) -> PriceQuote:
        meta = await self.get_metadata(address)
        pool = meta.get("liquidity_pool") or ""
        if not pool:
            return PriceQuote(price_in_quote=0.0, quote_token=self.weth)
        try:
            raw = await self.rpc.call_fn(pool, "slot0()")
            ws = words(raw)
            if not ws:
                return PriceQuote(price_in_quote=0.0, quote_token=self.weth)
            sqrt_price_x96 = decode_uint(ws[0])
            ratio = sqrt_price_x96 / (2**96)
            token1_per_token0 = ratio * ratio
            is_token0 = int(address, 16) < int(self.weth, 16)
            price = (
                token1_per_token0
                if is_token0
                else (1 / token1_per_token0 if token1_per_token0 else 0)
            )
            return PriceQuote(price_in_quote=price, quote_token=self.weth)
        except (RpcError, ZeroDivisionError):
            return PriceQuote(price_in_quote=0.0, quote_token=self.weth)

    async def quote_buy(self, address: str, amount_wei: int) -> SwapQuote:
        # Paper path: do not hit a router; return a placeholder quote from spot price.
        price = await self.get_price(address)
        out = int(amount_wei / price.price_in_quote) if price.price_in_quote else 0
        return SwapQuote(amount_in=amount_wei, amount_out=out)

    async def quote_sell(self, address: str, amount_tokens: int) -> SwapQuote:
        price = await self.get_price(address)
        out = int(amount_tokens * price.price_in_quote)
        return SwapQuote(amount_in=amount_tokens, amount_out=out)

    async def buy(self, address: str, amount_wei: int, **kwargs: Any) -> dict[str, Any]:
        if self.paper:
            return {
                "mode": "paper",
                "sent": False,
                "adapter": self.name,
                "token": address,
                "amount_wei": amount_wei,
            }
        raise LiveTradingDisabled("live PONS buys are not implemented")

    async def sell(self, address: str, amount_tokens: int, **kwargs: Any) -> dict[str, Any]:
        if self.paper:
            return {
                "mode": "paper",
                "sent": False,
                "adapter": self.name,
                "token": address,
                "amount_tokens": amount_tokens,
            }
        raise LiveTradingDisabled("live PONS sells are not implemented")
