import axios from 'axios'

const DADATA_TOKEN = 'REDACTED_DADATA_TOKEN'
const DADATA_SECRET = 'REDACTED_DADATA_SECRET'

const dadataClient = axios.create({
  baseURL: '/api/dadata',
  headers: {
    'Authorization': `Api Key ${DADATA_TOKEN}`,
    'X-Secret': DADATA_SECRET,
  },
})

// eslint-disable-next-line no-console
console.log('[DAData] Initialized')

export interface DadataSuggestion {
  value: string
  unrestricted_value: string
  country: string
  city: string
  lat?: string
  lon?: string
  postal_code?: string
}

export const dadataApi = {
  /** Search cities by query (returns up to 10 results) */
  async searchCities(query: string, limit = 10): Promise<DadataSuggestion[]> {
    const { data } = await dadataClient.post('/suggestions/address', {
      value: query,
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
