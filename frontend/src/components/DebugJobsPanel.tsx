import type { DebugJobs } from '../types'

type Props = { open: boolean; onClose: () => void; data: DebugJobs | null }

export function DebugJobsPanel({ open, onClose, data }: Props) {
  if (!open) return null
  return (
    <div style={{ position: 'fixed', right: 12, bottom: 12, width: 620, maxHeight: '50vh', overflow: 'auto', background: '#fff', color: '#000', border: '1px solid #ccc', borderRadius: 6, boxShadow: '0 2px 8px rgba(0,0,0,0.2)', padding: 10, zIndex: 9999, textAlign: 'left' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ fontWeight: 700 }}>Debug Jobs</div>
        <div style={{ flex: 1 }} />
        <button onClick={onClose} style={{ padding: '2px 6px' }}>Close</button>
      </div>
      {data ? (
        <div>
          <div style={{ fontSize: 12, color: '#666', margin: '6px 0' }}>
            queued: {data.counts['queued']||0} | analyzing: {data.counts['analyzing']||0} | ready: {data.counts['ready']||0} | accepted: {data.counts['accepted']||0} | moving: {data.counts['moving']||0} | skipped: {data.counts['skipped']||0} | error: {data.counts['error']||0} | completed: {data.counts['completed']||0}
          </div>
          <pre style={{
            maxHeight: 260,
            overflow: 'auto',
            margin: 0,
            padding: 8,
            background: '#0b0d0e',
            color: '#d1e0e0',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
            fontSize: 12,
            borderRadius: 4,
            textAlign: 'left'
          }}>
{data.recent.map((j) => `[${j.status}] ${j.folder_path} (${j.job_type})${j.error ? `\n  error: ${j.error}` : ''}`).join('\n')}
          </pre>
        </div>
      ) : (
        <div style={{ fontSize: 12, color: '#999' }}>No data</div>
      )}
    </div>
  )
}


