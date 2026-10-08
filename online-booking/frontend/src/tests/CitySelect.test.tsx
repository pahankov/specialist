import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import CitySelect from '../components/common/CitySelect'
import apiClient from '../api/http'

vi.mock('../api/http', () => ({
  default: { get: vi.fn() },
}))

const mockedGet = apiClient.get as unknown as ReturnType<typeof vi.fn>

describe('CitySelect', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedGet.mockResolvedValue({ data: [{ id: 362, name_ru: 'Мичуринск' }] })
  })

  it('shows typed characters while focused (never swallows input)', () => {
    render(<CitySelect value={null} onChange={vi.fn()} />)
    const input = screen.getByLabelText('Город')
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'М' } })
    expect(input).toHaveValue('М')
  })

  it('searches after 2 letters and picks a city', async () => {
    const onChange = vi.fn()
    render(<CitySelect value={null} onChange={onChange} />)
    const input = screen.getByLabelText('Город')
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'Мичу' } })
    await waitFor(() => {
      expect(mockedGet).toHaveBeenCalledWith(
        '/api/v1/cities/search/',
        expect.objectContaining({ params: expect.objectContaining({ q: 'Мичу' }) }),
      )
    })
    await waitFor(() => expect(screen.getByText('Мичуринск')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Мичуринск'))
    expect(onChange).toHaveBeenCalledWith({ id: 362, name: 'Мичуринск' })
  })

  it('shows an error state instead of dying silently', async () => {
    mockedGet.mockRejectedValueOnce(new Error('offline'))
    render(<CitySelect value={null} onChange={vi.fn()} />)
    const input = screen.getByLabelText('Город')
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'Мичу' } })
    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить города/)).toBeInTheDocument()
    })
  })
})
