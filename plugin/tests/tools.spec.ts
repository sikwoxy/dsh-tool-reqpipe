/**
 * reqpipe 插件工具组装测试：注册工具后直接调用 ctx.tools.execute，
 * 断言规范值（result.value）与渲染文本（result.content）。
 *
 * 测试通过 `python3 -m reqpipe` 调用 reqpipe CLI；CLI 源码位置由
 * REQPIPE_SRC 环境变量指定（默认指向仓库内的 python-cli 包）。
 */

import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { Context } from '@deepseek-ai/cordis'
import { CallId } from '@deepseek-ai/dsh-llm'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime, { type ToolExecutionResult } from '@deepseek-ai/dsh-tools'
import { apply, Config } from '../src/index.ts'

/** reqpipe Python 源码目录（PYTHONPATH 指向它），可用环境变量覆盖；默认探测仓库内 python-cli。 */
const REQPIPE_SRC =
  process.env.REQPIPE_SRC ?? join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'python-cli')

const testSignal = new AbortController().signal
let root: string
let ctx: Context

function rendered(result: ToolExecutionResult): string {
  return result.content.map(b => (b.type === 'text' ? b.text : '')).join('')
}

async function execute(
  name: string,
  args: Record<string, unknown> = {},
  agentId?: string,
): Promise<ToolExecutionResult> {
  return ctx.tools.execute({
    signal: testSignal,
    callId: CallId(`reqpipe-${name}-${Math.random()}`),
    name,
    arguments: args,
    ...(agentId ? { agent: { id: agentId } as never } : {}),
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

  it('review gate: advance on review stage is blocked', async () => {
    await execute('reqpipe_create', { title: '标准需求', id: 'REQ-3' })
    await execute('reqpipe_advance', { id: 'REQ-3' }, 'alice')
    await execute('reqpipe_advance', { id: 'REQ-3' }, 'alice')
    const r = await execute('reqpipe_advance', { id: 'REQ-3' }, 'alice')
    expect(r.isError).toBe(true)
    expect(rendered(r)).toContain('review 动作')
  })

  it('review gate: design author cannot review own design', async () => {
    await execute('reqpipe_create', { title: '导出优化', id: 'REQ-4' })
    await execute('reqpipe_advance', { id: 'REQ-4' }, 'alice')
    await execute('reqpipe_advance', { id: 'REQ-4' }, 'alice')
    const r = await execute('reqpipe_review', { id: 'REQ-4', reviewer: 'alice', verdict: 'approve' })
    expect(r.isError).toBe(true)
    expect(rendered(r)).toContain('不能评审自己的方案')
  })

  it('reqpipe_review approve by another agent enters development', async () => {
    await execute('reqpipe_create', { title: '导出优化', id: 'REQ-5' })
    await execute('reqpipe_advance', { id: 'REQ-5' }, 'alice')
    await execute('reqpipe_advance', { id: 'REQ-5' }, 'alice')
    const r = await execute('reqpipe_review', { id: 'REQ-5', reviewer: 'bob', verdict: 'approve', comment: '方案可行' })
    expect(r.isError).toBe(false)
    const v = r.value as { pipeline: { stages: Array<{ name: string; status: string; done_by: string | null; reviews: unknown[] }> }; messages: string[] }
    const review = v.pipeline.stages.find(s => s.name === 'review')!
    expect(review.status).toBe('done')
    expect(review.done_by).toBe('bob')
    expect(review.reviews).toHaveLength(1)
    expect(rendered(r)).toContain('评审通过')
    expect(rendered(r)).toContain('方案可行')
    const adv = await execute('reqpipe_advance', { id: 'REQ-5' }, 'alice')
    expect(adv.isError).toBe(false)
    const dev = (adv.value as { pipeline: { stages: Array<{ name: string; status: string }> } }).pipeline.stages.find(s => s.name === 'development')!
    expect(dev.status).toBe('done')
  })

  it('review reject sends design back to rework, then approve completes', async () => {
    await execute('reqpipe_create', { title: '登录改造', id: 'REQ-6' })
    await execute('reqpipe_advance', { id: 'REQ-6' }, 'alice')
    await execute('reqpipe_advance', { id: 'REQ-6' }, 'alice')
    const r = await execute('reqpipe_review', { id: 'REQ-6', reviewer: 'bob', verdict: 'reject', comment: '选型有风险' })
    expect(r.isError).toBe(false)
    const v = r.value as { pipeline: { stages: Array<{ name: string; status: string }> }; messages: string[] }
    expect(v.pipeline.stages.find(s => s.name === 'design')!.status).toBe('rejected')
    expect(v.pipeline.stages.find(s => s.name === 'review')!.status).toBe('pending')
    expect(rendered(r)).toContain('打回返工')
    // 返工：推进方案后再评审
    await execute('reqpipe_advance', { id: 'REQ-6' }, 'alice')
    const ok = await execute('reqpipe_review', { id: 'REQ-6', reviewer: 'bob', verdict: 'approve' })
    expect(ok.isError).toBe(false)
    const okv = ok.value as { pipeline: { stages: Array<{ name: string; status: string }> } }
    expect(okv.pipeline.stages.find(s => s.name === 'review')!.status).toBe('done')
  })

  it('design author cannot skip own review via tools', async () => {
    await execute('reqpipe_create', { title: 'x', id: 'REQ-7' })
    await execute('reqpipe_advance', { id: 'REQ-7' }, 'alice')
    await execute('reqpipe_advance', { id: 'REQ-7' }, 'alice')
    const r = await execute('reqpipe_skip', { id: 'REQ-7', stage: 'review', reason: '不需要' }, 'alice')
    expect(r.isError).toBe(true)
    expect(rendered(r)).toContain('不能跳过自己方案的评审')
  })

  it('reqpipe_show renders reviewers and rework status', async () => {
    await execute('reqpipe_create', { title: 'x', id: 'REQ-8' })
    await execute('reqpipe_advance', { id: 'REQ-8' }, 'alice')
    await execute('reqpipe_advance', { id: 'REQ-8' }, 'alice')
    await execute('reqpipe_review', { id: 'REQ-8', reviewer: 'bob', verdict: 'reject', comment: '需返工' })
    const r = await execute('reqpipe_show', { id: 'REQ-8' })
    expect(r.isError).toBe(false)
    expect(rendered(r)).toContain('需返工')
    expect(rendered(r)).toContain('评审[不通过] by bob')
  })
})
