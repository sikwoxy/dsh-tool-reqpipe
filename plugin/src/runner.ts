/**
 * reqpipe CLI runner：通过 execFile 调用 Python CLI，透传 AbortSignal 取消。
 * 除 init 外，所有调用都附加 `--json`，stdout 即为规范 JSON 值。
 */

import { execFile } from 'node:child_process'

export interface RunnerOptions {
  /** 可执行文件，默认 `reqpipe`（需已安装）；可改为绝对路径。 */
  bin: string
  /** 前置参数，例如 `['-m', 'reqpipe']`（配合 bin='python3'）。 */
  args: string[]
  /** 流水线根目录（绝对路径），作为 `--root` 传入。 */
  root: string
  /** 附加环境变量（合并到 process.env 之上）。 */
  env?: NodeJS.ProcessEnv
}

export class CliRunError extends Error {
  readonly exitCode: number | null
  readonly stdout: string
  readonly stderr: string

  constructor(message: string, exitCode: number | null, stdout: string, stderr: string) {
    super(message)
    this.name = 'CliRunError'
    this.exitCode = exitCode
    this.stdout = stdout
    this.stderr = stderr
  }
}

export interface CliRunner {
  run(args: string[], signal: AbortSignal): Promise<string>
  runJson<T>(args: string[], signal: AbortSignal): Promise<T>
}

export function createRunner(opts: RunnerOptions): CliRunner {
  const run = (args: string[], signal: AbortSignal): Promise<string> =>
    new Promise((resolve, reject) => {
      execFile(
        opts.bin,
        [...opts.args, ...args, '--root', opts.root],
        {
          env: { ...process.env, ...opts.env },
          encoding: 'utf8',
          signal,
          maxBuffer: 64 * 1024 * 1024,
        },
        (error, stdout, stderr) => {
          if (error) {
            const code = (error as { code?: unknown }).code
            reject(new CliRunError(
              stderr.trim() || error.message,
              typeof code === 'number' ? code : null,
              stdout,
              stderr,
            ))
            return
          }
          resolve(stdout)
        },
      )
    })

  return {
    run,
    async runJson<T>(args: string[], signal: AbortSignal): Promise<T> {
      const stdout = await run(args, signal)
      try {
        return JSON.parse(stdout) as T
      } catch {
        throw new Error(`reqpipe 输出不是合法 JSON（前 200 字符：${stdout.slice(0, 200)}）`)
      }
    },
  }
}
