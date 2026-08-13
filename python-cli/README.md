# reqpipe —— 研发需求流水线管理工具

把每个需求拆成 4 个固定阶段（**需求 → 方案 → 评审 → 开发**），每个需求一个工作目录，
阶段产物使用约定的目录命名与文档格式；通过命令行创建需求、推进/跳过阶段、列出流水线、
生成提交清单。支持**跳过 方案/评审 的轻量流程**（跳过时必须记录原因）。

纯标准库实现，零第三方依赖。

---

## 特性

- 4 阶段流水线：需求 `requirement` → 方案 `design` → 评审 `review` → 开发 `development`
- 每个需求一个独立工作目录，固定子目录命名与文档格式（自动生成文档模板）
- `advance` 推进阶段，自动生成下一阶段文档模板；缺文档时可用 `--force` 强制推进
- `skip` 跳过 **方案 / 评审** 阶段，**必须**通过 `--reason` 记录原因（写入清单与历史）
- `--light` 轻量流程：创建时声明，方案/评审标记为可选阶段
- `list` / `show` 查看流水线；`checklist` 一键生成提交清单
- 根目录解析：`--root` 参数 > 环境变量 `REQPIPE_ROOT` > 默认 `./pipelines`

---

## 安装

### 方式一：pip 安装（推荐，得到 `reqpipe` 命令）

```bash
cd reqpipe
python3 -m venv .venv && source .venv/bin/activate
pip install .
reqpipe --version
```

### 方式二：不安装，直接运行

```bash
cd reqpipe
python3 -m reqpipe --help
```

---

## 快速开始

```bash
# 1. 初始化流水线根目录（默认 ./pipelines）
reqpipe init

# 2. 创建需求（自动生成 ID：REQ-001、REQ-002 …）
reqpipe create "登录模块支持记住我"

# 3. 完善 01-requirement/REQUIREMENT.md 后，推进阶段
reqpipe advance REQ-001

# 4. 轻量流程：跳过 方案 与 评审（必须说明原因）
reqpipe skip REQ-001 design --reason "交互简单，无需方案文档"
reqpipe skip REQ-001 review --reason "团队口头评审通过"

# 5. 推进到 开发 并完成
reqpipe advance REQ-001

# 6. 查看流水线 / 生成提交清单
reqpipe list
reqpipe show REQ-001
reqpipe checklist REQ-001 -o COMMIT_CHECKLIST.md
```

---

## 目录与文档约定

每个需求一个工作目录 `<需求ID>/`，固定包含 4 个阶段子目录，每个阶段一个约定文档
（创建需求时自动生成第一阶段的模板，推进/跳过时自动生成后续阶段模板）：

| 阶段 | 子目录 | 文档文件 |
| --- | --- | --- |
| 需求 | `01-requirement/` | `REQUIREMENT.md` |
| 方案 | `02-design/` | `DESIGN.md` |
| 评审 | `03-review/` | `REVIEW.md` |
| 开发 | `04-development/` | `DEVELOPMENT.md` |

流水线元数据（阶段状态、跳过原因、操作历史）统一保存在 `<需求ID>/pipeline.json`，
由工具自动维护，无需手工编辑。

```
pipelines/
└── REQ-001/
    ├── pipeline.json          # 元数据：阶段状态、跳过原因、历史
    ├── 01-requirement/
    │   └── REQUIREMENT.md     # 需求说明（背景 / 目标 / 验收标准）
    ├── 02-design/
    │   └── DESIGN.md          # 方案设计（概述 / 选型 / 实施步骤 / 风险）
    ├── 03-review/
    │   └── REVIEW.md          # 评审记录（结论 / 意见 / 决议）
    └── 04-development/
        └── DEVELOPMENT.md     # 开发说明（实现 / 变更文件 / 自测）
```

---

## 命令参考

### `reqpipe init`

初始化流水线根目录，并写入一份约定说明 `README.md`。

