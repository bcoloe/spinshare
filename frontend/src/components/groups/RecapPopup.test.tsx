import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router-dom'
import { renderWithProviders } from '../../test/renderWithProviders'
import RecapPopup from './RecapPopup'
import type { RecapSummary } from '../../types/recap'

const mockUsePendingRecaps = vi.fn()
const mockMarkSeen = vi.fn()
vi.mock('../../hooks/useRecaps', () => ({
  usePendingRecaps: () => mockUsePendingRecaps(),
  useMarkRecapSeen: () => ({ mutate: mockMarkSeen }),
}))

function recap(id: number, groupId: number, groupName: string): RecapSummary {
  return { id, group_id: groupId, group_name: groupName, week_start: '2026-09-14', week_end: '2026-09-21' }
}

const PENDING = [recap(10, 1, 'Alpha Group'), recap(20, 2, 'Beta Group')]

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

describe('RecapPopup', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUsePendingRecaps.mockReturnValue({ data: PENDING })
  })

  it("shows only the current group's pending recap", async () => {
    renderWithProviders(<RecapPopup groupId={1} />)

    expect(await screen.findByText('Alpha Group')).toBeInTheDocument()
    expect(screen.queryByText('Beta Group')).not.toBeInTheDocument()
  })

  it('renders nothing when the current group has no pending recap', () => {
    renderWithProviders(<RecapPopup groupId={3} />)

    expect(screen.queryByText('Your week is ready')).not.toBeInTheDocument()
  })

  it("marks only this group's recap seen on dismiss", async () => {
    const user = userEvent.setup()
    renderWithProviders(<RecapPopup groupId={1} />)

    await user.click(await screen.findByRole('button', { name: 'Dismiss' }))

    expect(mockMarkSeen).toHaveBeenCalledTimes(1)
    expect(mockMarkSeen).toHaveBeenCalledWith({ groupId: 1, recapId: 10 })
    await waitFor(() => expect(screen.queryByText('Alpha Group')).not.toBeInTheDocument())
  })

  it("marks the recap seen and opens this group's recap on view", async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <Routes>
        <Route
          path="*"
          element={
            <>
              <RecapPopup groupId={2} />
              <LocationProbe />
            </>
          }
        />
      </Routes>,
      { route: '/groups/2' },
    )

    await user.click(await screen.findByRole('button', { name: /View recap/ }))

    expect(mockMarkSeen).toHaveBeenCalledTimes(1)
    expect(mockMarkSeen).toHaveBeenCalledWith({ groupId: 2, recapId: 20 })
    expect(screen.getByTestId('location')).toHaveTextContent('/groups/2?tab=info&recap=open')
  })

  it('prompts again for the next group when switching groups while mounted', async () => {
    const user = userEvent.setup()
    const { rerender } = renderWithProviders(<RecapPopup groupId={1} />)

    await user.click(await screen.findByRole('button', { name: 'Dismiss' }))
    rerender(<RecapPopup groupId={2} />)

    expect(await screen.findByText('Beta Group')).toBeInTheDocument()
  })
})
