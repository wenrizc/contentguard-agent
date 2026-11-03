"""Command-line entry point for ContentGuard Agent.

The command handlers are intentionally kept small during the data-baseline
stage. Later stages will connect them to the ReAct runner.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contentguard",
        description="审核短视频素材并生成可确认的排期草稿。",
    )
    subparsers = parser.add_subparsers(dest="command")

    plan = subparsers.add_parser("plan", help="分析素材并生成排期建议")
    plan.add_argument("--input", type=Path, required=True, help="任务输入 JSON 文件")
    plan.add_argument("--offline", action="store_true", help="使用离线模型客户端")

    confirm = subparsers.add_parser("confirm", help="确认候选时段并保存排期草稿")
    confirm.add_argument("--input", type=Path, required=True, help="任务输入 JSON 文件")
    confirm.add_argument("--agreed-time", required=True, help="用户确认的带时区时间")
    confirm.add_argument("--offline", action="store_true", help="使用离线模型客户端")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    parser.error("CLI 工具将在后续阶段接入；当前阶段仅验证命令入口。")


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())

