import { useMemo, useState } from 'react'
import { Api } from '../api'
import type { PathsResponse } from '../types'
import { DirectoryPickerModal } from './DirectoryPickerModal'

type Props = {
  paths: PathsResponse | null
  onRefresh: () => Promise<void>
  onToggleDebug: () => void
}

export function PathsHeader({ paths, onRefresh, onToggleDebug }: Props) {
  const [busy, setBusy] = useState(false)
  const [applyHidden, setApplyHidden] = useState(false)
  const [pickerOpen, setPickerOpen] = useState<null | 'source' | 'target'>(null)

  const curSource = paths?.current.source_dir || ''
  const curTarget = paths?.current.target_dir || ''
  const stagedSource = paths?.staged.source_dir || ''
  const stagedTarget = paths?.staged.target_dir || ''

  const stagedInfo = useMemo(() => {
    const infos: string[] = []
    if (stagedSource) infos.push(`Staged source: ${stagedSource}`)
    if (stagedTarget) infos.push(`Staged target: ${stagedTarget}`)
    return infos.join('  |  ')
  }, [stagedSource, stagedTarget])

  function openPicker(which: 'source' | 'target') {
    if (busy) return
    setPickerOpen(which)
  }

  async function choosePath(path: string) {
    if (!pickerOpen) return
    const body: any = {}
    if (pickerOpen === 'source') body.source_dir = path
    else body.target_dir = path
    await Api.stagePaths(body)
    await onRefresh()
    setPickerOpen(null)
  }

  async function applyPaths(action: 'confirm' | 'cancel') {
    if (action === 'confirm') { setBusy(true); setApplyHidden(true) }
    try {
      await Api.stagePaths({ action })
      await onRefresh()
    } finally {
      setBusy(false)
      if (action === 'cancel') setApplyHidden(false)
    }
  }

  return (
    <header style={{ padding: '8px 12px', background: '#101820', color: '#fff', display: 'flex', alignItems: 'center', gap: 12 }}>
      <div id="paths">
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 6 }}>
          <b>Source:</b> <span>{curSource || '-'}</span>
          <button onClick={() => openPicker('source')} disabled={busy}>Change</button>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <b>Target:</b> <span>{curTarget || '-'}</span>
          <button onClick={() => openPicker('target')} disabled={busy}>Change</button>
        </div>
        {!applyHidden && (
          <div style={{ color: '#9bb', fontSize: 12, marginTop: 6 }}>{stagedInfo}</div>
        )}
        {(stagedSource || stagedTarget) && !applyHidden && (
          <div style={{ marginTop: 6 }}>
            <button onClick={() => applyPaths('confirm')} disabled={busy}>Confirm</button>
            <button onClick={() => applyPaths('cancel')} disabled={busy}>Cancel</button>
          </div>
        )}
      </div>
      <div style={{ flex: 1 }} />
      <button onClick={onToggleDebug} style={{ padding: '4px 8px' }}>Debug</button>

      <DirectoryPickerModal
        isOpen={!!pickerOpen}
        initialPath={(pickerOpen === 'source' ? (stagedSource || curSource) : (stagedTarget || curTarget)) || '/'}
        title={`Select ${pickerOpen || ''} directory`}
        onClose={() => setPickerOpen(null)}
        onChoose={choosePath}
      />
    </header>
  )
}


