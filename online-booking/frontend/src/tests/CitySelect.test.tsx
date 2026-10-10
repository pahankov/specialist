import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import CitySelect from '../components/common/CitySelect';
import apiClient from '../api/http';
import { dadataApi } from '../api/dadata';

vi.mock('../api/http', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

vi.mock('../api/dadata', () => ({
  dadataApi: { searchCities: vi.fn() },
}));

const mockedGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;
const mockedPost = (apiClient as unknown as { post: ReturnType<typeof vi.fn> }).post;
const mockedDadata = dadataApi.searchCities as unknown as ReturnType<typeof vi.fn>;

describe('CitySelect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGet.mockResolvedValue({ data: [{ id: 362, name_ru: 'Мичуринск' }] });
    mockedDadata.mockResolvedValue([]);
  });

  it('shows typed characters while focused (never swallows input)', () => {
    render(<CitySelect value={null} onChange={vi.fn()} />);
    const input = screen.getByLabelText('Город');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'М' } });
    expect(input).toHaveValue('М');
  });

  it('searches after 2 letters and picks a city', async () => {
    const onChange = vi.fn();
    render(<CitySelect value={null} onChange={onChange} />);
    const input = screen.getByLabelText('Город');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Мичу' } });
    await waitFor(() => {
      expect(mockedGet).toHaveBeenCalledWith(
        '/api/v1/cities/search/',
        expect.objectContaining({ params: expect.objectContaining({ q: 'Мичу' }) }),
      );
    });
    await waitFor(() => expect(screen.getByText('Мичуринск')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Мичуринск'));
    expect(onChange).toHaveBeenCalledWith({ id: 362, name: 'Мичуринск', source: 'local' });
  });

  it('resolves a DaData-only pick to a local id', async () => {
    mockedGet.mockResolvedValue({ data: [] });
    mockedDadata.mockResolvedValue([{ value: 'г Гвардейск', city: 'Гвардейск' }]);
    mockedPost.mockResolvedValue({ data: { id: 999, name_ru: 'Гвардейск' } });
    const onChange = vi.fn();
    render(<CitySelect value={null} onChange={onChange} />);
    const input = screen.getByLabelText('Город');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Гвард' } });
    await waitFor(() => expect(screen.getByText('Гвардейск')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Гвардейск'));
    await waitFor(() => {
      expect(mockedPost).toHaveBeenCalledWith('/api/v1/cities/resolve', { name: 'Гвардейск' });
      expect(onChange).toHaveBeenCalledWith({ id: 999, name: 'Гвардейск', source: 'dadata' });
    });
  });

  it('shows an error state instead of dying silently', async () => {
    mockedGet.mockRejectedValueOnce(new Error('offline'));
    mockedDadata.mockRejectedValueOnce(new Error('offline'));
    render(<CitySelect value={null} onChange={vi.fn()} />);
    const input = screen.getByLabelText('Город');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'Мичу' } });
    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить города/)).toBeInTheDocument();
    });
  });
});
