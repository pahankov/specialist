import { describe, it, expect, vi } from 'vitest'
import { toggleHour } from '../components/schedule/hooks'

vi.mock('../api/client', () => ({
  workingHoursApi: {
    create: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('schedule hooks', () => {
  describe('toggleHour', () => {
    it('toggles hour state - activates hour', () => {
      const setActiveHours = vi.fn()
      const dateStr = '2026-01-15'
      toggleHour(dateStr, 10, setActiveHours)
      expect(setActiveHours).toHaveBeenCalled()
    })

    it('toggles hour state - deactivates hour', () => {
      const setActiveHours = vi.fn((fn: any) => {
        const prev = { '2026-01-15-10': true }
        return fn(prev)
      })
      toggleHour('2026-01-15', 10, setActiveHours)
      expect(setActiveHours).toHaveBeenCalled()
    })
  })
})
