import type { ReadyItem } from '../types'

type Props = { ready: ReadyItem[]; onSelect: (path: string) => void }

export function ReadyList({ ready, onSelect }: Props) {
  return (
    <div className="panel" style={{ border: '1px solid #ddd', padding: 10, borderRadius: 4 }}>
      <div className="title" style={{ fontWeight: 700, marginBottom: 6 }}>Ready {ready.length ? <span style={{ background: '#eef6ff', border: '1px solid #c9d6e2', color: '#244c6b', padding: '0 6px', borderRadius: 10, fontSize: 12 }}>{ready.length}</span> : null}</div>
      <ul>
        {ready.length ? (
          ready.slice(0, 10).map((item) => (
            <li key={item.path} style={{ cursor: 'pointer' }} onClick={() => onSelect(item.path)}>
              {item.name}
            </li>
          ))
        ) : (
          <li>No ready items yet</li>
        )}
      </ul>
    </div>
  )
}


