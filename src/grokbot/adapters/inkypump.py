from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from grokbot.abi import decode_uint, pad32, selector, words
from grokbot.adapters.base import LaunchpadAdapter, LiveTradingDisabled
from grokbot.events import (
    INKY_LAUNCH_CREATED,
    INKY_LAUNCH_METADATA,
    INKY_TRADE,
    parse_inkypump_launch_created,
    parse_inkypump_launch_metadata,
    parse_inkypump_trade,
)
from grokbot.models import Holder, PriceQuote, Progress, Socials, SwapQuote, Token, Trade
from grokbot.rpc import JsonRpc, RpcError


class InkyPumpAdapter(LaunchpadAdapter):
    name = "inkypump"
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
        self.chain_id = int(config.get("chain_id", 57073))
        self.hook = config["hook"]
        self.view = config.get("launch_view_module", "")
        self.weth = config.get("weth", "")
        self.poll = poll or {}
        self._seen: set[int] = set()
        self._cursor: int | None = None
        self._meta_cache: dict[int, Any] = {}
        self._token_to_launch: dict[str, int] = {}

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
            address=self.hook,
            topics=[[INKY_LAUNCH_CREATED, INKY_LAUNCH_METADATA]],
            from_block=start,
            to_block=head,
            chunk=int(self.poll.get("log_chunk_blocks", 1500)),
            min_chunk=int(self.poll.get("min_chunk_blocks", 50)),
        )
        created: dict[int, Any] = {}
        metadata: dict[int, Any] = {}
        for log in logs:
            t0 = (log.get("topics") or ["0x"])[0].lower()
            try:
                if t0 == INKY_LAUNCH_CREATED:
                    ev = parse_inkypump_launch_created(log)
                    created[ev.launch_id] = ev
                    self._token_to_launch[ev.token.lower()] = ev.launch_id
                elif t0 == INKY_LAUNCH_METADATA:
                    md = parse_inkypump_launch_metadata(log)
                    metadata[md.launch_id] = md
                    self._meta_cache[md.launch_id] = md
            except ValueError:
                continue
        now_ts = int(time.time())
        try:
            now_ts = await self.rpc.get_block_timestamp(head)
        except RpcError:
            pass
        for launch_id, ev in created.items():
            if launch_id in self._seen:
                continue
            self._seen.add(launch_id)
            yield await self._hydrate(ev, metadata.get(launch_id), now_ts)

    async def _hydrate(self, ev, md, now_ts: int) -> Token:
        name = md.name if md else ""
        symbol = md.ticker if md else ""
        desc = md.description if md else ""
        image = md.image_url if md else ""
        socials = Socials(
            twitter=md.twitter if md else "",
            telegram=md.telegram if md else "",
            website=md.website if md else "",
        )
        trades: list[Trade] = []
        try:
            trades = await self.get_trades(ev.token)
        except RpcError:
            pass
        unique_buyers = len({t.trader.lower() for t in trades if t.side == "buy"})
        buy_vol = sum(t.quote_amount for t in trades if t.side == "buy")
        sell_vol = sum(t.quote_amount for t in trades if t.side == "sell")
        net = max(0, buy_vol - sell_vol)
        progress_pct = (net / ev.target_raise * 100.0) if ev.target_raise else 0.0
        age = 0.0
        if ev.block_number:
            try:
                ts = await self.rpc.get_block_timestamp(ev.block_number)
                if ts:
                    age = max(0.0, (now_ts - ts) / 60.0)
            except RpcError:
                pass
        has_meta = bool(name and symbol)
        risk = 0.0
        if not has_meta:
            risk += 0.3
        if not socials.any():
            risk += 0.1
        return Token(
            chain_id=self.chain_id,
            launchpad=self.name,
            address=ev.token,
            name=name,
            symbol=symbol,
            description=desc,
            image=image,
            socials=socials,
            creator=ev.creator,
            progress_pct=min(100.0, progress_pct),
            unique_buyers=unique_buyers,
            age_minutes=age,
            has_metadata=has_meta,
            risk_score=min(1.0, risk),
            quote_token=self.weth,
            pair=self.hook,
            pool=self.hook,
            launch_id=ev.launch_id,
            factory=self.hook,
            block_number=ev.block_number,
            tx_hash=ev.tx_hash,
            extra={"target_raise": ev.target_raise},
        )

    async def get_token(self, address: str) -> Token:
        launch_id = self._token_to_launch.get(address.lower())
        md = self._meta_cache.get(launch_id) if launch_id is not None else None
        return Token(
            chain_id=self.chain_id,
            launchpad=self.name,
            address=address,
            name=md.name if md else "",
            symbol=md.ticker if md else "",
            description=md.description if md else "",
            image=md.image_url if md else "",
            socials=Socials(
                twitter=md.twitter if md else "",
                telegram=md.telegram if md else "",
                website=md.website if md else "",
            ),
            has_metadata=bool(md and md.name and md.ticker),
            quote_token=self.weth,
            launch_id=launch_id,
            factory=self.hook,
        )

    async def get_metadata(self, address: str) -> dict[str, Any]:
        t = await self.get_token(address)
        return {
            "name": t.name,
            "symbol": t.symbol,
            "description": t.description,
            "logo": t.image,
        }

    async def get_socials(self, address: str) -> dict[str, str]:
        t = await self.get_token(address)
        return {
            "twitter": t.socials.twitter,
            "telegram": t.socials.telegram,
            "discord": t.socials.discord,
            "website": t.socials.website,
            "farcaster": t.socials.farcaster,
        }

    async def get_holders(self, address: str) -> list[Holder]:
        return []  # curve custody; unique buyers come from Trade events

    async def get_trades(self, address: str) -> list[Trade]:
        launch_id = self._token_to_launch.get(address.lower())
        head = await self.rpc.block_number()
        lookback = int(self.poll.get("trade_lookback_blocks", 8000))
        start = max(0, head - lookback)
        topic_launch = "0x" + pad32(launch_id or 0).hex() if launch_id is not None else None
        topics: list[Any] = [INKY_TRADE]
        if topic_launch is not None:
            topics = [INKY_TRADE, topic_launch]
        logs = await self.rpc.get_logs_chunked(
            address=self.hook,
            topics=topics,
            from_block=start,
            to_block=head,
            chunk=int(self.poll.get("log_chunk_blocks", 1500)),
        )
        out: list[Trade] = []
        for log in logs:
            try:
                ev = parse_inkypump_trade(log)
            except ValueError:
                continue
            if launch_id is not None and ev.launch_id != launch_id:
                continue
            out.append(
                Trade(
                    tx_hash=ev.tx_hash,
                    block_number=ev.block_number,
                    trader=ev.trader,
                    side=ev.side,
                    quote_amount=ev.eth_amount,
                    token_amount=ev.token_amount,
                )
            )
        return out

    async def get_progress(self, address: str) -> Progress:
        t = await self.get_token(address)
        trades = await self.get_trades(address)
        buy_vol = sum(x.quote_amount for x in trades if x.side == "buy")
        sell_vol = sum(x.quote_amount for x in trades if x.side == "sell")
        target = int((t.extra or {}).get("target_raise") or 0)
        if not target and t.launch_id is not None:
            # target is on LaunchCreated; we may not have extra if get_token was used
            target = 0
        net = max(0, buy_vol - sell_vol)
        pct = (net / target * 100.0) if target else 0.0
        return Progress(progress_pct=min(100.0, pct), paired_principal=net, threshold=target)

    async def get_price(self, address: str) -> PriceQuote:
        trades = await self.get_trades(address)
        if not trades:
            return PriceQuote(price_in_quote=0.0, quote_token=self.weth)
        last = trades[-1]
        price = last.quote_amount / last.token_amount if last.token_amount else 0.0
        return PriceQuote(price_in_quote=price, quote_token=self.weth)

    async def quote_buy(self, address: str, amount_wei: int) -> SwapQuote:
        """Use LaunchViewModule.previewBuyLocal when we can; else last-trade estimate."""
        launch_id = self._token_to_launch.get(address.lower())
        if launch_id is not None and self.view:
            try:
                quoted = await self._preview_buy(launch_id, amount_wei)
                if quoted is not None:
                    return quoted
            except RpcError:
                pass
        price = await self.get_price(address)
        out = int(amount_wei / price.price_in_quote) if price.price_in_quote else 0
        return SwapQuote(amount_in=amount_wei, amount_out=out)

    async def _preview_buy(self, launch_id: int, amount_wei: int) -> SwapQuote | None:
        # Hook wrapper: previewBuy(uint256 launchId, uint256 ethIn) — docs.inkyswap.com ABI
        from grokbot.abi import hex_to_bytes

        sel = selector("previewBuy(uint256,uint256)")
        data = sel + pad32(launch_id).hex() + pad32(amount_wei).hex()
        result = await self.rpc.eth_call(self.hook, data)
        ws = words(hex_to_bytes(result))
        if not ws:
            return None
        return SwapQuote(amount_in=amount_wei, amount_out=decode_uint(ws[0]))

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
        raise LiveTradingDisabled("live InkyPump buys are not implemented")

    async def sell(self, address: str, amount_tokens: int, **kwargs: Any) -> dict[str, Any]:
        if self.paper:
            return {
                "mode": "paper",
                "sent": False,
                "adapter": self.name,
                "token": address,
                "amount_tokens": amount_tokens,
            }
        raise LiveTradingDisabled("live InkyPump sells are not implemented")
