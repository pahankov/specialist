import axios from 'axios'
import apiClient from './client'

// Same-origin proxy path (NO direct DaData calls — the secret must never
// reach the browser bundle):
// - dev: vite proxies /api/dadata -> suggestions.dadata.ru (needs
//   VITE_DADATA_TOKEN in frontend .env for the direct dev path)
// - prod: nginx proxies /api/dadata -> backend proxy (server-side keys)
const DADATA_TOKEN = import.meta.env.VITE_DADATA_TOKEN ?? ''

const dadataClient = axios.create({
  baseURL: '/api/dadata',
  headers: {
    'Authorization': `Token ${DADATA_TOKEN}`,
    'Content-Type': 'application/json',
  },
})

interface LocalCity {
  id: number
  name_ru: string
  name_en?: string | null
}

export interface DadataSuggestionData {
  country?: string
  country_iso_code?: string
  region?: string
  city?: string
  postal_code?: string
  lat?: string
  lon?: string
  capital_marker?: number
  geo_lat?: number
  geo_lon?: number
}

export interface DadataSuggestion {
  value: string
  unrestricted_value: string
  country?: string
  city?: string
  data?: DadataSuggestionData
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
      })
      if (data.suggestions?.length) return data.suggestions
    } catch { /* fall through to local DB */ }
    return searchLocalCities(query, limit)
  },

  /** Get full city info by query */
  async getCityInfo(query: string): Promise<DadataSuggestion | undefined> {
    const suggestions = await dadataApi.searchCities(query, 1)
    return suggestions[0]
  },
}

/** Local DB fallback: same DadataSuggestion shape, enough for registration. */
async function searchLocalCities(query: string, limit: number): Promise<DadataSuggestion[]> {
  const { data } = await apiClient.get('/api/v1/cities/', {
    params: { search: query, page_size: limit },
  })
  const list: LocalCity[] = Array.isArray(data) ? data : (data.items ?? [])
  return list.map((c) => ({
    value: c.name_ru,
    unrestricted_value: c.name_ru,
    city: c.name_ru,
    data: {},
  }))
}
