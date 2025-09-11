import type { Status } from '../types'

type Props = { status: Status | null }

export function WorkerStatus({ status }: Props) {
  return (
    <div className="panel" style={{ border: '1px solid #ddd', padding: 10, borderRadius: 4 }}>
      <div className="title" style={{ fontWeight: 700, marginBottom: 6 }}>Background</div>
      <div>
        {status ? (
          <>
            Queue: {status.counts['queued'] || 0}
            {' | Analyzing: '}{status.counts['analyzing'] || 0}
            {' | Ready: '}{status.counts['ready'] || 0}
            {' | Moving: '}{status.counts['moving'] || 0}
            {' | Skipped: '}{status.counts['skipped'] || 0}
            {' | Errors: '}{status.counts['error'] || 0}
            {' | Completed: '}{status.counts['completed'] || 0}
            {' | Processed: '}{status.processed}/{status.total}
          </>
        ) : '-'}
      </div>
    </div>
  )
}


