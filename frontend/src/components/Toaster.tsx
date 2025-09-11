import { useEffect } from 'react'

export type Toast = {
  id: string
  message: string
  type?: 'success' | 'error' | 'info'
  ttlMs?: number
}

type Props = {
  toasts: Toast[]
  onRemove: (id: string) => void
}

export function Toaster({ toasts, onRemove }: Props) {
  useEffect(() => {
    const timers = toasts.map((t) => {
      const ttl = t.ttlMs ?? 3000
      const handle = setTimeout(() => onRemove(t.id), ttl)
      return handle
    })
    return () => { timers.forEach(clearTimeout) }
  }, [toasts, onRemove])

  if (!toasts.length) return null
  return (
    <div style={{ position: 'fixed', right: 12, top: 12, display: 'flex', flexDirection: 'column', gap: 8, zIndex: 10000 }}>
      {toasts.map((t) => (
        <div key={t.id} style={{
          minWidth: 220,
          padding: '8px 10px',
          borderRadius: 6,
          border: '1px solid ' + (t.type === 'error' ? '#f2c4c4' : t.type === 'success' ? '#bfe3c7' : '#c9d6e2'),
          background: t.type === 'error' ? '#fff5f5' : t.type === 'success' ? '#f4fff7' : '#f6fbff',
          color: t.type === 'error' ? '#6b1111' : '#1d4d26',
          boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
          display: 'flex',
          alignItems: 'center',
          gap: 8
        }}>
          <div style={{ flex: 1 }}>{t.message}</div>
          <button onClick={() => onRemove(t.id)} style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}>✕</button>
        </div>
      ))}
    </div>
  )
}


