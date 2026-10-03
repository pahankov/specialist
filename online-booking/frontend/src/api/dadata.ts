import axios from 'axios'

const DADATA_TOKEN = '07c167324787848e78b070373c5de217fff9fb52'
const DADATA_SECRET = '78368de41f0c54a0ab401ca0367933092cdbbb80'

const dadataClient = axios.create({
  baseURL: 'https://suggestions.dadata.ru/suggestions/api/v4/rich',
  headers: {
    'Authorization': `Api Key ${DADATA_TOKEN}`,
    'X-Secret': DADATA_SECRET,
  },
})

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
