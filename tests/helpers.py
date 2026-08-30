from grokbot.abi import encode_address, encode_string_tuple, pad32


def log(
    address: str,
    topics: list[str],
    data: bytes = b"",
    block: int = 100,
    tx: str = "0x" + "ab" * 32,
) -> dict:
    return {
        "address": address,
        "topics": topics,
        "data": "0x" + data.hex() if data else "0x",
        "blockNumber": hex(block),
        "transactionHash": tx,
        "logIndex": "0x0",
    }


def addr_topic(address: str) -> str:
    return "0x" + encode_address(address).hex()


def uint_topic(value: int) -> str:
    return "0x" + pad32(value).hex()


def static_data(*parts: int | str) -> bytes:
    out = b""
    for p in parts:
        out += encode_address(p) if isinstance(p, str) else pad32(p)
    return out


def string_tuple_data(values: list[str]) -> bytes:
    return encode_string_tuple(values)
