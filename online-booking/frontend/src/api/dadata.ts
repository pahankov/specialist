import axios from 'axios'

// Публичный токен — из env (VITE_DADATA_TOKEN), значение — в LOCAL.md / backend/.env (never commit).
// Секрет DADATA_SECRET во фронте НЕ хранится — только через backend-прокси app/modules/dadata/router.py.
const DADATA_TOKEN = import.meta.env.VITE_DADATA_TOKEN ?? ''

// Прямой запрос к DAData API (обход Vite proxy)
const dadataClient = axios.create({
  baseURL: 'https://suggestions.dadata.ru/suggestions/api/4_1/rs',
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
