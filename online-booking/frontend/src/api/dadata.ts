import axios from 'axios'

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
  /** Search cities by query (returns up to 10 results) */
  async searchCities(query: string, limit = 10): Promise<DadataSuggestion[]> {
    const { data } = await dadataClient.post('/suggest/address', {
      query,
      locations: [{ country: '*' }],
      from_bound: { value: 'CITY' },
      to_bound: { value: 'DISTRICT' },
      count: limit,
    })
    return data.suggestions
  },

  /** Get full city info by query */
  async getCityInfo(query: string): Promise<DadataSuggestion | undefined> {
    const suggestions = await dadataApi.searchCities(query, 1)
    return suggestions[0]
  },
}
