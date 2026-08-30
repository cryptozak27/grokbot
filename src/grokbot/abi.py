"""Minimal ABI helpers. keccak via pycryptodome; no web3.py required."""

from __future__ import annotations

from Crypto.Hash import keccak

ZERO_ADDRESS = "0x" + "0" * 40


def keccak256(data: bytes) -> bytes:
    k = keccak.new(digest_bits=256)
    k.update(data)
    return k.digest()


def topic0(signature: str) -> str:
    return "0x" + keccak256(signature.encode("ascii")).hex()


def selector(signature: str) -> str:
    return "0x" + keccak256(signature.encode("ascii")).hex()[:8]


def normalize_address(value: str | None) -> str:
    if not value:
        return ZERO_ADDRESS
    v = value.lower()
    if v.startswith("0x"):
        v = v[2:]
    v = v[-40:].rjust(40, "0")
    return "0x" + v


def pad32(value: int | str | bytes) -> bytes:
    if isinstance(value, bytes):
        if len(value) > 32:
            raise ValueError("value longer than 32 bytes")
        return value.rjust(32, b"\x00")
    if isinstance(value, str):
        h = value[2:] if value.startswith("0x") else value
        raw = bytes.fromhex(h)
        return raw.rjust(32, b"\x00")
    if value < 0:
        value = value & ((1 << 256) - 1)
    return value.to_bytes(32, "big")


def encode_address(addr: str) -> bytes:
    return pad32(normalize_address(addr))


def decode_uint(word: bytes) -> int:
    return int.from_bytes(word[-32:], "big")


def decode_int256(word: bytes) -> int:
    v = int.from_bytes(word[-32:], "big")
    if v >= 1 << 255:
        v -= 1 << 256
    return v


def decode_address(word: bytes | str) -> str:
    if isinstance(word, str):
        h = word[2:] if word.startswith("0x") else word
        return normalize_address("0x" + h[-40:])
    return normalize_address("0x" + word[-20:].hex())


def hex_to_bytes(data: str) -> bytes:
    h = data[2:] if data.startswith("0x") else data
    if len(h) % 2:
        h = "0" + h
    return bytes.fromhex(h or "00")


def words(data: bytes) -> list[bytes]:
    if not data:
        return []
    out = []
    for i in range(0, len(data), 32):
        chunk = data[i : i + 32]
        if len(chunk) < 32:
            chunk = chunk + b"\x00" * (32 - len(chunk))
        out.append(chunk)
    return out


def decode_string_at(data: bytes, offset: int) -> str:
    if offset + 32 > len(data):
        return ""
    length = int.from_bytes(data[offset : offset + 32], "big")
    start = offset + 32
    end = start + length
    if end > len(data):
        end = len(data)
    return data[start:end].decode("utf-8", errors="replace")


def decode_abi_strings(data: bytes, count: int) -> list[str]:
    """Decode `count` dynamic ABI strings packed as a tuple of strings."""
    if len(data) < 32 * count:
        return [""] * count
    result = []
    for i in range(count):
        rel = int.from_bytes(data[i * 32 : (i + 1) * 32], "big")
        result.append(decode_string_at(data, rel) if rel < len(data) else "")
    return result


def encode_string(s: str) -> bytes:
    raw = s.encode("utf-8")
    length = pad32(len(raw))
    padded = raw + b"\x00" * ((32 - (len(raw) % 32)) % 32)
    return length + padded


def encode_string_tuple(values: list[str]) -> bytes:
    n = len(values)
    head = b""
    tail = b""
    offset = 32 * n
    bodies = [encode_string(v) for v in values]
    for body in bodies:
        head += pad32(offset)
        offset += len(body)
        tail += body
    return head + tail


def encode_call(signature: str, *static_args: int | str) -> str:
    """Encode a call with only static args (address / uint)."""
    data = bytes.fromhex(selector(signature)[2:])
    for arg in static_args:
        if isinstance(arg, str):
            data += encode_address(arg)
        else:
            data += pad32(int(arg))
    return "0x" + data.hex()


