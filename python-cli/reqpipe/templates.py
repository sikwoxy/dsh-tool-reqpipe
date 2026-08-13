"""各阶段文档模板与流水线根目录说明模板。"""

from __future__ import annotations

from datetime import datetime


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


TEMPLATES = {
    "requirement": """# 需求说明：{title}

- 需求 ID：{id}
- 创建时间：{created}
- 阶段：需求

## 背景
<!-- 描述需求的背景与动机 -->

## 目标
<!-- 明确本次要达成的目标 -->

## 验收标准
<!-- 逐条列出可验证的验收标准 -->
- [ ] 

## 备注
<!-- 其他说明 -->
""",
    "design": """# 方案设计：{title}

- 需求 ID：{id}
- 创建时间：{created}
- 阶段：方案

## 方案概述
<!-- 用一段话概述整体方案 -->

## 技术选型
<!-- 列出关键选型与理由 -->

## 实施步骤
<!-- 拆解实施步骤 -->

## 风险与对策
<!-- 列出主要风险与应对措施 -->
""",
    "review": """# 评审记录：{title}

- 需求 ID：{id}
- 创建时间：{created}
- 阶段：评审

## 评审结论
- [ ] 通过
- [ ] 需修改
- [ ] 不通过

## 评审意见
<!-- 逐条记录评审意见 -->

## 决议与待办
<!-- 记录决议与后续待办事项 -->
""",
    "development": """# 开发说明：{title}

- 需求 ID：{id}
- 创建时间：{created}
- 阶段：开发

## 实现说明
<!-- 描述实现方式与关键改动 -->

## 变更文件
<!-- 列出本次涉及的代码 / 文件 -->

## 自测结果
<!-- 记录自测用例与结果 -->

## 遗留问题
<!-- 如有遗留问题，记录于此 -->
""",
}


def stage_template(stage_name: str, req_id: str, title: str) -> str:
    """生成某阶段的文档模板内容。"""
    tpl = TEMPLATES.get(stage_name)
    if tpl is None:
        raise ValueError(f"未知阶段模板：{stage_name}")
    return tpl.format(id=req_id, title=title, created=_now())


ROOT_README_TEMPLATE = """# 需求流水线根目录：{root}

本目录由 reqpipe（研发需求流水线管理工具）管理。
每个需求占用一个子目录（以需求 ID 命名），内部按固定约定组织。

## 阶段与目录约定

| 阶段 | 子目录 | 文档文件 |
| --- | --- | --- |
| 需求 | 01-requirement/ | REQUIREMENT.md |
| 方案 | 02-design/ | DESIGN.md |
| 评审 | 03-review/ | REVIEW.md |
| 开发 | 04-development/ | DEVELOPMENT.md |

阶段顺序：需求 → 方案 → 评审 → 开发；其中「方案」「评审」可跳过（必须记录原因），
适用于轻量流程。

## 常用命令

    reqpipe init                          # 初始化根目录
    reqpipe create "需求标题" --light      # 创建需求（轻量流程）
    reqpipe advance <ID>                  # 推进阶段
    reqpipe skip <ID> design --reason 原因 # 跳过方案阶段
    reqpipe list                          # 列出所有流水线
    reqpipe show <ID>                     # 查看详情
    reqpipe checklist <ID>                # 生成提交清单
"""
