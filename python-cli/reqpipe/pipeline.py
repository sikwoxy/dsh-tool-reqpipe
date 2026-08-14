"""需求流水线管理工具 —— 核心逻辑。

阶段约定：需求(requirement) → 方案(design) → 评审(review) → 开发(development)
每个需求一个工作目录，内部固定 4 个阶段子目录与约定文档文件。
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .errors import CreateError, InvalidStageError, NotFoundError, SkipError, StageError
from .templates import ROOT_README_TEMPLATE, stage_template

MANIFEST_NAME = "pipeline.json"
DEFAULT_ROOT_NAME = "pipelines"
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
AUTO_ID_PATTERN = re.compile(r"^REQ-(\d+)$")

STAGES: List[Dict[str, Any]] = [
    {"name": "requirement", "label": "需求", "dir": "01-requirement", "doc": "REQUIREMENT.md", "skippable": False},
    {"name": "design",      "label": "方案", "dir": "02-design",      "doc": "DESIGN.md",      "skippable": True},
    {"name": "review",      "label": "评审", "dir": "03-review",      "doc": "REVIEW.md",      "skippable": True},
    {"name": "development", "label": "开发", "dir": "04-development", "doc": "DEVELOPMENT.md", "skippable": False},
]

STAGE_BY_NAME = {s["name"]: s for s in STAGES}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def default_actor() -> str:
    """操作者身份默认值：REQPIPE_ACTOR 环境变量，否则 anonymous。"""
    return os.environ.get("REQPIPE_ACTOR") or "anonymous"


def default_root() -> Path:
    """根目录解析：--root 参数 > 环境变量 REQPIPE_ROOT > ./pipelines。"""
    env = os.environ.get("REQPIPE_ROOT")
    if env:
        return Path(env)
    return Path(DEFAULT_ROOT_NAME)


def stage_by_alias(alias: str) -> Optional[Dict[str, Any]]:
    """按英文名或中文名查找阶段定义。"""
    for s in STAGES:
        if alias == s["name"] or alias == s["label"]:
            return s
    return None


# ---------- JSON 读写 ----------

def _read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


# ---------- 根目录 ----------

def init_root(root: Path) -> Path:
    """初始化流水线根目录，并生成约定说明 README。"""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(ROOT_README_TEMPLATE.format(root=str(root)), encoding="utf-8")
    return root


def ensure_root(root: Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def next_id(root: Path) -> str:
    """按现有 REQ-NNN 目录自动生成下一个 ID。"""
    maximum = 0
    if root.is_dir():
        for child in root.iterdir():
            if child.is_dir():
                m = AUTO_ID_PATTERN.fullmatch(child.name)
                if m:
                    maximum = max(maximum, int(m.group(1)))
    return f"REQ-{maximum + 1:03d}"


# ---------- 创建 / 加载 ----------

def create_pipeline(
    root: Path,
    title: str,
    req_id: Optional[str] = None,
    description: str = "",
    light: bool = False,
) -> Dict[str, Any]:
    """创建一个需求流水线：建目录、初始化 4 个阶段、生成需求文档模板。"""
    root = ensure_root(Path(root))
    title = (title or "").strip()
    if not title:
        raise CreateError("需求标题不能为空")
    req_id = (req_id or next_id(root)).strip()
    if not ID_PATTERN.fullmatch(req_id):
        raise CreateError(
            f"需求 ID 不合法：{req_id!r}（仅允许字母、数字、-、_、.，且以字母或数字开头）"
        )
    target = root / req_id
    if target.exists():
        raise CreateError(f"需求已存在：{req_id}（{target}）")

    target.mkdir(parents=True)
    try:
        stages: List[Dict[str, Any]] = []
        for s in STAGES:
            (target / s["dir"]).mkdir()
            stages.append({
                **s,
                "status": "pending",
                "reason": None,
                "skipped_at": None,
                "done_by": None,
                "done_at": None,
                "skipped_by": None,
                "reviews": [],
                "rejected_at": None,
            })
        manifest = {
            "schema": 1,
            "id": req_id,
            "title": title,
            "description": description,
            "created_at": now_iso(),
            "light": bool(light),
            "stages": stages,
            "history": [
                {"action": "create", "stage": None, "at": now_iso(), "detail": f"创建需求：{title}"}
            ],
        }
        _write_json(target / MANIFEST_NAME, manifest)
        scaffold_doc(target, STAGES[0], req_id, title)
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return manifest


def scaffold_doc(pdir: Path, stage: Dict[str, Any], req_id: str, title: str) -> bool:
    """为指定阶段生成文档模板；已存在则跳过。返回是否新建。"""
    doc = pdir / stage["dir"] / stage["doc"]
    if doc.exists():
        return False
    doc.write_text(stage_template(stage["name"], req_id, title), encoding="utf-8")
    return True


def load_pipeline(root: Path, req_id: str) -> "Pipeline":
    root = Path(root)
    manifest_path = root / req_id / MANIFEST_NAME
    if not manifest_path.is_file():
        raise NotFoundError(f"未找到需求 {req_id}（{root} 下不存在 {req_id}/{MANIFEST_NAME}）")
    try:
        data = _read_json(manifest_path)
    except (json.JSONDecodeError, OSError) as exc:
        raise NotFoundError(f"读取需求 {req_id} 的清单失败：{exc}") from exc
    return Pipeline(root, req_id, data)


def list_pipelines(root: Path) -> List["Pipeline"]:
    """列出根目录下所有流水线（按 ID 排序）。"""
    root = Path(root)
    result: List[Pipeline] = []
    if not root.is_dir():
        return result
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / MANIFEST_NAME).is_file():
            try:
                result.append(Pipeline(root, child.name, _read_json(child / MANIFEST_NAME)))
            except (json.JSONDecodeError, OSError):
                continue
    return result


# ---------- 流水线对象 ----------

class Pipeline:
    def __init__(self, root: Path, req_id: str, data: Dict[str, Any]):
        self.root = Path(root)
        self.id = req_id
        self.data = data
        self.dir = self.root / req_id

    @property
    def title(self) -> str:
        return self.data["title"]

    @property
    def stages(self) -> List[Dict[str, Any]]:
        return self.data["stages"]

    @property
    def light(self) -> bool:
        return bool(self.data.get("light", False))

    def save(self) -> None:
        _write_json(self.dir / MANIFEST_NAME, self.data)

    def stage(self, name: str) -> Optional[Dict[str, Any]]:
        """返回本流水线内某个阶段的当前状态。"""
        for s in self.stages:
            if s["name"] == name:
                return s
        return None

    def current(self) -> Optional[Dict[str, Any]]:
        """当前阶段 = 第一个待处理（pending）或需返工（rejected）的阶段。"""
        for s in self.stages:
            if s["status"] in ("pending", "rejected"):
                return s
        return None

    def design_author(self) -> Optional[str]:
        """方案作者（design 阶段的完成人），可能为 None（旧数据或方案被跳过）。"""
        design = self.stage("design")
        if design is None:
            return None
        return design.get("done_by")

    def completed(self) -> bool:
        return all(s["status"] in ("done", "skipped") for s in self.stages)

    def doc_path(self, stage: Dict[str, Any]) -> Path:
        return self.dir / stage["dir"] / stage["doc"]

    def scaffold_doc(self, stage: Dict[str, Any]) -> bool:
        return scaffold_doc(self.dir, stage, self.id, self.title)

    def _log(self, action: str, stage: Optional[str], detail: str) -> None:
        self.data["history"].append(
            {"action": action, "stage": stage, "at": now_iso(), "detail": detail}
        )

    def _scaffold_next(self, msgs: List[str]) -> None:
        nxt = self.current()
        if nxt is None:
            msgs.append(f"🎉 需求 {self.id} 的全部阶段已完成")
            return
        if self.scaffold_doc(nxt):
            msgs.append(f"→ 当前阶段：{nxt['label']}（已生成模板：{self.doc_path(nxt).relative_to(self.root)}）")
        else:
            msgs.append(f"→ 当前阶段：{nxt['label']}")

    # ---------- 推进阶段 ----------

    def advance(self, force: bool = False, by: Optional[str] = None) -> List[str]:
        """推进阶段：完成当前阶段并进入下一阶段（自动生成下一阶段文档模板）。

        评审（review）阶段不允许用 advance 推进——必须通过 review 动作完成，
        且评审人不能是方案作者；否则直接报错，防止同一 agent 自写自评。
        """
        msgs: List[str] = []
        by = by or default_actor()
        cur = self.current()
        if cur is None:
            raise StageError(f"需求 {self.id} 的所有阶段均已完成，无需推进")
        if cur["name"] == "review":
            author = self.design_author()
            raise StageError(
                f"评审阶段必须通过 review 动作完成（评审人须与方案作者"
                f"{author or '（未知）'}不同，可由其他 agent 或人工评审），"
                f"不能直接 advance 跳过评审"
            )
        doc = self.doc_path(cur)
        if not force and not doc.exists():
            raise StageError(
                f"{cur['label']} 阶段缺少文档：{doc.relative_to(self.root)}；"
                f"请先完善文档，或使用 --force 强制推进"
            )
        cur["status"] = "done"
        cur["done_by"] = by
        cur["done_at"] = now_iso()
        self._log("advance", cur["name"], f"推进：{cur['label']} 阶段完成（by {by}）")
        msgs.append(f"✔ {cur['label']} 阶段已完成（{cur['dir']}/，by {by}）")
        self._scaffold_next(msgs)
        self.save()
        return msgs

    # ---------- 跳过阶段 ----------

    def skip(self, alias: str, reason: str, by: Optional[str] = None) -> List[str]:
        """跳过阶段（仅 方案/评审 可跳过），必须记录原因。

        评审阶段不能由方案作者自行跳过：跳过评审须由其他 agent 或人工决定。
        """
        spec = stage_by_alias(alias)
        if spec is None:
            raise InvalidStageError(
                f"未知阶段：{alias}（可选：{', '.join(s['name'] for s in STAGES)}）"
            )
        stage = self.stage(spec["name"])
        if not spec["skippable"]:
            raise SkipError(f"{spec['label']} 阶段不允许跳过（仅支持跳过：方案 design、评审 review）")
        if stage["status"] == "done":
            raise SkipError(f"{spec['label']} 阶段已完成，不能跳过")
        if stage["status"] == "skipped":
            raise SkipError(f"{spec['label']} 阶段已跳过，不能重复跳过")
        if stage["status"] == "rejected":
            raise SkipError(f"{spec['label']} 阶段处于返工中（评审未通过），请先重新完善，不能跳过")
        reason = (reason or "").strip()
        if not reason:
            raise SkipError(f"跳过 {spec['label']} 阶段必须提供原因（--reason）")
        by = by or default_actor()

        # 评审跳过：方案作者不能决定自己方案的评审跳过
        if spec["name"] == "review":
            design = self.stage("design")
            if design and design["status"] == "rejected":
                raise SkipError("方案处于返工中（评审未通过），请先重新完善方案后再决定是否跳过评审")
            author = self.design_author()
            if author and author == by:
                raise SkipError(
                    f"方案作者 {author} 不能跳过自己方案的评审：评审须由其他 agent 或人工完成"
                )

        stage["status"] = "skipped"
        stage["reason"] = reason
        stage["skipped_at"] = now_iso()
        stage["skipped_by"] = by
        self._log("skip", spec["name"], f"跳过：{spec['label']}（by {by}，原因：{reason}）")
        msgs = [f"⏭ 已跳过 {spec['label']} 阶段（by {by}），原因：{reason}"]
        self._scaffold_next(msgs)
        self.save()
        return msgs

    # ---------- 评审 ----------

    def review(self, by: Optional[str], verdict: str, comment: str = "") -> List[str]:
        """评审方案（设计阶段）。评审人必须显式声明且与方案作者不同。

        verdict=approve：评审通过，评审阶段完成并进入开发；
        verdict=reject：评审不通过，方案阶段打回返工（status=rejected），
        重新完善方案后再评审。每轮评审记录（评审人/结论/意见/时间）写入
        pipeline.json 的 reviews 与 REVIEW.md，留档可查。
        """
        msgs: List[str] = []
        review_stage = self.stage("review")
        if review_stage is None:
            raise StageError("该需求没有评审阶段")
        design = self.stage("design")
        if design is None or design["status"] != "done":
            raise StageError("评审前需要先完成方案（design）阶段")
        by = (by or "").strip()
        if not by:
            raise StageError("评审必须显式声明评审人身份（by）：可为其他 agent 的会话 id 或人工姓名")
        author = design.get("done_by")
        if author and author == by:
            raise StageError(
                f"方案作者 {author} 不能评审自己的方案：请由其他 agent 或人工完成评审"
            )
        verdict = (verdict or "").strip().lower()
        if verdict not in ("approve", "reject"):
            raise StageError(f"verdict 必须是 approve 或 reject，收到：{verdict!r}")
        comment = (comment or "").strip()

        reviews = review_stage.setdefault("reviews", [])
        reviews.append({"verdict": verdict, "by": by, "comment": comment or None, "at": now_iso()})

        if verdict == "approve":
            review_stage["status"] = "done"
            review_stage["done_by"] = by
            review_stage["done_at"] = now_iso()
            detail = f"评审通过（评审人：{by}）"
            msgs.append(f"✔ 评审通过（评审人：{by}），进入开发阶段")
            self._scaffold_next(msgs)
        else:
            design["status"] = "rejected"
            design["rejected_at"] = now_iso()
            detail = f"评审不通过（评审人：{by}），方案已打回返工"
            msgs.append(
                f"✘ 评审不通过（评审人：{by}），方案已打回返工：请重新完善 DESIGN.md 后再次评审"
            )
        if comment:
            detail += f"；意见：{comment}"
            msgs.append(f"　评审意见：{comment}")
        self._log("review", "review", detail)
        self._write_review_doc(review_stage, reviews)
        self.save()
        return msgs

    def _write_review_doc(self, review_stage: Dict[str, Any], reviews: List[Dict[str, Any]]) -> None:
        """把评审记录落盘为 REVIEW.md（每轮评审一节，保留全部历史）。"""
        from .templates import review_doc

        doc = self.doc_path(review_stage)
        doc.write_text(review_doc(self.id, self.title, reviews), encoding="utf-8")

    # ---------- 提交清单 ----------

    def checklist(self) -> str:
        """生成 Markdown 提交清单。"""
        lines = [
            f"# 提交清单：{self.title}（{self.id}）",
            "",
            f"- 生成时间：{now_iso()}",
            f"- 流程类型：{'轻量（方案/评审可跳过）' if self.light else '标准'}",
            f"- 总体状态：{'已完成' if self.completed() else '进行中'}",
            "",
            "## 阶段与文件",
        ]
        status_text = {"done": "已完成", "pending": "待完成", "skipped": "已跳过", "rejected": "需返工"}
        for s in self.stages:
            lines.append("")
            lines.append(f"### {s['label']}（{s['dir']}/）[{status_text[s['status']]}]")
            if s["status"] == "skipped":
                lines.append(f"- [x] 已跳过，原因：{s['reason']}")
                continue
            if s["status"] == "rejected":
                lines.append("- [ ] 需返工：评审未通过，请重新完善方案后再评审")
                continue
            stage_dir = self.dir / s["dir"]
            files = sorted(p for p in stage_dir.rglob("*") if p.is_file())
            if not files:
                hint = (
                    "（待完成，暂无提交文件）"
                    if s["status"] == "pending"
                    else f"（{s['label']} 阶段暂无文件）"
                )
                lines.append(f"- [ ] {hint}")
            else:
                for f in files:
                    lines.append(f"- [ ] {f.relative_to(self.root)}")
        done = sum(1 for s in self.stages if s["status"] == "done")
        skipped = sum(1 for s in self.stages if s["status"] == "skipped")
        pending = sum(1 for s in self.stages if s["status"] == "pending")
        rejected = sum(1 for s in self.stages if s["status"] == "rejected")
        lines += [
            "",
            "## 汇总",
            f"- 已完成：{done} 个阶段；已跳过：{skipped} 个；需返工：{rejected} 个；待完成：{pending} 个",
            "",
            "> 逐项勾选以上条目，确认各阶段产物齐备后再提交。",
            "",
        ]
        return "\n".join(lines)
