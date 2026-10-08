import { describe, it, expect } from 'vitest'
import { getApiErrorMessage } from '../utils/apiError'

describe('getApiErrorMessage', () => {
  it('passes strings through', () => {
    expect(getApiErrorMessage('boom')).toBe('boom')
  })

  it('formats string detail (default FastAPI shape)', () => {
    expect(getApiErrorMessage({ response: { data: { detail: 'Not found' } } })).toBe('Not found')
  })

  it('joins custom 422 string list ("loc -> msg")', () => {
    const err = { response: { data: { detail: ['body -> email: bad', 'body -> name: required'] } } }
    expect(getApiErrorMessage(err)).toBe('body -> email: bad, body -> name: required')
  })

  it('reads object detail with msg/message', () => {
    expect(getApiErrorMessage({ response: { data: { detail: { msg: 'M' } } } })).toBe('M')
    expect(getApiErrorMessage({ response: { data: { detail: { message: 'M2' } } } })).toBe('M2')
  })

  it('falls back to data.message then default', () => {
    expect(getApiErrorMessage({ response: { data: { message: 'DM' } } })).toBe('DM')
    expect(getApiErrorMessage({ response: { data: {} } })).toBe('Ошибка сервера')
    expect(getApiErrorMessage({ response: { data: {} } }, 'Custom')).toBe('Custom')
    expect(getApiErrorMessage(null)).toBe('Ошибка сервера')
    expect(getApiErrorMessage(new Error('plain'))).toBe('plain')
  })
})
