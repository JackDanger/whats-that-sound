import { useEffect, useState } from 'react'
import './App.css'
import { Api } from './api'
import type { DebugJobs, Decision, PathsResponse, ReadyItem, Status } from './types'
import { PathsHeader } from './components/PathsHeader'
import { WorkerStatus } from './components/WorkerStatus'
import { DecisionPanel } from './components/DecisionPanel'
import { ReadyList } from './components/ReadyList'
import { DebugJobsPanel } from './components/DebugJobsPanel'
import { ErrorBanner } from './components/ErrorBanner'
import { Toaster, type Toast } from './components/Toaster'

function App() {
  const [paths, setPaths] = useState<PathsResponse | null>(null)
  const [status, setStatus] = useState<Status | null>(null)
  const [currentDecision, setCurrentDecision] = useState<Decision | null>(null)
  const [selectedPath, setSelectedPath] = useState<string>('')
  const [readyQueue, setReadyQueue] = useState<ReadyItem[]>([])
  const [loadingDecision, setLoadingDecision] = useState(false)
  const [debugJobs, setDebugJobs] = useState<DebugJobs | null>(null)
  const [showDebug, setShowDebug] = useState(false)
  const [error, setError] = useState('')
  const [toasts, setToasts] = useState<Toast[]>([])
  const [proposalOverrides, setProposalOverrides] = useState<Record<string, Decision['proposal']>>({})
  const STORAGE_KEY = 'wts_proposal_overrides'

  async function refreshPaths() {
    try {
      const p = await Api.getPaths()
      setPaths(p)
    } catch (e: any) {
      setError(String(e?.message || e || 'Failed to load paths'))
    }
  }

  async function refreshStatus() {
    try {
      const s = await Api.getStatus()
      setStatus(s)
    } catch (e: any) {
      setError(String(e?.message || e || 'Failed to load status'))
    }
    try {
      const fresh = await Api.getReady(50)
      setReadyQueue(fresh)
      if (!currentDecision) {
        await loadNextReady(fresh)
      }
    } catch {}
    // Fetch debug jobs in the background (best-effort)
    try {
      const dj = await Api.getDebugJobs(25)
      setDebugJobs(dj)
    } catch {}
  }

  async function loadDecision(path: string) {
    try {
      const d = await Api.getDecision(path)
      setCurrentDecision(d)
      setSelectedPath(path)
      return true
    } catch (e) {
      setError('Failed to load decision for ' + path)
      return false
    }
  }

  async function loadNextReady(candidates?: ReadyItem[]) {
    if (loadingDecision) return
    setLoadingDecision(true)
    try {
      const list = candidates ?? readyQueue
      for (const item of list) {
        const ok = await loadDecision(item.path)
        if (ok) return
      }
      // fetch fresh list and try once more
      const fresh = await Api.getReady(20)
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

  async function postDecision(action: 'accept' | 'reconsider' | 'skip', feedback?: string, proposalOverride?: Decision['proposal']) {
    if (!selectedPath) return
    try {
      const finalProposal = action === 'accept' ? (proposalOverride || proposalOverrides[selectedPath] || currentDecision?.proposal) : undefined
      await Api.postDecision({ path: selectedPath, action, proposal: finalProposal, feedback })
      const nextList = readyQueue.filter((i) => i.path !== selectedPath)
      setReadyQueue(nextList)
      setCurrentDecision(null)
      setProposalOverrides((m) => { const n = { ...m }; delete n[selectedPath]; return n })
      await loadNextReady(nextList)
      await refreshStatus()
      const id = Math.random().toString(36).slice(2)
      const message = action === 'accept' ? 'Accepted proposal' : action === 'reconsider' ? 'Requested reconsideration' : 'Skipped folder'
      setToasts((t) => [...t, { id, message, type: 'success', ttlMs: 2500 }])
    } catch (e: any) {
      setError(String(e?.message || e || 'Failed to submit decision'))
    }
  }

  function connectSSE() {
    const es = new EventSource('/api/events')
    es.onmessage = (e) => {
      try {
        const s = JSON.parse(e.data)
        setStatus((prev) => (prev ?
          { ...prev, counts: s.counts, processed: s.processed, total: s.total } :
          { counts: s.counts, processed: s.processed, total: s.total, ready: [] }))
        if (s.debug && s.debug.recent) {
          setDebugJobs((prev) => {
            const prevCounts = prev?.counts || {}
            // Rebuild counts from current status counts to stay consistent
            const nextCounts = s.counts || prevCounts
            return { counts: nextCounts, recent: s.debug.recent }
          })
        }
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

  useEffect(() => {
    if (!currentDecision && readyQueue.length > 0 && !loadingDecision) {
      loadNextReady()
    }
  }, [readyQueue, currentDecision, loadingDecision])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!currentDecision) return
      const target = e.target as HTMLElement | null
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || (target as any).isContentEditable)) return
      const key = e.key.toLowerCase()
      if (e.metaKey) return
      if (key === 'a') { postDecision('accept'); e.preventDefault() }
      if (key === 'r') { const fb = window.prompt('Feedback?'); if (fb !== null) postDecision('reconsider', fb); e.preventDefault() }
      if (key === 's') { postDecision('skip'); e.preventDefault() }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [currentDecision])

  // Load persisted overrides on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const data = JSON.parse(raw)
        if (data && typeof data === 'object') setProposalOverrides(data)
      }
    } catch {}
  }, [])

  // Persist overrides whenever they change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(proposalOverrides))
    } catch {}
  }, [proposalOverrides])

  return (
      <div>
      <ErrorBanner message={error} onClose={() => setError('')} />
      <Toaster toasts={toasts} onRemove={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
      <PathsHeader paths={paths} onRefresh={async () => { await refreshPaths(); await refreshStatus() }} onToggleDebug={() => setShowDebug((v) => !v)} />

      <div className="grid" style={{ display: 'grid', gridTemplateColumns: '2fr 3fr 2fr', gap: 10, padding: 10 }}>
        <WorkerStatus status={status} />
        <DecisionPanel
          decision={currentDecision}
          selectedPath={selectedPath}
          readyAvailable={readyQueue.length > 0}
          loading={loadingDecision}
          onReviewNext={() => loadNextReady()}
          onDecide={(action, feedback, proposalOverride) => postDecision(action, feedback, proposalOverride)}
          initialOverrides={proposalOverrides[selectedPath]}
          onProposalChange={(proposal) => { if (selectedPath) setProposalOverrides((m) => ({ ...m, [selectedPath]: proposal })) }}
        />
        <ReadyList ready={readyQueue} onSelect={(p) => loadDecision(p)} />
        {null}
      </div>

      <DebugJobsPanel open={showDebug} data={debugJobs} onClose={() => setShowDebug(false)} />
      <div style={{ padding: 10, color: '#567', fontSize: 12 }}>
        Shortcuts: <b>A</b> Accept, <b>R</b> Reconsider, <b>S</b> Skip
      </div>
    </div>
  )
}

export default App
