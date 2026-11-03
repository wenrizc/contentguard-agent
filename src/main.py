"""Command-line entry point for ContentGuard Agent."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from .agent import AgentRunner, build_dependencies
from .catalog import DataCatalog
from .llm_client import OpenAIChatClient
from .offline import OfflineScenarioClient
from .schemas import TaskInput


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contentguard",
        description="审核短视频素材并生成可确认的排期草稿。",
    )
    subparsers = parser.add_subparsers(dest="command")

    plan = subparsers.add_parser("plan", help="分析素材并生成排期建议")
    plan.add_argument("--input", type=Path, required=True, help="任务输入 JSON 文件")
    plan.add_argument("--offline", action="store_true", help="使用离线模型客户端（仅验证流程）")
    plan.add_argument("--db", type=Path, default=Path(".contentguard.sqlite"), help="SQLite 数据库路径")
    plan.add_argument("--trace", type=Path, help="将最终结果和 Trace 写入 JSON 文件")

    confirm = subparsers.add_parser("confirm", help="确认候选时段并保存排期草稿")
    confirm.add_argument("--input", type=Path, required=True, help="任务输入 JSON 文件")
    confirm.add_argument("--agreed-time", required=True, help="用户确认的带时区时间")
    confirm.add_argument("--offline", action="store_true", help="使用离线模型客户端（仅验证流程）")
    confirm.add_argument("--db", type=Path, default=Path(".contentguard.sqlite"), help="SQLite 数据库路径")
    confirm.add_argument("--trace", type=Path, help="将最终结果和 Trace 写入 JSON 文件")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    try:
        with args.input.open(encoding="utf-8") as handle:
            task = TaskInput.model_validate(json.load(handle))
        catalog = DataCatalog(Path(__file__).parents[1] / "data")
        client = OfflineScenarioClient() if args.offline else OpenAIChatClient.from_env()
        runner = AgentRunner(client, build_dependencies(catalog, args.db))
        confirmed_start = None
        if args.command == "confirm":
            confirmed_start = datetime.fromisoformat(args.agreed_time)
        result = runner.run(task, confirmed_start=confirmed_start)
        result = {"execution_mode": "offline_mock" if args.offline else "real_model", **result}
        rendered = json.dumps(result, ensure_ascii=False, indent=2)
        if args.trace:
            args.trace.parent.mkdir(parents=True, exist_ok=True)
            args.trace.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0 if result["task_status"] != "INCOMPLETE" else 2
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())