def topic_address(topic: str) -> str:
    return decode_address(topic)


def topic_uint(topic: str) -> int:
    h = topic[2:] if topic.startswith("0x") else topic
    return int(h, 16) if h else 0


# Verified topic0 hashes (keccak of the canonical signature).

# PONS V1 factory TokenLaunched — docs.ponsfamily.com
PONS_V1_TOKEN_LAUNCHED = "0xdb51ea9ad51ab453a65a4cb7e60c3cb378c9501bb002609f8f97778fb6c4235a"
PONS_V1_TOKEN_LAUNCHED_SIG = (
    "TokenLaunched(address,address,address,address,address,uint256,uint256,uint256,uint256,uint256)"
)

# Uniswap V3 Swap — docs.ponsfamily.com
UNISWAP_V3_SWAP = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
UNISWAP_V3_SWAP_SIG = "Swap(address,address,int256,int256,uint160,uint128,int24)"

# PONS V2 factory TokenLaunched — Bitquery event reference (verified keccak of source signature)
PONS_V2_TOKEN_LAUNCHED = "0x8d4aad4953d0ca700d468f3753aa14432d1b35b43ec6409f051fb6aa43a89607"
PONS_V2_TOKEN_LAUNCHED_SIG = "TokenLaunched(address,address,address,address,uint256,uint256)"
PONS_V2_LAUNCH_SWEPT = "0xcdb72f157fd3666758a6ce201387ffb52038c7562e4fff352828da1096c4b6b4"
PONS_V2_POOL_GRADUATED = "0x0a44ef75df69c534f43cd6c1aa3ef8983065fe5fe79ef9e79f6494e6f258c259"
PONS_V2_CURVE_BUY = "0xec36bf571f136799e8dc0b0b8bea4b04d8bd3d43de838aab0d5fc21d4cbfc455"
PONS_V2_CURVE_SELL = "0x8113d738abdcb6b38357e9d53a54a7157861a09031b453651f0fe7fe151f59df"

# InkyPump V2 — docs.inkyswap.com ABI page
INKY_LAUNCH_CREATED_SIG = "LaunchCreated(uint256,address,address,uint96)"
INKY_LAUNCH_METADATA_SIG = (
    "LaunchMetadata(uint256,string,string,string,string,string,string,string)"
)
# TradeType is an enum → uint8 in the canonical signature.
# PriceData (uint256,uint256), TradeData (uint256,uint256,uint256) from integration-guide.
INKY_TRADE_SIG = "Trade(uint256,address,uint8,(uint256,uint256),(uint256,uint256,uint256),uint256"
INKY_TRADE_SIG_CANON = (
    "Trade(uint256,address,uint8,(uint256,uint256),(uint256,uint256,uint256),uint256)"
)
INKY_LAUNCH_FINALIZED_SIG = "LaunchFinalized(uint256,bytes32,uint256,uint256)"

ERC20_TRANSFER_SIG = "Transfer(address,address,uint256)"
ERC20_TRANSFER = topic0(ERC20_TRANSFER_SIG)

SEL_NAME = selector("name()")
SEL_SYMBOL = selector("symbol()")
SEL_DECIMALS = selector("decimals()")
SEL_TOTAL_SUPPLY = selector("totalSupply()")
SEL_LOGO = selector("logo()")
SEL_DESCRIPTION = selector("description()")
SEL_LIQUIDITY_POOL = selector("liquidityPool()")
SEL_SOCIALS = selector("socials()")
SEL_GET_LAUNCHED_TOKEN = selector("getLaunchedToken(address)")
SEL_GRADUATION_STATUS = selector("graduationStatus(address)")
SEL_SLOT0 = selector("slot0()")
SEL_BALANCE_OF = selector("balanceOf(address)")
SEL_GET_LAUNCH_STATE = selector("getLaunchState(uint256)")
SEL_PREVIEW_BUY = selector("previewBuy(uint256,uint256)")
SEL_PREVIEW_SELL = selector("previewSell(uint256,uint128)")
