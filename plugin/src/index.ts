/**
 * reqpipe —— 研发需求流水线管理工具插件。
 *
 * 把 Python CLI（reqpipe）包装成一组结构化工具：每个命令一个工具，
 * execute 通过子进程调用 CLI 并取 `--json` 输出作为规范值，
 * render 再把规范值转成模型可见的中文文本。
 *
 * 阶段约定：需求(requirement) → 方案(design) → 评审(review) → 开发(development)；
 * 其中方案/评审可跳过（必须记录原因），即轻量流程。
 */

import type { Context } from '@deepseek-ai/cordis'
import Schema from '@deepseek-ai/schemastery'
import { defineTool, type JsonValue } from '@deepseek-ai/dsh-tools'
import { createRunner, type RunnerOptions } from './runner.ts'
import { renderChange, renderCreate, renderList, renderShow, text } from './render.ts'
import type { PipelineManifest, PipelineSummary, StageChangeResult } from './types.ts'

export const name = 'reqpipe'
export const inject = ['tools']

/**
 * 插件配置。所有字段都有 Schemastery 默认值，加载时必被填充，
 * 因此接口中声明为必填（与官方插件配置约定一致）。
 */
export interface Config {
  /** 流水线根目录；留空依次回退环境变量 REQPIPE_ROOT、./pipelines。 */
  root: string
  /** reqpipe 可执行文件；默认 'reqpipe'（需已安装），可给绝对路径。 */
  reqpipeBin: string
  /** 前置参数，如 ['-m', 'reqpipe']（配合 reqpipeBin='python3'）。 */
  reqpipeArgs: string[]
  /** 附加环境变量（合并到 process.env 之上）。 */
  env: Record<string, string>
}

export const Config: Schema<Config> = Schema.object({
  root: Schema.string().default(''),
  reqpipeBin: Schema.string().default('reqpipe'),
  reqpipeArgs: Schema.array(Schema.string()).default([]),
  env: Schema.dict(Schema.string()).default({}),
})

function resolveRoot(config: Config): string {
  if (config.root) return config.root
  if (process.env.REQPIPE_ROOT) return process.env.REQPIPE_ROOT
  return 'pipelines'
}

const OBJECT_OUTPUT = { type: 'object', additionalProperties: true } as const

/** output.schema 声明的规范值类型。 */
type JsonObjectValue = Record<string, JsonValue>

/**
 * 强类型 CLI 结果（PipelineManifest / StageChangeResult / 摘要…）与规范值
 * 的类型投影适配：结构上完全等价（纯 JSON），仅 TS 类型不同。
 */
const asObjectValue = <T>(v: T): JsonObjectValue => v as unknown as JsonObjectValue
const asArrayValue = <T>(v: T[]): JsonObjectValue[] => v as unknown as JsonObjectValue[]

