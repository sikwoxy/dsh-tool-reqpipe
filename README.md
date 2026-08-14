# reqpipe —— 研发需求流水线管理工具（DeepSeek Harness 插件）

> 为研发团队把每个需求拆成 4 个阶段（**需求 → 方案 → 评审 → 开发**），
> 每个需求一个工作目录，阶段产物有约定的目录命名与文档格式；
> 支持跳过 方案/评审 的轻量流程（跳过必须记录原因）。
> **评审必须由方案作者以外的身份完成**（另一个 agent 或人工），`reject` 打回返工。

本仓库包含两个可分发包：

| 目录 | 包 | 平台 | 安装 |
| --- | --- | --- | --- |
| [`plugin/`](./plugin/) | `dsh-tool-reqpipe` | npm（DeepSeek Harness 插件） | `dsh plugin add dsh-tool-reqpipe` |
| [`python-cli/`](./python-cli/) | `reqpipe` | PyPI（命令行工具） | `pip install reqpipe` |

插件通过子进程调用 `reqpipe` CLI，因此**两个包都需要安装**。

## 安装

```bash
# 1. 安装 Python CLI（插件运行时依赖）
pip install reqpipe

# 2. 安装 Harness 插件（在 deepseek-harness 环境内）
dsh plugin add dsh-tool-reqpipe
```

> 已安装 DeepSeek Harness 的用户可直接 `dsh plugin add dsh-tool-reqpipe`；
> 插件与 CLI 的版本建议保持一致。

## 使用

插件注册 7 个工具，在 Web UI / CLI 会话中**用自然语言直接指挥**即可：

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `reqpipe_init` | — | 初始化流水线根目录（通常无需手动调用） |
| `reqpipe_create` | `title`（必填）, `id?`, `description?`, `light?` | 创建需求 |
| `reqpipe_advance` | `id`（必填）, `force?` | 推进阶段（需求/方案/开发），自动生成下一阶段文档模板；评审阶段须用 `reqpipe_review` |
| `reqpipe_review` | `id`, `reviewer`（必填，≠方案作者）, `verdict: approve\|reject`, `comment?` | 评审方案：通过进入开发，不通过打回返工；评审人/结论/意见留档 |
| `reqpipe_skip` | `id`, `stage: design\|review`, `reason`（必填） | 跳过方案/评审（轻量流程，原因留档）；方案作者不能跳过自己的评审 |
| `reqpipe_list` | — | 列出所有流水线 |
| `reqpipe_show` | `id` | 查看详情（阶段状态、操作者、评审记录、跳过原因、历史） |
| `reqpipe_checklist` | `id` | 生成提交清单（Markdown） |

示例对话：

> - “创建一个需求：支持导出 CSV，轻量流程”
> - “推进 REQ-001”（需求 → 方案）
> - “拉一个独立 agent 评审 REQ-001 的方案，通过”（`reqpipe_review`，评审人 ≠ 方案作者）
> - “评审不通过，打回返工”（`reqpipe_review` verdict=reject）
> - “跳过 REQ-002 的方案阶段，理由是改动太小”
> - “给 REQ-003 生成一份提交清单”

也可以直接用 CLI（详见 [`python-cli/README.md`](./python-cli/README.md)）：

```bash
reqpipe create "登录模块支持记住我" --light
reqpipe advance REQ-001 --by alice
reqpipe review REQ-001 --by bob --verdict approve --comment "方案可行"
reqpipe skip REQ-001 design --reason "交互简单，无需方案文档"
reqpipe list
reqpipe checklist REQ-001 -o COMMIT_CHECKLIST.md
```

## 插件配置

在 profile / 组合包层的 `cordis.patch.yml` 中按需覆盖：

```yaml
- id: reqpipe
  name: dsh-tool-reqpipe
  config:
    reqpipeBin: 'reqpipe'          # 默认：PATH 中的 reqpipe
    root: '/srv/pipelines'         # 默认：REQPIPE_ROOT 环境变量 → ./pipelines
```

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `root` | `''` → `REQPIPE_ROOT` → `./pipelines` | 流水线根目录 |
| `reqpipeBin` | `'reqpipe'` | reqpipe 可执行文件，可为绝对路径 |
| `reqpipeArgs` | `[]` | 前置参数，如 `['-m', 'reqpipe']`（配合 `reqpipeBin: 'python3'`） |
| `env` | `{}` | 附加环境变量 |

## 开发与测试

```bash
# Python CLI（python-cli/）
cd python-cli && python3 -m unittest discover -s tests

# 插件（plugin/）
cd plugin && pnpm install && pnpm build && pnpm test && pnpm typecheck
```

## 发布

- **npm**：`cd plugin && pnpm publish`（`lib/` 为预构建产物，安装无需构建授权）
- **PyPI**：`cd python-cli && python -m build && twine upload dist/*`
- 推荐用 GitHub Actions（见 `.github/workflows/publish.yml`）：打 `v*` tag 自动构建、测试并发布两个包（含 npm provenance 与 PyPI 可信发布）

## 许可证

[MIT](./LICENSE)
