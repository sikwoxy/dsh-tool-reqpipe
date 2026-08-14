/**
 * 渲染：把工具的规范 JSON 值转成模型可见的中文文本。
 * 与 Python CLI 的展示文案保持一致。
 */

import type { ContentBlock } from '@deepseek-ai/dsh-llm'
import type { PipelineManifest, PipelineSummary, StageChangeResult } from './types.ts'

const STAGE_STATUS_TEXT = { pending: '待开始', done: '已完成', skipped: '已跳过', rejected: '需返工' } as const

export function text(value: string): ContentBlock[] {
  return [{ type: 'text', text: value }]
}

export function renderCreate(m: PipelineManifest): string {
  const cur = m.stages.find(s => s.status === 'pending') ?? m.stages[m.stages.length - 1]!
  return [
    `✔ 需求已创建：${m.id}（${m.title}）`,
    `  类型：${m.light ? '轻量流程' : '标准流程'}`,
    `  当前阶段：${cur.label}（请完善 ${cur.dir}/${cur.doc}）`,
  ].join('\n')
}

export function renderChange(r: StageChangeResult): string {
  return r.messages.join('\n')
}

export function renderList(pipes: PipelineSummary[]): string {
  if (pipes.length === 0) return '（暂无需求流水线，可用 reqpipe_create 创建）'
  const rows = pipes.map(p => {
    const cur = p.stages.find(s => s.status === 'pending' || s.status === 'rejected')
    return [
      `- ${p.id}　${p.title}`,
      `　当前阶段：${cur ? cur.label : '—'}`,
      `　状态：${p.status === 'completed' ? '已完成' : '进行中'}`,
      `　类型：${p.light ? '轻量' : '标准'}`,
    ].join('')
  })
  return `需求流水线（${pipes.length} 条）：\n${rows.join('\n')}`
}

export function renderShow(m: PipelineManifest): string {
  const lines = [
    `需求：${m.title}（${m.id}）`,
    `类型：${m.light ? '轻量流程（方案/评审可跳过）' : '标准流程'}`,
    `状态：${m.stages.every(s => s.status !== 'pending' && s.status !== 'rejected') ? '已完成' : '进行中'}`,
    `创建：${m.created_at}`,
  ]
  if (m.description) lines.push(`描述：${m.description}`)
  lines.push('', '阶段：')
  for (const s of m.stages) {
    const mark = s.status === 'done' ? '✔' : s.status === 'skipped' ? '⏭' : s.status === 'rejected' ? '✘' : '·'
    const opt = s.skippable ? '（可选）' : ''
    let extra = ''
    if (s.status === 'skipped') extra = `　跳过原因：${s.reason ?? ''}（by ${s.skipped_by ?? '—'}）`
    else if (s.status === 'done') extra = `　完成人：${s.done_by ?? '—'}`
    else if (s.status === 'rejected') extra = `　需返工（作者：${s.done_by ?? '—'}）`
    lines.push(`  ${mark} ${s.label}${opt}　${s.dir}/${s.doc}　[${STAGE_STATUS_TEXT[s.status]}${extra}]`)
    for (const r of s.reviews ?? []) {
      const verdict = r.verdict === 'approve' ? '通过' : '不通过'
      const note = r.comment ? `，意见：${r.comment}` : ''
      lines.push(`      · 评审[${verdict}] by ${r.by} @ ${r.at}${note}`)
    }
  }
  lines.push('', '历史：')
  for (const h of m.history) lines.push(`  ${h.at}  ${h.detail}`)
  return lines.join('\n')
}