export function apply(ctx: Context, config: Config) {
  const runner = createRunner({
    bin: config.reqpipeBin,
    args: config.reqpipeArgs,
    root: resolveRoot(config),
    env: config.env as NodeJS.ProcessEnv,
  } satisfies RunnerOptions)

  console.log(`[reqpipe] plugin loaded (root=${resolveRoot(config)}, bin=${config.reqpipeBin})`)

  ctx.tools.register(defineTool({
    name: 'reqpipe_init',
    description: '初始化需求流水线根目录：创建目录（若不存在）并写入约定说明 README。通常无需手动调用，reqpipe_create 会自动创建根目录。',
    parameters: {},
    output: {
      schema: { type: 'string' },
      render: (_args, value) => text(value),
    },
    async execute(_args, exec) {
      const stdout = await runner.run(['init'], exec.signal)
      return stdout.trim()
    },
  }))

  ctx.tools.register(defineTool({
    name: 'reqpipe_create',
    description: '创建一个研发需求流水线（阶段：需求→方案→评审→开发）。每个需求一个独立工作目录，自动生成需求文档模板。返回新需求清单（含 ID、各阶段状态）。light 为 true 时声明轻量流程（方案/评审可跳过）。',
    parameters: {
      title: { type: 'string', required: true, description: '需求标题' },
      id: { type: 'string', description: '需求 ID，默认自动生成（REQ-001 起递增）' },
      description: { type: 'string', description: '需求描述' },
      light: { type: 'boolean', description: '轻量流程：方案/评审阶段标记为可选，可跳过' },
    },
    output: {
      schema: OBJECT_OUTPUT,
      render: (_args, value) => text(renderCreate(value as unknown as PipelineManifest)),
    },
    async execute(args, exec) {
      const cliArgs = ['create', '--json']
      if (args.id) cliArgs.push('--id', args.id)
      if (args.description) cliArgs.push('--desc', args.description)
      if (args.light) cliArgs.push('--light')
      cliArgs.push(args.title)
      return asObjectValue(await runner.runJson<PipelineManifest>(cliArgs, exec.signal))
    },
    presentCall: args => ({ card: 'generic', title: `创建需求：${args.title}`, kind: 'edit' }),
  }))

  ctx.tools.register(defineTool({
    name: 'reqpipe_advance',
    description: '推进需求的当前阶段（需求→方案→开发）：完成当前阶段并进入下一阶段，自动生成下一阶段文档模板。要求当前阶段文档已存在，否则报错；force 为 true 时缺文档也可推进。注意：评审（review）阶段不能 advance——必须用 reqpipe_review 完成评审，且评审人不能是方案作者（同一 agent 不能自写自评）。操作者身份自动取当前 agent 会话 id。返回 {pipeline, messages}。',
    parameters: {
      id: { type: 'string', required: true, description: '需求 ID，如 REQ-001' },
      force: { type: 'boolean', description: '当前阶段缺少文档时强制推进' },
    },
    output: {
      schema: OBJECT_OUTPUT,
      render: (_args, value) => text(renderChange(value as unknown as StageChangeResult)),
    },
    async execute(args, exec) {
      const cliArgs = ['advance', '--json', args.id]
      if (args.force) cliArgs.push('--force')
      if (exec.agent?.id) cliArgs.push('--by', exec.agent.id)
      return asObjectValue(await runner.runJson<StageChangeResult>(cliArgs, exec.signal))
    },
    presentCall: args => ({ card: 'generic', title: `推进阶段：${args.id}`, kind: 'execute' }),
  }))

  ctx.tools.register(defineTool({
    name: 'reqpipe_review',
    description: '评审需求的方案（design 阶段）：评审人必须与方案作者不同（同一 agent 不能自写自评），评审记录（评审人/结论/意见/时间）写入 REVIEW.md 与 pipeline.json 留档。verdict=approve 评审通过并进入开发；verdict=reject 评审不通过，方案阶段打回返工，重新完善 DESIGN.md 后再评审。评审人身份：由另一个 agent 会话 id 或人工评审的评审人姓名（reject 后返工再评审可多次调用，每轮留档）。',
    parameters: {
      id: { type: 'string', required: true, description: '需求 ID，如 REQ-001' },
      reviewer: { type: 'string', required: true, description: '评审人身份：与方案作者不同的其他 agent 会话 id，或人工评审时的评审人姓名' },
      verdict: { type: 'string', required: true, enum: ['approve', 'reject'], description: '评审结论：approve=通过，reject=不通过（打回返工）' },
      comment: { type: 'string', description: '评审意见（可选）' },
    },
    output: {
      schema: OBJECT_OUTPUT,
      render: (_args, value) => text(renderChange(value as unknown as StageChangeResult)),
    },
    async execute(args, exec) {
      const cliArgs = ['review', '--json', args.id, '--by', args.reviewer, '--verdict', args.verdict]
      if (args.comment) cliArgs.push('--comment', args.comment)
      return asObjectValue(await runner.runJson<StageChangeResult>(cliArgs, exec.signal))
    },
    presentCall: args => ({ card: 'generic', title: `评审方案：${args.id}（${args.verdict === 'approve' ? '通过' : '不通过'}）`, kind: 'other' }),
  }))

  ctx.tools.register(defineTool({
    name: 'reqpipe_skip',
    description: '跳过需求的方案（design）或评审（review）阶段——轻量流程的入口。仅这两个阶段可跳过（需求/开发不可跳过），且必须提供原因 reason；原因会写入 pipeline.json 历史与提交清单，留档可查。注意：方案作者不能跳过自己方案的评审（评审须由其他 agent 或人工决定）。操作者身份自动取当前 agent 会话 id。返回 {pipeline, messages}。',
    parameters: {
      id: { type: 'string', required: true, description: '需求 ID，如 REQ-001' },
      stage: {
        type: 'string', required: true, enum: ['design', 'review'],
        description: '要跳过的阶段：design=方案，review=评审',
      },
      reason: { type: 'string', required: true, description: '跳过原因（必填，会留档）' },
    },
    output: {
      schema: OBJECT_OUTPUT,
      render: (_args, value) => text(renderChange(value as unknown as StageChangeResult)),
    },
    async execute(args, exec) {
      const cliArgs = ['skip', '--json', args.id, args.stage, '--reason', args.reason]
      if (exec.agent?.id) cliArgs.push('--by', exec.agent.id)
      return asObjectValue(await runner.runJson<StageChangeResult>(cliArgs, exec.signal))
    },
    presentCall: args => ({ card: 'generic', title: `跳过阶段：${args.id} ${args.stage}`, kind: 'other' }),
  }))

  ctx.tools.register(defineTool({
    name: 'reqpipe_list',
    description: '列出流水线根目录下的所有需求流水线（ID、标题、当前阶段、状态、类型）。返回摘要数组；无流水线时返回空数组。',
    parameters: {},
    output: {
      schema: { type: 'array', items: { type: 'object', additionalProperties: true } },
      render: (_args, value) => text(renderList(value as unknown as PipelineSummary[])),
    },
    async execute(_args, exec) {
      return asArrayValue(await runner.runJson<PipelineSummary[]>(['list', '--json'], exec.signal))
    },
    presentCall: () => ({ card: 'generic', title: '列出所有需求流水线', kind: 'search' }),
  }))

  ctx.tools.register(defineTool({
    name: 'reqpipe_show',
    description: '查看某个需求流水线的完整详情：阶段状态（含可选标记与跳过原因）、操作历史。返回完整清单。',
    parameters: {
      id: { type: 'string', required: true, description: '需求 ID，如 REQ-001' },
    },
    output: {
      schema: OBJECT_OUTPUT,
      render: (_args, value) => text(renderShow(value as unknown as PipelineManifest)),
    },
    async execute(args, exec) {
      return asObjectValue(await runner.runJson<PipelineManifest>(['show', '--json', args.id], exec.signal))
    },
    presentCall: args => ({ card: 'generic', title: `查看需求：${args.id}`, kind: 'read' }),
  }))

  ctx.tools.register(defineTool({
    name: 'reqpipe_checklist',
    description: '生成某个需求的提交清单（Markdown）：按阶段列出待提交文件、跳过原因与汇总统计。适合提交/合并前核对阶段产物是否齐备。',
    parameters: {
      id: { type: 'string', required: true, description: '需求 ID，如 REQ-001' },
    },
    output: {
      schema: OBJECT_OUTPUT,
      render: (_args, value) => text((value as unknown as { markdown: string }).markdown),
    },
    async execute(args, exec) {
      return asObjectValue(await runner.runJson<{ markdown: string }>(['checklist', '--json', args.id], exec.signal))
    },
    presentCall: args => ({ card: 'generic', title: `生成提交清单：${args.id}`, kind: 'read' }),
  }))
}
