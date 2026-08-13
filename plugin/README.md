# dsh-tool-reqpipe

DeepSeek Harness 插件：把 [`reqpipe`](../python-cli/)（研发团队需求流水线管理工具）包装成一组结构化工具，模型可以直接调用工具来创建需求、推进/跳过阶段、查看流水线、生成提交清单。

- 阶段约定：**需求 → 方案 → 评审 → 开发**，每个需求一个工作目录，固定目录命名与文档格式
- 跳过 **方案/评审** 即轻量流程，`reason` 必填并留档
- 规范值：每个工具返回 CLI 的 `--json` 输出；渲染层产出模型可见的中文文本

## 依赖

插件通过子进程调用 `reqpipe` CLI，**必须先安装**：

```bash
pip install reqpipe
```

## 安装

```bash
dsh plugin add dsh-tool-reqpipe
```

（开发/调试也可用 `--patch` 加载本目录：`pnpm dsh web --patch ./cordis.patch.yml`。）

## 注册的工具

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `reqpipe_init` | — | 初始化流水线根目录（通常无需手动调用） |
| `reqpipe_create` | `title`（必填）, `id?`, `description?`, `light?` | 创建需求，返回清单 |
| `reqpipe_advance` | `id`（必填）, `force?` | 推进阶段，自动生成下一阶段文档模板 |
| `reqpipe_skip` | `id`, `stage: design\|review`, `reason`（必填） | 跳过方案/评审（轻量流程），原因留档 |
| `reqpipe_list` | — | 列出所有流水线 |
| `reqpipe_show` | `id` | 查看详情（阶段状态、跳过原因、历史） |
| `reqpipe_checklist` | `id` | 生成提交清单（Markdown） |

## 配置

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

## 开发

```bash
pnpm install
pnpm build        # tsdown → lib/（自包含，可作 git 安装的 prepare）
pnpm typecheck    # tsc --noEmit
pnpm test         # vitest（需先有 ../python-cli 下的 reqpipe 源码）
```

测试通过 `python3 -m reqpipe` 调用仓库内 `../python-cli` 的 CLI 源码，
可用 `REQPIPE_SRC` 环境变量覆盖位置。
