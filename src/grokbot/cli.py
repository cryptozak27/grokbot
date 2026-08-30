from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from grokbot.adapters import build_adapters
from grokbot.agents.llm import HttpLlmClient, ScriptedLlmClient
from grokbot.config import load_config
from grokbot.log import JsonlLogger
from grokbot.pipeline import Pipeline
from grokbot.risk import RiskManager


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="grokbot", description="EVM memecoin paper pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run the pipeline")
    run.add_argument("--mode", default=None, help="paper (default) or live")
    run.add_argument("--launchpad", action="append", dest="launchpads", help="pons / inkypump")
    run.add_argument("--config", default=None)
    run.add_argument("--once", action="store_true", help="single poll then exit")
    run.add_argument("--dry-llm", action="store_true", help="use a local scripted LLM (no API)")
    args = parser.parse_args(argv)

    if args.cmd == "run":
        return asyncio.run(_run(args))
    return 1


async def _run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    if args.mode:
        cfg.execution_mode = args.mode.lower()
    if not cfg.is_paper:
        print("live execution is not implemented; refusing to run. Set EXECUTION_MODE=paper.")
        return 2

    adapters = build_adapters(cfg, enabled_only=True)
    if args.launchpads:
        wanted = {n.lower() for n in args.launchpads}
        adapters = {k: v for k, v in adapters.items() if k in wanted}
        missing = wanted - set(adapters)
        if missing:
            # allow selecting a configured-but-disabled launchpad
            all_adapters = build_adapters(cfg, enabled_only=False)
            for name in list(missing):
                if name in all_adapters and not all_adapters[name].stub:
                    adapters[name] = all_adapters[name]
                    missing.discard(name)
        if missing:
            print(f"unknown or stub launchpad: {sorted(missing)}")
            return 2
    if not adapters:
        print("no launchpads enabled")
        return 2

    if args.dry_llm or not cfg.llm.api_key:
        llm = ScriptedLlmClient(
            default='{"passed": false, "reasons": ["dry-llm"], "approve": false, '
            '"narrative_fit": 0, "virality": 0, "community": 0, "timing": 0, '
            '"mood": 0.4, "meme_season": false, "volume_regime": "unknown"}'
        )
        if not cfg.llm.api_key and not args.dry_llm:
            print("GROK_API_KEY unset; using dry scripted LLM (all auditor/checker fail-closed).")
    else:
        llm = HttpLlmClient(cfg.llm)

    logger = JsonlLogger(Path(cfg.log_dir) / "pipeline.jsonl")
    pipelines = [
        Pipeline(cfg, adapter, llm, logger, risk=RiskManager(cfg.risk))
        for adapter in adapters.values()
        if not adapter.stub
    ]
    if not pipelines:
        print("only stub adapters selected")
        return 2

    print(
        f"paper mode | launchpads={list(adapters)} | once={args.once} | "
        f"llm={'dry' if isinstance(llm, ScriptedLlmClient) else cfg.llm.auditor_model}"
    )
    if args.once:
        for p in pipelines:
            await p.run_once()
        return 0
    await asyncio.gather(*(p.run_forever() for p in pipelines))
    return 0
