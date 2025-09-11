import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from '../App'

vi.stubGlobal('EventSource', class {
  onmessage: ((this: EventSource, ev: MessageEvent) => any) | null = null
  onerror: ((this: EventSource, ev: Event) => any) | null = null
  close() {}
  constructor(url: string) {}
} as any)

vi.mock('../api', () => {
  return {
    Api: {
      getPaths: async () => ({ current: { source_dir: '', target_dir: '' }, staged: { source_dir: '', target_dir: '' } }),
      getStatus: async () => ({ counts: {}, processed: 0, total: 0, ready: [] }),
      getReady: async () => ([{ path: '/music/Album', name: 'Album' }]),
      getDecision: async () => ({ metadata: { folder_name: 'Album', total_files: 1, files: [{ filename: 'x.mp3' }] }, proposal: { artist: 'X', album: 'Y', year: 2000, release_type: 'album' } }),
      postDecision: async () => ({}),
      getDebugJobs: async () => ({ counts: {}, recent: [] }),
    }
  }
})

test('overrides persisted in localStorage across refresh', async () => {
  // First render: wait for decision fields to hydrate, then change artist
  const { unmount } = render(<App />)
  const artist = (await screen.findByPlaceholderText('Artist')) as HTMLInputElement
  await waitFor(() => expect(artist.value).toBe('X'))
  fireEvent.change(artist, { target: { value: 'Persist Me' } })
  unmount()

  // Second render: value should be restored into the input
  render(<App />)
  const artist2 = (await screen.findByPlaceholderText('Artist')) as HTMLInputElement
  await waitFor(() => expect(artist2.value).toBe('Persist Me'))
})


