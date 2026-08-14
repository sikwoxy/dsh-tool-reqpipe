"""reqpipe 命令行入口。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .errors import ReqPipeError
from .pipeline import (
    STAGES,
    create_pipeline,
    default_root,
    init_root,
    list_pipelines,
    load_pipeline,
)

_STATUS_TEXT = {"pending": "待开始", "done": "已完成", "skipped": "已跳过", "rejected": "需返工"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reqpipe",
        description="研发团队需求流水线管理工具：需求 → 方案 → 评审 → 开发",
    )
    parser.add_argument("--version", action="version", version=f"reqpipe {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="命令", required=True)

    p = sub.add_parser("init", help="初始化流水线根目录")
    p.set_defaults(handler=cmd_init)

    p = sub.add_parser("create", help="创建需求")
    p.add_argument("title", help="需求标题")
    p.add_argument("--id", dest="req_id", default=None, help="需求 ID（默认自动生成 REQ-XXX）")
    p.add_argument("--desc", default="", help="需求描述")
    p.add_argument("--light", action="store_true", help="轻量流程：方案/评审阶段标记为可选，可跳过")
    p.add_argument("--json", action="store_true", help="以 JSON 输出（pipeline 清单）")
    p.set_defaults(handler=cmd_create)

    p = sub.add_parser("advance", help="推进阶段（需求→方案→评审→开发；评审阶段需用 review 命令）")
    p.add_argument("req_id", help="需求 ID")
    p.add_argument("--force", action="store_true", help="缺少阶段文档时强制推进")
    p.add_argument("--by", default=None, help="操作者身份（默认：REQPIPE_ACTOR 环境变量或 anonymous）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出（{pipeline, messages}）")
    p.set_defaults(handler=cmd_advance)

    p = sub.add_parser("skip", help="跳过阶段（必须记录原因，仅支持 方案/评审；评审须由非方案作者执行）")
    p.add_argument("req_id", help="需求 ID")
    choices: List[str] = []
    for s in STAGES:
        choices.append(s["name"])
        choices.append(s["label"])
    p.add_argument("stage", choices=choices, help="要跳过的阶段（design/方案、review/评审）")
    p.add_argument("--reason", required=True, help="跳过原因（必填）")
    p.add_argument("--by", default=None, help="操作者身份（默认：REQPIPE_ACTOR 环境变量或 anonymous）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出（{pipeline, messages}）")
    p.set_defaults(handler=cmd_skip)

    p = sub.add_parser("review", help="评审方案（评审人须与方案作者不同；approve 进入开发，reject 打回返工）")
    p.add_argument("req_id", help="需求 ID")
    p.add_argument("--by", default=None, help="评审人身份（必填：其他 agent 的会话 id 或人工姓名）")
    p.add_argument("--verdict", choices=["approve", "reject"], required=True, help="评审结论")
    p.add_argument("--comment", default="", help="评审意见")
    p.add_argument("--json", action="store_true", help="以 JSON 输出（{pipeline, messages}）")
    p.set_defaults(handler=cmd_review)

    p = sub.add_parser("list", help="列出所有流水线")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    p.set_defaults(handler=cmd_list)

    p = sub.add_parser("show", help="查看需求详情")
    p.add_argument("req_id", help="需求 ID")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    p.set_defaults(handler=cmd_show)

    p = sub.add_parser("checklist", help="生成提交清单")
    p.add_argument("req_id", help="需求 ID")
    p.add_argument("-o", "--out", default=None, help="写入指定文件（默认输出到终端）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出（{markdown}）")
    p.set_defaults(handler=cmd_checklist)

    return parser


# ---------- 各子命令实现 ----------

def cmd_init(args: argparse.Namespace, root: Path) -> None:
    p = init_root(root)
    print(f"✔ 已初始化流水线根目录：{p}")
    print(f"  约定说明文档：{p / 'README.md'}")


def cmd_create(args: argparse.Namespace, root: Path) -> None:
    manifest = create_pipeline(
        root, args.title, req_id=args.req_id, description=args.desc, light=args.light
    )
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return
    print(f"✔ 需求已创建：{manifest['id']}（{manifest['title']}）")
    print(f"  目录：{root / manifest['id']}")
    print(f"  类型：{'轻量流程' if manifest['light'] else '标准流程'}")
    first = manifest["stages"][0]
    print(f"  当前阶段：{first['label']}（请完善 {root / manifest['id'] / first['dir'] / first['doc']}）")
    print(f"  下一步：reqpipe advance {manifest['id']}")


def _emit_messages(msgs: List[str], pipeline_data: Dict[str, Any], as_json: bool) -> None:
    """advance/skip 的通用输出：--json 输出 {pipeline, messages}，否则逐行打印。"""
    if as_json:
        print(json.dumps({"pipeline": pipeline_data, "messages": msgs}, ensure_ascii=False, indent=2))
        return
    for msg in msgs:
        print(msg)


def cmd_advance(args: argparse.Namespace, root: Path) -> None:
    pipe = load_pipeline(root, args.req_id)
    msgs = pipe.advance(force=args.force, by=args.by)
    _emit_messages(msgs, pipe.data, args.json)


def cmd_skip(args: argparse.Namespace, root: Path) -> None:
    pipe = load_pipeline(root, args.req_id)
    msgs = pipe.skip(args.stage, args.reason, by=args.by)
    _emit_messages(msgs, pipe.data, args.json)


def cmd_review(args: argparse.Namespace, root: Path) -> None:
    pipe = load_pipeline(root, args.req_id)
    msgs = pipe.review(by=args.by, verdict=args.verdict, comment=args.comment)
    _emit_messages(msgs, pipe.data, args.json)


def _summary(pipe) -> Dict[str, Any]:
    cur = pipe.current()
    return {
        "id": pipe.id,
        "title": pipe.title,
        "light": pipe.light,
        "status": "completed" if pipe.completed() else "in_progress",
        "current_stage": cur["name"] if cur else None,
        "stages": [
            {
                "name": s["name"],
                "label": s["label"],
                "status": s["status"],
                "reason": s.get("reason"),
                "skipped_at": s.get("skipped_at"),
                "done_by": s.get("done_by"),
                "skipped_by": s.get("skipped_by"),
                "reviews": s.get("reviews") or [],
            }
            for s in pipe.stages
        ],
    }


def cmd_list(args: argparse.Namespace, root: Path) -> None:
    pipes = list_pipelines(root)
    if args.json:
        print(json.dumps([_summary(p) for p in pipes], ensure_ascii=False, indent=2))
        return
    if not pipes:
        print('（暂无流水线，可先运行：reqpipe create "需求标题"）')
        return
    rows = [["ID", "标题", "当前阶段", "状态", "类型"]]
    for p in pipes:
        cur = p.current()
        rows.append(
            [
                p.id,
                p.title,
                cur["label"] if cur else "—",
                "已完成" if p.completed() else "进行中",
                "轻量" if p.light else "标准",
            ]
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def cmd_show(args: argparse.Namespace, root: Path) -> None:
    pipe = load_pipeline(root, args.req_id)
    if args.json:
        print(json.dumps(pipe.data, ensure_ascii=False, indent=2))
        return
    print(f"需求：{pipe.title}（{pipe.id}）")
    print(f"类型：{'轻量流程（方案/评审可跳过）' if pipe.light else '标准流程'}")
    print(f"状态：{'已完成' if pipe.completed() else '进行中'}")
    print(f"创建：{pipe.data['created_at']}")
    if pipe.data.get("description"):
        print(f"描述：{pipe.data['description']}")
    print()
    print("阶段：")
    for s in pipe.stages:
        mark = {"done": "✔", "skipped": "⏭", "pending": "·", "rejected": "✘"}[s["status"]]
        optional = "（可选）" if s["skippable"] else ""
        extra = ""
        if s["status"] == "skipped":
            extra = f"　跳过原因：{s['reason']}（by {s.get('skipped_by') or '—'}）"
        elif s["status"] == "done":
            extra = f"　完成人：{s.get('done_by') or '—'}"
        elif s["status"] == "rejected":
            extra = f"　需返工（作者：{s.get('done_by') or '—'}）"
        print(f"  {mark} {s['label']}{optional}　{s['dir']}/{s['doc']}　[{_STATUS_TEXT[s['status']]}]{extra}")
        reviews = s.get("reviews") or []
        if reviews:
            for r in reviews:
                verdict = "通过" if r["verdict"] == "approve" else "不通过"
                note = f"，意见：{r['comment']}" if r.get("comment") else ""
                print(f"      · 评审[{verdict}] by {r['by']} @ {r['at']}{note}")
    print()
    print("历史：")
    for h in pipe.data["history"]:
        print(f"  {h['at']}  {h['detail']}")


def cmd_checklist(args: argparse.Namespace, root: Path) -> None:
    pipe = load_pipeline(root, args.req_id)
    text = pipe.checklist()
    if args.json:
        print(json.dumps({"markdown": text}, ensure_ascii=False, indent=2))
        return
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"✔ 提交清单已写入：{out}")
    else:
        print(text, end="")


# ---------- 入口 ----------

def _extract_root(argv: List[str]):
    """从任意位置提取 --root，使该参数在子命令前后均可使用。"""
    rest: List[str] = []
    root: Optional[str] = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--root":
            if i + 1 >= len(argv):
                raise ReqPipeError("--root 需要一个路径参数")
            root = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--root="):
            root = arg.split("=", 1)[1]
            i += 1
            continue
        rest.append(arg)
        i += 1
    return rest, root


def resolve_root(argv_root: Optional[str]) -> Path:
    if argv_root:
        return Path(argv_root)
    env = os.environ.get("REQPIPE_ROOT")
    if env:
        return Path(env)
    return default_root()


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        argv, root_flag = _extract_root(argv)
        parser = build_parser()
        args = parser.parse_args(argv)
        root = resolve_root(root_flag)
        handler = getattr(args, "handler", None)
        if handler is None:
            parser.print_help()
            return 2
        handler(args, root)
        return 0
    except ReqPipeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已取消", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
