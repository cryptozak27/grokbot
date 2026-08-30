"""Lightweight JSON-RPC client with bounded eth_getLogs chunking."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from grokbot.abi import hex_to_bytes, selector


class RpcError(RuntimeError):
    pass


class JsonRpc:
    def __init__(
        self,
        url: str,
        timeout: float = 20.0,
        client: httpx.AsyncClient | None = None,
        chain_id: int | None = None,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None
        self.chain_id = chain_id
        self.sent_methods: list[str] = []

    async def _client_obj(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def call(self, method: str, params: list[Any] | None = None) -> Any:
        self.sent_methods.append(method)
        if method.startswith("eth_send"):
            raise RpcError(f"refusing broadcast RPC method {method}")
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        client = await self._client_obj()
        try:
            resp = await client.post(self.url, json=payload)
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPError as exc:
            raise RpcError(f"{method} failed: {exc}") from exc
        if "error" in body and body["error"]:
            raise RpcError(f"{method}: {body['error']}")
        return body.get("result")

    async def block_number(self) -> int:
        result = await self.call("eth_blockNumber")
        return int(result, 16)

    async def get_block_timestamp(self, block: int | str = "latest") -> int:
        tag = hex(block) if isinstance(block, int) else block
        result = await self.call("eth_getBlockByNumber", [tag, False])
        if not result:
            return 0
        return int(result.get("timestamp", "0x0"), 16)

    async def get_logs(
        self,
        *,
        address: str | list[str] | None = None,
        topics: list[Any] | None = None,
        from_block: int,
        to_block: int,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
        }
        if address:
            params["address"] = address
        if topics:
            params["topics"] = topics
        result = await self.call("eth_getLogs", [params])
        return result or []

    async def get_logs_chunked(
        self,
        *,
        address: str | list[str] | None = None,
        topics: list[Any] | None = None,
        from_block: int,
        to_block: int,
        chunk: int = 1500,
        min_chunk: int = 50,
    ) -> list[dict[str, Any]]:
        """Backfill in bounded chunks. Public PONS RPC times out on wide ranges."""
        if to_block < from_block:
            return []
        out: list[dict[str, Any]] = []
        start = from_block
        size = max(min_chunk, chunk)
        while start <= to_block:
            end = min(start + size - 1, to_block)
            try:
                out.extend(
                    await self.get_logs(
                        address=address, topics=topics, from_block=start, to_block=end
                    )
                )
                start = end + 1
            except RpcError:
                if size <= min_chunk or (end - start) < min_chunk:
                    # skip this window rather than fail the whole poll
                    start = end + 1
                    size = chunk
                    continue
                size = max(min_chunk, size // 2)
        return out

    async def eth_call(self, to: str, data: str, block: str = "latest") -> str:
        result = await self.call("eth_call", [{"to": to, "data": data}, block])
        return result or "0x"

    async def call_fn(self, to: str, signature: str, *args: int | str) -> bytes:
        from grokbot.abi import encode_call

        raw = await self.eth_call(to, encode_call(signature, *args))
        return hex_to_bytes(raw)

    async def call_selector(self, to: str, sel: str, *static_args: int | str) -> bytes:
        from grokbot.abi import encode_address, pad32

        data = bytes.fromhex(sel[2:] if sel.startswith("0x") else sel)
        for arg in static_args:
            if isinstance(arg, str):
                data += encode_address(arg)
            else:
                data += pad32(int(arg))
        raw = await self.eth_call(to, "0x" + data.hex())
        return hex_to_bytes(raw)


def decode_string_return(data: bytes) -> str:
    """Decode a single ABI string return (offset+length+bytes) or bytes32."""
    if not data or data == b"\x00":
        return ""
    if len(data) >= 64:
        offset = int.from_bytes(data[0:32], "big")
        if offset == 32 and len(data) >= 64:
            length = int.from_bytes(data[32:64], "big")
            return data[64 : 64 + length].decode("utf-8", errors="replace")
        if offset < len(data):
            length = int.from_bytes(data[offset : offset + 32], "big")
            start = offset + 32
            return data[start : start + length].decode("utf-8", errors="replace")
    # bytes32 fallback
    return data.rstrip(b"\x00").decode("utf-8", errors="replace")


async def read_string(rpc: JsonRpc, address: str, signature: str) -> str:
    try:
        data = await rpc.call_fn(address, signature)
        return decode_string_return(data)
    except RpcError:
        return ""


def unique_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        k = item.lower()
        if k not in seen:
            seen.add(k)
            out.append(item)
    return out


# silence unused import for selector in type checkers
_ = selector
