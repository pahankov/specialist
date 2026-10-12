import axios from 'axios';
import apiClient from './http';

// Same-origin proxy path (NO direct DaData calls — the secret must never
// reach the browser bundle). Both dev (vite -> localhost:8000) and prod
// (nginx -> backend) terminate at the backend proxy, which authenticates
// with server-side keys from backend/.env.
const dadataClient = axios.create({
  baseURL: '/api/dadata',
  headers: {
    'Content-Type': 'application/json',
  },
});

interface LocalCity {
  id: number;
  name_ru: string;
  name_en?: string | null;
}

export interface DadataSuggestionData {
  country?: string;
  country_iso_code?: string;
  region?: string;
  city?: string;
  postal_code?: string;
  lat?: string;
  lon?: string;
  capital_marker?: number;
  geo_lat?: number;
  geo_lon?: number;
}

export interface DadataSuggestion {
  value: string;
  unrestricted_value: string;
  country?: string;
  city?: string;
  data?: DadataSuggestionData;
}

export const dadataApi = {
  /** Search cities by query (returns up to 10 results).
   *
   * Primary: DaData suggestions (worldwide). Fallback: local cities DB
   * (survives DaData quota/tariff outages — e.g. 403 feature disabled).
   */
  async searchCities(query: string, limit = 10): Promise<DadataSuggestion[]> {
    try {
      const { data } = await dadataClient.post('/suggest/address', {
        query,
        locations: [{ country: '*' }],
        from_bound: { value: 'CITY' },
        to_bound: { value: 'DISTRICT' },
        count: limit,
      });
      if (data.suggestions?.length) return data.suggestions;
    } catch {
      /* fall through to local DB */
    }
    return searchLocalCities(query, limit);
  },

  /** Get full city info by query */
  async getCityInfo(query: string): Promise<DadataSuggestion | undefined> {
    const suggestions = await dadataApi.searchCities(query, 1);
    return suggestions[0];
  },

  /** Street addresses for the cabinet field (DaData suggest/address).
   * Returns display strings; empty list when quota/network fails.
   */
  async searchAddresses(query: string, limit = 8): Promise<string[]> {
    try {
      const { data } = await dadataClient.post('/suggest/address', {
        query,
        count: limit,
      });
      const list = (data.suggestions ?? []) as { value?: string; unrestricted_value?: string }[];
      const out: string[] = [];
      for (const s of list) {
        const v = (s.unrestricted_value || s.value || '').trim();
        if (v && !out.includes(v)) out.push(v);
      }
      return out;
    } catch {
      return [];
    }
  },
};

/** Local DB fallback: same DadataSuggestion shape, enough for registration. */
async function searchLocalCities(query: string, limit: number): Promise<DadataSuggestion[]> {
  const { data } = await apiClient.get('/api/v1/cities/search/', {
    params: { q: query, limit },
  });
  const list: LocalCity[] = Array.isArray(data) ? data : (data.items ?? []);
  return list.map((c) => ({
    value: c.name_ru,
    unrestricted_value: c.name_ru,
    city: c.name_ru,
    data: {},
  }));
}
