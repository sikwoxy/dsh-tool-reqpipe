/**
 * reqpipe 插件工具组装测试：注册工具后直接调用 ctx.tools.execute，
 * 断言规范值（result.value）与渲染文本（result.content）。
 *
 * 测试通过 `python3 -m reqpipe` 调用 reqpipe CLI；CLI 源码位置由
 * REQPIPE_SRC 环境变量指定（默认指向开发工作区中的 Python 包）。
 */

import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { Context } from '@deepseek-ai/cordis'
import { CallId } from '@deepseek-ai/dsh-llm'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime, { type ToolExecutionResult } from '@deepseek-ai/dsh-tools'
import { apply, Config } from '../src/index.ts'

/**
 * reqpipe Python 源码目录（PYTHONPATH 指向它），可用环境变量覆盖。
 * 默认指向本仓库的 ../python-cli。
 */
const REQPIPE_SRC = process.env.REQPIPE_SRC ?? fileURLToPath(new URL('../../python-cli', import.meta.url))

const testSignal = new AbortController().signal
let root: string
let ctx: Context

function rendered(result: ToolExecutionResult): string {
  return result.content.map(b => (b.type === 'text' ? b.text : '')).join('')
}

async function execute(name: string, args: Record<string, unknown> = {}): Promise<ToolExecutionResult> {
  return ctx.tools.execute({
    signal: testSignal,
    callId: CallId(`reqpipe-${name}-${Math.random()}`),
    name,
    arguments: args,
  })
}

beforeAll(async () => {
  root = mkdtempSync(join(tmpdir(), 'reqpipe-tools-'))
  ctx = new Context()
  await ctx.plugin(SystemPrompt)
  await ctx.plugin(ToolRuntime)
  apply(ctx, Config({
    root,
    reqpipeBin: 'python3',
    reqpipeArgs: ['-m', 'reqpipe'],
    env: { PYTHONPATH: REQPIPE_SRC },
  }))
})

afterAll(() => {
  rmSync(root, { recursive: true, force: true })
})

describe('reqpipe tools', () => {
  it('reqpipe_create returns a typed manifest and renders Chinese text', async () => {
    const r = await execute('reqpipe_create', { title: '登录模块支持记住我', light: true })
    expect(r.isError).toBe(false)
    const m = r.value as { id: string; title: string; light: boolean; stages: unknown[] }
    expect(m.id).toBe('REQ-001')
    expect(m.title).toBe('登录模块支持记住我')
    expect(m.light).toBe(true)
    expect(m.stages).toHaveLength(4)
    expect(rendered(r)).toContain('需求已创建')
    expect(rendered(r)).toContain('REQ-001')
  })

  it('reqpipe_advance completes the current stage and scaffolds the next doc', async () => {
    await execute('reqpipe_create', { title: '导出优化', id: 'REQ-1' })
    const r = await execute('reqpipe_advance', { id: 'REQ-1' })
    expect(r.isError).toBe(false)
    const v = r.value as { pipeline: { stages: Array<{ name: string; status: string }> }; messages: string[] }
    expect(v.pipeline.stages[0]).toMatchObject({ name: 'requirement', status: 'done' })
    expect(v.messages.join(' ')).toContain('需求 阶段已完成')
    expect(rendered(r)).toContain('需求 阶段已完成')
  })

  it('reqpipe_skip records the reason on the stage', async () => {
    const r = await execute('reqpipe_skip', { id: 'REQ-1', stage: 'design', reason: '改动极小' })
    expect(r.isError).toBe(false)
    const v = r.value as { pipeline: { stages: Array<{ name: string; status: string; reason: string | null }> } }
    const design = v.pipeline.stages.find(s => s.name === 'design')!
    expect(design.status).toBe('skipped')
    expect(design.reason).toBe('改动极小')
    expect(rendered(r)).toContain('改动极小')
  })

  it('parameter validation rejects stages outside design/review', async () => {
    const r = await execute('reqpipe_skip', { id: 'REQ-1', stage: 'requirement', reason: 'x' })
    expect(r.isError).toBe(true)
  })

  it('reqpipe_list returns pipeline summaries', async () => {
    const r = await execute('reqpipe_list')
    expect(r.isError).toBe(false)
    const arr = r.value as Array<{ id: string; status: string; current_stage: string | null }>
    expect(arr.map(p => p.id)).toEqual(expect.arrayContaining(['REQ-001', 'REQ-1']))
    expect(rendered(r)).toContain('需求流水线')
  })

  it('reqpipe_show renders stage status and skip reasons', async () => {
    const r = await execute('reqpipe_show', { id: 'REQ-1' })
    expect(r.isError).toBe(false)
    expect(rendered(r)).toContain('需求：导出优化（REQ-1）')
    expect(rendered(r)).toContain('跳过原因：改动极小')
  })

  it('reqpipe_checklist returns a markdown checklist', async () => {
    const r = await execute('reqpipe_checklist', { id: 'REQ-1' })
    expect(r.isError).toBe(false)
    const v = r.value as { markdown: string }
    expect(v.markdown).toContain('# 提交清单')
    expect(v.markdown).toContain('已跳过，原因：改动极小')
  })

  it('reqpipe_show reports unknown pipelines as errors', async () => {
    const r = await execute('reqpipe_show', { id: 'NOPE' })
    expect(r.isError).toBe(true)
    expect(rendered(r)).toContain('未找到')
  })

  it('light flow end-to-end via tools completes the pipeline', async () => {
    await execute('reqpipe_create', { title: '小需求', id: 'REQ-2', light: true })
    await execute('reqpipe_advance', { id: 'REQ-2' })
    await execute('reqpipe_skip', { id: 'REQ-2', stage: 'design', reason: '轻量流程' })
    await execute('reqpipe_skip', { id: 'REQ-2', stage: 'review', reason: '轻量流程' })
    const r = await execute('reqpipe_advance', { id: 'REQ-2' })
    expect(r.isError).toBe(false)
    const v = r.value as { pipeline: { stages: Array<{ status: string }> } }
    expect(v.pipeline.stages.every(s => s.status === 'done' || s.status === 'skipped')).toBe(true)
  })
})
