import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

type Status = {
  counts: Record<string, number>
  processed: number
  total: number
  ready: { path: string; name: string }[]
}

type PathsResponse = {
  current: { source_dir: string; target_dir: string }
  staged: { source_dir: string; target_dir: string }
}

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as T
}

function App() {
  const [paths, setPaths] = useState<PathsResponse | null>(null)
  const [status, setStatus] = useState<Status | null>(null)
  const [currentDecision, setCurrentDecision] = useState<any | null>(null)
  const [selectedPath, setSelectedPath] = useState<string>('')
  const [busyPaths, setBusyPaths] = useState(false)
  const [applyHidden, setApplyHidden] = useState(false)
  const [readyQueue, setReadyQueue] = useState<{ path: string; name: string }[]>([])
  const [loadingDecision, setLoadingDecision] = useState(false)
  const pickerOpen = useRef<null | 'source' | 'target'>(null)
  const [pickCurrent, setPickCurrent] = useState<string>('/')
  const [pickList, setPickList] = useState<{ name: string; path: string }[]>([])
  const parentPath = useRef<string>('')

  const curSource = paths?.current.source_dir || ''
  const curTarget = paths?.current.target_dir || ''
  const stagedSource = paths?.staged.source_dir || ''
  const stagedTarget = paths?.staged.target_dir || ''

  async function refreshPaths() {
    const p = await fetchJSON<PathsResponse>('/api/paths')
    setPaths(p)
  }

  async function refreshStatus() {
    const s = await fetchJSON<Status>('/api/status')
    setStatus(s)
    setReadyQueue(s.ready || [])
    if (!currentDecision) {
      await loadNextReady(s.ready)
    }
  }

  async function loadDecision(path: string) {
    try {
      const d = await fetchJSON<any>('/api/folder?path=' + encodeURIComponent(path))
      setCurrentDecision(d)
      setSelectedPath(path)
      return true
    } catch (e) {
      return false
    }
  }

  async function loadNextReady(candidates?: { path: string; name: string }[]) {
    if (loadingDecision) return
    setLoadingDecision(true)
    try {
      const list = candidates ?? readyQueue
      for (const item of list) {
        const ok = await loadDecision(item.path)
        if (ok) return
      }
      // fetch fresh list and try once more
      const fresh = await fetchJSON<{ path: string; name: string }[]>('/api/ready?limit=20')
      setReadyQueue(fresh)
      for (const item of fresh) {
        const ok = await loadDecision(item.path)
        if (ok) return
      }
      setCurrentDecision(null)
    } finally {
      setLoadingDecision(false)
    }
  }

  async function decide(path: string, action: 'accept' | 'reconsider' | 'skip', proposal?: any, feedback?: string) {
    await fetchJSON('/api/decision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, action, proposal, feedback }),
    })
    setReadyQueue((q) => q.filter((i) => i.path !== path))
    setCurrentDecision(null)
    await loadNextReady()
    await refreshStatus()
  }

  function connectSSE() {
    const es = new EventSource('/api/events')
    es.onmessage = (e) => {
      try {
        const s = JSON.parse(e.data)
        setStatus((prev) => (prev ? { ...prev, ...s } : { counts: s.counts, processed: s.processed, total: s.total, ready: [] }))
      } catch {}
    }
    es.onerror = () => {
      es.close()
      setTimeout(connectSSE, 2000)
    }
  }

  useEffect(() => {
    refreshPaths();
    refreshStatus();
    connectSSE();
  }, [])

  function openPicker(which: 'source' | 'target') {
    if (busyPaths) return
    pickerOpen.current = which
    const desired = which === 'source' ? (stagedSource || curSource) : (stagedTarget || curTarget)
    const start = desired || '/'
    setPickCurrent(start)
    ;(async () => {
      const d = await fetchJSON<{ entries: { name: string; path: string }[]; parent: string }>('/api/list?path=' + encodeURIComponent(start))
      setPickList(d.entries)
      parentPath.current = d.parent
    })()
    ;(document.getElementById('picker') as HTMLDivElement | null)?.style && ((document.getElementById('picker') as HTMLDivElement).style.display = 'flex')
  }

  function closePicker() {
    pickerOpen.current = null
    const picker = document.getElementById('picker') as HTMLDivElement | null
    if (picker) picker.style.display = 'none'
  }

  async function listDir(dir: string) {
    setPickCurrent(dir)
    const d = await fetchJSON<{ entries: { name: string; path: string }[]; parent: string }>('/api/list?path=' + encodeURIComponent(dir))
    setPickList(d.entries)
    parentPath.current = d.parent
  }

  async function chooseCurrent() {
    if (!pickerOpen.current) return
    const body: any = {}
    if (pickerOpen.current === 'source') body.source_dir = pickCurrent
    else body.target_dir = pickCurrent
    await fetchJSON('/api/paths', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    await refreshPaths()
    closePicker()
  }

  async function applyPaths(action: 'confirm' | 'cancel') {
    if (action === 'confirm') { setBusyPaths(true); setApplyHidden(true) }
    try {
      await fetchJSON('/api/paths', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) })
      await refreshPaths()
      await refreshStatus()
    } finally {
      setBusyPaths(false)
      if (action === 'cancel') setApplyHidden(false)
    }
  }

  const stagedInfo = useMemo(() => {
    const infos: string[] = []
    if (stagedSource) infos.push(`Staged source: ${stagedSource}`)
    if (stagedTarget) infos.push(`Staged target: ${stagedTarget}`)
    return infos.join('  |  ')
  }, [stagedSource, stagedTarget])

  return (
      <div>
      <header style={{ padding: '8px 12px', background: '#101820', color: '#fff' }}>
        <div id="paths">
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 6 }}>
            <b>Source:</b> <span id="curSource">{curSource || '-'}</span>
            <button id="changeSourceBtn" onClick={() => openPicker('source')} disabled={busyPaths}>Change</button>
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <b>Target:</b> <span id="curTarget">{curTarget || '-'}</span>
            <button id="changeTargetBtn" onClick={() => openPicker('target')} disabled={busyPaths}>Change</button>
          </div>
          {!applyHidden && (
            <div id="staged" style={{ color: '#9bb', fontSize: 12, marginTop: 6 }}>{stagedInfo}</div>
          )}
          {(stagedSource || stagedTarget) && !applyHidden && (
            <div id="applyBtns" style={{ marginTop: 6 }}>
              <button onClick={() => applyPaths('confirm')} disabled={busyPaths}>Confirm</button>
              <button onClick={() => applyPaths('cancel')} disabled={busyPaths}>Cancel</button>
            </div>
          )}
        </div>
      </header>

      <div id="picker" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'none', alignItems: 'center', justifyContent: 'center' }}>
        <div className="dialog" style={{ background: '#fff', color: '#000', width: 640, maxHeight: '70vh', overflow: 'auto', borderRadius: 6, padding: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ fontWeight: 700 }}>Select directory</div>
            <div style={{ flex: 1 }} />
            <button onClick={closePicker}>Close</button>
          </div>
          <div style={{ marginTop: 6 }}>
            <div>Current: <span id="pickPath">{pickCurrent}</span></div>
            <div style={{ marginTop: 4 }}>
              <button onClick={() => parentPath.current && listDir(parentPath.current)}>Up</button>
              <button onClick={chooseCurrent}>Select this</button>
            </div>
            <ul id="pickList" style={{ marginTop: 6, listStyle: 'none', paddingLeft: 0 }}>
              {pickList.map((e) => (
                <li key={e.path} style={{ padding: '4px 0', cursor: 'pointer' }} onClick={() => listDir(e.path)}>
                  {e.name}/
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="grid" style={{ display: 'grid', gridTemplateColumns: '2fr 3fr 2fr', gap: 10, padding: 10 }}>
        <div className="panel" style={{ border: '1px solid #ddd', padding: 10, borderRadius: 4 }}>
          <div className="title" style={{ fontWeight: 700, marginBottom: 6 }}>Background</div>
          <div id="bg">
            {status ? (
              <>Queue: {status.counts["queued"] || 0}
              {" | Analyzing: "}{status.counts["analyzing"] || 0}
              {" | Ready: "}{status.counts["ready"] || 0}
              {" | Moving: "}{status.counts["moving"] || 0}
              {" | Skipped: "}{status.counts["skipped"] || 0}
              {" | Errors: "}{status.counts["error"] || 0}
              {" | Completed: "}{status.counts["completed"] || 0}
              {" | Processed: "}{status.processed}/{status.total}</>
            ) : '-' }
          </div>
        </div>
        <div className="panel" style={{ border: '1px solid #ddd', padding: 10, borderRadius: 4 }}>
          <div className="title" style={{ fontWeight: 700, marginBottom: 6 }}>Current Decision</div>
          <div id="current">
            {!currentDecision ? 'Waiting for ready proposals...' : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 10 }}>
                <div style={{ textAlign: 'right' }}>
                  <div><b>Folder:</b></div>
                  <div><b>Files:</b></div>
                  <div><b>Artist:</b></div>
                  <div><b>Album:</b></div>
                  <div><b>Year:</b></div>
                  <div><b>Type:</b></div>
                  <div><b>Reasoning:</b></div>
                </div>
                <div style={{ textAlign: 'left' }}>
                  <div>{currentDecision.metadata.folder_name}</div>
                  <div>{currentDecision.metadata.total_files}</div>
                  <div>{currentDecision.proposal.artist}</div>
                  <div>{currentDecision.proposal.album}</div>
                  <div>{currentDecision.proposal.year}</div>
                  <div>{currentDecision.proposal.release_type}</div>
                  <div>{(currentDecision.proposal.reasoning || '').slice(0, 300)}</div>
                </div>
              </div>
            )}
          </div>
          <div id="actions" style={{ marginTop: 8 }}>
            {currentDecision && (
              <>
                <button onClick={() => decide(selectedPath, 'accept', currentDecision.proposal)}>Accept</button>
                <button onClick={() => {
                  const fb = window.prompt('Feedback?')
                  if (fb !== null) decide(selectedPath, 'reconsider', undefined, fb)
                }}>Reconsider</button>
                <button onClick={() => decide(selectedPath, 'skip')}>Skip</button>
              </>
            )}
          </div>
        </div>
        <div className="panel" style={{ border: '1px solid #ddd', padding: 10, borderRadius: 4 }}>
          <div className="title" style={{ fontWeight: 700, marginBottom: 6 }}>Ready</div>
          <ul id="ready">
            {status?.ready?.length ? status.ready.slice(0, 10).map((item) => (
              <li key={item.path} style={{ cursor: 'pointer' }} onClick={() => loadDecision(item.path)}>{item.name}</li>
            )) : <li>No ready items yet</li>}
          </ul>
        </div>
      </div>
    </div>
  )
}

export default App
