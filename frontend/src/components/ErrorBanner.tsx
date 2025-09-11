type Props = {
  message: string
  onClose: () => void
}

export function ErrorBanner({ message, onClose }: Props) {
  if (!message) return null
  return (
    <div style={{
      margin: '10px',
      padding: '10px 12px',
      borderRadius: 6,
      border: '1px solid #f2c4c4',
      background: '#fff5f5',
      color: '#6b1111',
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }}>
      <div style={{ fontWeight: 700 }}>Error</div>
      <div style={{ flex: 1 }}>{message}</div>
      <button onClick={onClose} style={{ background: '#6b1111', color: '#fff', border: 'none', borderRadius: 4, padding: '4px 8px' }}>Dismiss</button>
    </div>
  )
}