```bash
reqpipe init                 # 默认 ./pipelines
reqpipe --root data init     # 指定根目录
```

### `reqpipe create <标题> [--id ID] [--desc 描述] [--light]`

创建需求。默认自动生成 ID（`REQ-001` 起，自动避让已有编号）。

```bash
reqpipe create "登录模块改造"
reqpipe create "修复导出乱码" --id BUG-17 --desc "CSV 导出中文乱码"
reqpipe create "小需求" --light          # 轻量流程
```

### `reqpipe advance <ID> [--force]`

推进阶段：完成当前阶段 → 进入下一阶段，并自动生成下一阶段的文档模板。
要求当前阶段的文档已存在，否则报错；`--force` 可跳过该检查。

```bash
reqpipe advance REQ-001
reqpipe advance REQ-001 --force
```

### `reqpipe skip <ID> <阶段> --reason <原因>`

跳过阶段。**仅支持 方案（design/方案）与 评审（review/评审）**，`--reason` 必填，
原因会记录到清单与历史中。这正是轻量流程的入口。

```bash
reqpipe skip REQ-001 design --reason "改动极小，无需方案文档"
reqpipe skip REQ-001 方案 --reason "改动极小，无需方案文档"   # 中文名亦可
```

### `reqpipe list [--json]`

列出所有流水线（ID / 标题 / 当前阶段 / 状态 / 类型）。`--json` 输出机器可读结构。

### `reqpipe show <ID> [--json]`

查看需求详情：阶段状态（含可选标记与跳过原因）、操作历史。`--json` 输出完整清单。

### `reqpipe checklist <ID> [-o 文件]`

生成 Markdown 提交清单：按阶段列出待提交文件、跳过原因、汇总统计。
默认输出到终端，`-o` 写入文件。

```bash
reqpipe checklist REQ-001
reqpipe checklist REQ-001 -o COMMIT_CHECKLIST.md
```

---

## 轻量流程

团队遇到简单需求时，可以跳过 **方案 / 评审** 阶段直接进入开发：

1. 创建时加 `--light`（方案/评审标记为「可选」，展示时体现）；
2. 需求阶段完成后，用 `skip` 跳过方案与评审，**每次都必须写原因**；
3. 直接 `advance` 进入开发并完成。

跳过记录（原因 + 时间）会写入 `pipeline.json` 的历史与提交清单，
保证“轻量但不留痕”不会发生。

---

## 环境变量

- `REQPIPE_ROOT`：默认流水线根目录。优先级：`--root` 参数 > `REQPIPE_ROOT` > `./pipelines`。

```bash
export REQPIPE_ROOT=/data/req-pipelines
reqpipe create "需求"
```

---

## 测试

```bash
cd reqpipe
python3 -m unittest discover -s tests -v
```

测试覆盖：创建（结构/自动编号/去重/校验）、推进（缺文档检查/完整流程）、
跳过（原因必填/仅方案评审/重复与已完成校验）、轻量流程端到端、
清单内容、CLI 端到端、环境变量与 `--root` 位置无关性、`python -m reqpipe` 冒烟测试。

---

## 项目结构

```
reqpipe/
├── pyproject.toml          # 打包配置（console script: reqpipe）
├── README.md               # 本文档
├── reqpipe/
│   ├── __init__.py         # 版本号
│   ├── __main__.py         # python -m reqpipe
│   ├── cli.py              # 命令行入口（argparse）
│   ├── pipeline.py         # 核心逻辑：阶段机、清单、读写
│   ├── templates.py        # 文档模板与根目录说明
│   └── errors.py           # 自定义异常
└── tests/
    ├── helpers.py          # 测试基类与 CLI 调用封装
    ├── test_core.py        # 核心逻辑测试
    └── test_cli.py         # CLI 端到端测试
```

## 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | 业务错误（需求不存在、阶段不可跳过、缺原因等） |
| 2 | 用法错误（未知命令、缺参数等） |
| 130 | 用户中断（Ctrl-C） |
