import { render, screen, fireEvent } from '@testing-library/react'
import { DecisionPanel } from '../../components/DecisionPanel'

function makeDecision(): any {
  return {
    metadata: {
      folder_name: 'AlbumDir',
      total_files: 5,
      files: [{ filename: 'a.mp3' }, { filename: 'b.mp3' }],
    },
    proposal: {
      artist: 'Artist',
      album: 'Album',
      year: 2020,
      release_type: 'album',
      reasoning: 'because',
    },
  }
}

test('shows editable proposal fields and sends updated proposal on accept', () => {
  const decision = makeDecision()
  const onDecide = vi.fn()
  render(
    <DecisionPanel
      decision={decision}
      selectedPath="/music/AlbumDir"
      readyAvailable={true}
      loading={false}
      onReviewNext={() => {}}
      onDecide={onDecide}
    />
  )

  const artist = screen.getByPlaceholderText('Artist') as HTMLInputElement
  fireEvent.change(artist, { target: { value: 'New Artist' } })

  const accept = screen.getByText('Accept (A)')
  fireEvent.click(accept)

  expect(onDecide).toHaveBeenCalled()
  const args = onDecide.mock.calls[0]
  expect(args[0]).toBe('accept')
  expect(args[2]).toMatchObject({ artist: 'New Artist' })
})

test('shows year warning when non-numeric', () => {
  const decision = makeDecision()
  render(
    <DecisionPanel
      decision={decision}
      selectedPath="/music/AlbumDir"
      readyAvailable={true}
      loading={false}
      onReviewNext={() => {}}
      onDecide={() => {}}
    />
  )

  const year = screen.getByPlaceholderText('Year') as HTMLInputElement
  fireEvent.change(year, { target: { value: 'twenty' } })
  expect(screen.getByText('Year should be a number')).toBeInTheDocument()
})


