import type { Decision, DebugJobs, ListedEntry, PathsResponse, ReadyItem, Status } from './types'

export async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as T
}

export const Api = {
  getPaths(): Promise<PathsResponse> {
    return fetchJSON<PathsResponse>('/api/paths')
  },
  stagePaths(body: Partial<{ source_dir: string; target_dir: string }> | { action: 'confirm' | 'cancel' }): Promise<any> {
    return fetchJSON('/api/paths', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },
  getStatus(): Promise<Status> {
    return fetchJSON<Status>('/api/status')
  },
  getReady(limit = 50): Promise<ReadyItem[]> {
    return fetchJSON<ReadyItem[]>(`/api/ready?limit=${limit}`)
  },
  getDecision(path: string): Promise<Decision> {
    return fetchJSON<Decision>('/api/folder?path=' + encodeURIComponent(path))
  },
  postDecision(body: { path: string; action: 'accept' | 'reconsider' | 'skip'; proposal?: any; feedback?: string }): Promise<any> {
    return fetchJSON('/api/decision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  },
  listDirectory(path: string): Promise<{ entries: ListedEntry[]; parent: string }> {
    return fetchJSON<{ entries: ListedEntry[]; parent: string }>('/api/list?path=' + encodeURIComponent(path))
  },
  getDebugJobs(limit = 25): Promise<DebugJobs> {
    return fetchJSON<DebugJobs>(`/api/debug/jobs?limit=${limit}`)
  },
}

export function connectEvents(onMessage: (statusDelta: Partial<Status> & { counts: Record<string, number>; processed: number; total: number }) => void): () => void {
  const es = new EventSource('/api/events')
  es.onmessage = (e) => {
    try {
      const s = JSON.parse(e.data)
      onMessage(s)
    } catch {}
  }
  es.onerror = () => {
    es.close()
    // caller may choose to reconnect
  }
  return () => es.close()
}


