/** Tests for DaData -> local DB fallback (city autocomplete resilience). */
import { describe, it, expect, vi, beforeEach } from 'vitest';

const { dadataPost, apiGet } = vi.hoisted(() => ({
  dadataPost: vi.fn(),
  apiGet: vi.fn(),
}));

vi.mock('axios', () => ({
  default: {
    create: (config?: { baseURL?: string }) => {
      if (config?.baseURL === '/api/dadata') return { post: dadataPost };
      return {
        defaults: { headers: { common: {} } },
        interceptors: { request: { use: () => undefined }, response: { use: () => undefined } },
        post: vi.fn(),
        get: apiGet,
      };
    },
  },
}));

import { dadataApi } from '../api/dadata';

beforeEach(() => {
  dadataPost.mockReset();
  apiGet.mockReset();
});

describe('dadataApi.searchCities', () => {
  it('returns DaData suggestions without touching local DB', async () => {
    const suggestions = [{ value: 'Москва', unrestricted_value: 'Москва' }];
    dadataPost.mockResolvedValue({ data: { suggestions } });

    const result = await dadataApi.searchCities('Моск', 10);

    expect(result).toEqual(suggestions);
    expect(apiGet).not.toHaveBeenCalled();
  });

  it('falls back to local cities when DaData fails (e.g. 403)', async () => {
    dadataPost.mockRejectedValue({ response: { status: 403 } });
    apiGet.mockResolvedValue({
      data: [{ id: 1, name_ru: 'Москва', name_en: 'Moscow' }],
    });

    const result = await dadataApi.searchCities('Моск', 10);

    expect(apiGet).toHaveBeenCalledWith(
      '/api/v1/cities/search/',
      expect.objectContaining({ params: expect.objectContaining({ q: 'Моск' }) }),
    );
    expect(result).toEqual([
      { value: 'Москва', unrestricted_value: 'Москва', city: 'Москва', data: {} },
    ]);
  });

  it('falls back when DaData returns empty suggestions', async () => {
    dadataPost.mockResolvedValue({ data: { suggestions: [] } });
    apiGet.mockResolvedValue({ data: [] });

    const result = await dadataApi.searchCities('Сызрань', 10);

    expect(apiGet).toHaveBeenCalled();
    expect(result).toEqual([]);
  });
});
