/**
 * reqpipe CLI 类型定义（与 Python 侧 pipeline.json 的结构对应）。
 */

export type StageStatus = 'pending' | 'done' | 'skipped' | 'rejected'

/** 一轮评审记录（评审人/结论/意见/时间），评审阶段可有多轮（reject 返工后再次评审）。 */
export interface ReviewRecord {
  verdict: 'approve' | 'reject'
  by: string
  comment: string | null
  at: string
}

export interface PipelineStage {
  name: string
  label: string
  dir: string
  doc: string
  skippable: boolean
  status: StageStatus
  reason: string | null
  skipped_at: string | null
  /** 完成该阶段的操作者（作者/评审人身份）。 */
  done_by: string | null
  done_at: string | null
  /** 执行跳过的操作者身份。 */
  skipped_by: string | null
  /** 评审阶段打回返工的时间（design 阶段被 reject 时记录）。 */
  rejected_at: string | null
  /** 评审阶段累计的评审记录。 */
  reviews: ReviewRecord[]
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

/** advance / skip / review 的规范值。 */
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
    done_by: string | null
    skipped_by: string | null
    reviews: ReviewRecord[]
  }>
}
