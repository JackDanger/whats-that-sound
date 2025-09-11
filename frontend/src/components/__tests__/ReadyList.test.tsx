import { render, screen, fireEvent } from '@testing-library/react'
import { ReadyList } from '../../components/ReadyList'

test('renders ready count badge and handles selection', () => {
  const items = [
    { path: '/a', name: 'A' },
    { path: '/b', name: 'B' },
  ]
  const onSelect = vi.fn()
  render(<ReadyList ready={items} onSelect={onSelect} />)

  expect(screen.getByText('Ready')).toBeInTheDocument()
  expect(screen.getByText('2')).toBeInTheDocument()

  fireEvent.click(screen.getByText('A'))
  expect(onSelect).toHaveBeenCalledWith('/a')
})


