import { useEffect, useState } from 'react'
import { Api } from '../api'
import type { ListedEntry } from '../types'

type Props = {
  isOpen: boolean
  initialPath: string
  title?: string
  onClose: () => void
  onChoose: (path: string) => Promise<void> | void
}

export function DirectoryPickerModal({ isOpen, initialPath, title = 'Select directory', onClose, onChoose }: Props) {
  const [currentPath, setCurrentPath] = useState<string>(initialPath || '/')
  const [entries, setEntries] = useState<ListedEntry[]>([])
  const [parent, setParent] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string>('')

  useEffect(() => {
    if (!isOpen) return
    setCurrentPath(initialPath || '/')
  }, [isOpen, initialPath])

  useEffect(() => {
    if (!isOpen) return
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const d = await Api.listDirectory(currentPath)
        if (!cancelled) {
          setEntries(d.entries)
          setParent(d.parent)
        }
      } catch (e: any) {
        if (!cancelled) setError(String(e?.message || e || 'Failed to list directory'))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [isOpen, currentPath])

  if (!isOpen) return null

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="dialog" style={{ background: '#fff', color: '#000', width: 640, maxHeight: '70vh', overflow: 'auto', borderRadius: 6, padding: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontWeight: 700 }}>{title}</div>
          <div style={{ flex: 1 }} />
          <button onClick={onClose}>Close</button>
        </div>
        <div style={{ marginTop: 6 }}>
          <div>Current: <span>{currentPath}</span></div>
          <div style={{ marginTop: 4, display: 'flex', gap: 8 }}>
            <button onClick={() => parent && setCurrentPath(parent)} disabled={!parent || loading}>Up</button>
            <button onClick={() => onChoose(currentPath)} disabled={loading}>Select this</button>
          </div>
          {error && <div style={{ color: '#b00', fontSize: 12, marginTop: 6 }}>{error}</div>}
          <ul style={{ marginTop: 6, listStyle: 'none', paddingLeft: 0 }}>
            {entries.map((e) => (
              <li key={e.path} style={{ padding: '4px 0', cursor: 'pointer' }} onClick={() => setCurrentPath(e.path)}>
                {e.name}/
              </li>
            ))}
            {!loading && entries.length === 0 && <li style={{ color: '#666' }}>No subdirectories</li>}
          </ul>
        </div>
      </div>
    </div>
  )
}


