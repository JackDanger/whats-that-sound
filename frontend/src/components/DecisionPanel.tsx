import { useEffect, useState, useMemo } from 'react'
import type { Decision } from '../types'

type Props = {
  decision: Decision | null
  selectedPath: string
  readyAvailable: boolean
  loading: boolean
  onReviewNext: () => void
  onDecide: (action: 'accept' | 'reconsider' | 'skip', feedback?: string, proposalOverride?: Decision['proposal']) => void
  initialOverrides?: Decision['proposal']
  onProposalChange?: (proposal: Decision['proposal']) => void
}

export function DecisionPanel({ decision, selectedPath, readyAvailable, loading, onReviewNext, onDecide, initialOverrides, onProposalChange }: Props) {
  const [artist, setArtist] = useState<string>('')
  const [album, setAlbum] = useState<string>('')
  const [year, setYear] = useState<string>('')

  useEffect(() => {
    if (decision) {
      const src = initialOverrides || decision.proposal
      setArtist(src.artist || '')
      setAlbum(src.album || '')
      setYear(String(src.year || ''))
    } else {
      setArtist('')
      setAlbum('')
      setYear('')
    }
  }, [decision, initialOverrides])

  const yearWarning = useMemo(() => {
    if (!year) return ''
    return isNaN(Number(year)) ? 'Year should be a number' : ''
  }, [year])

  function buildUpdatedProposal(): Decision['proposal'] | undefined {
    if (!decision) return undefined
    return {
      ...decision.proposal,
      artist: artist || undefined,
      album: album || undefined,
      year: year ? (isNaN(Number(year)) ? year : Number(year)) : undefined,
    }
  }
  function handleArtistChange(v: string) {
    setArtist(v)
    if (decision && onProposalChange) {
      const next = {
        ...decision.proposal,
        artist: v || undefined,
        album: album || undefined,
        year: year ? (isNaN(Number(year)) ? year : Number(year)) : undefined,
      }
      onProposalChange(next)
    }
  }
  function handleAlbumChange(v: string) {
    setAlbum(v)
    if (decision && onProposalChange) {
      const next = {
        ...decision.proposal,
        artist: artist || undefined,
        album: v || undefined,
        year: year ? (isNaN(Number(year)) ? year : Number(year)) : undefined,
      }
      onProposalChange(next)
    }
  }
  function handleYearChange(v: string) {
    setYear(v)
    if (decision && onProposalChange) {
      const next = {
        ...decision.proposal,
        artist: artist || undefined,
        album: album || undefined,
        year: v ? (isNaN(Number(v)) ? v : Number(v)) : undefined,
      }
      onProposalChange(next)
    }
  }
  return (
    <div className="panel" style={{ border: '1px solid #ddd', padding: 10, borderRadius: 4 }}>
      <div className="title" style={{ fontWeight: 700, marginBottom: 6 }}>Current Decision</div>
      <div>
        {decision ? (
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>{selectedPath || decision.metadata.folder_path || decision.metadata.folder_name}</div>
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
                <div>{decision.metadata.folder_name}</div>
                <div>{decision.metadata.total_files}</div>
                <div>
                  <input value={artist} onChange={(e) => handleArtistChange(e.target.value)} placeholder="Artist" style={{ width: '100%' }} />
                </div>
                <div>
                  <input value={album} onChange={(e) => handleAlbumChange(e.target.value)} placeholder="Album" style={{ width: '100%' }} />
                </div>
                <div>
                  <input value={year} onChange={(e) => handleYearChange(e.target.value)} placeholder="Year" style={{ width: '100%' }} />
                  {yearWarning && <div style={{ color: '#b00', fontSize: 12, marginTop: 4 }}>{yearWarning}</div>}
                </div>
                <div>{decision.proposal.release_type}</div>
                <div>{(decision.proposal.reasoning || '').slice(0, 300)}</div>
              </div>
            </div>
            {decision.proposal && (decision.proposal.artist || decision.proposal.album) && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontWeight: 700, marginBottom: 4 }}>Proposed Target</div>
                <div style={{
                  padding: '8px 10px',
                  background: '#f6fbff',
                  border: '1px solid #c9d6e2',
                  borderRadius: 4,
                  fontSize: 12
                }}>
                  {`${artist || 'Unknown Artist'} / ${album || 'Unknown Album'}${year ? ` (${year})` : ''}`}
                </div>
              </div>
            )}
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>Directory Contents</div>
              <pre style={{
                maxHeight: 220,
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
{(decision.metadata.files || []).map((f: any) => f.relative_path || f.filename).join('\n')}
              </pre>
            </div>
          </div>
        ) : loading ? (
          <div>
            <div style={{ height: 20, width: '60%', background: '#eee', borderRadius: 4, marginBottom: 8 }} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 10 }}>
              <div style={{ textAlign: 'right' }}>
                {['Folder','Files','Artist','Album','Year','Type','Reasoning'].map((k) => (
                  <div key={k} style={{ margin: '6px 0' }}><b>{k}:</b></div>
                ))}
              </div>
              <div style={{ textAlign: 'left' }}>
                {Array.from({ length: 7 }).map((_, i) => (
                  <div key={i} style={{ height: 14, background: '#eee', borderRadius: 4, margin: '6px 0' }} />
                ))}
              </div>
            </div>
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>Directory Contents</div>
              <div style={{ height: 160, background: '#eee', borderRadius: 4 }} />
            </div>
          </div>
        ) : readyAvailable ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div>Ready items available.</div>
            <button onClick={onReviewNext} disabled={loading}>Review next</button>
          </div>
        ) : (
          'Waiting for ready proposals...'
        )}
      </div>
      <div style={{ marginTop: 8 }}>
        {decision && (
          <>
            <button onClick={() => onDecide('accept', undefined, buildUpdatedProposal())}>Accept (A)</button>
            <button onClick={() => onDecide('accept', undefined, buildUpdatedProposal())}>Accept & Next</button>
            <button onClick={() => {
              const fb = window.prompt('Feedback?')
              if (fb !== null) onDecide('reconsider', fb)
            }}>Reconsider (R)</button>
            <button onClick={() => onDecide('skip')}>Skip (S)</button>
          </>
        )}
      </div>
    </div>
  )
}


