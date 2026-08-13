/**
 * reqpipe CLI 类型定义（与 Python 侧 pipeline.json 的结构对应）。
 */

export type StageStatus = 'pending' | 'done' | 'skipped'

export interface PipelineStage {
  name: string
  label: string
  dir: string
  doc: string
  skippable: boolean
  status: StageStatus
  reason: string | null
  skipped_at: string | null
}

export interface PipelineManifest {
  schema: number
  id: string
  title: string
  description: string
  created_at: string
  light: boolean
  stages: PipelineStage[]
  history: Array<{ action: string; stage: string | null; at: string; detail: string }>
}

/** advance / skip 的规范值。 */
export interface StageChangeResult {
  pipeline: PipelineManifest
  messages: string[]
}

/** list --json 的规范值。 */
export interface PipelineSummary {
  id: string
  title: string
  light: boolean
  status: 'completed' | 'in_progress'
  current_stage: string | null
  stages: Array<{
    name: string
    label: string
    status: StageStatus
    reason: string | null
    skipped_at: string | null
  }>
}
