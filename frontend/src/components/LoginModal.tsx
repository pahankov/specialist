import { useState, useEffect } from 'react'
import { authApi, citiesApi } from '../api/client'
import { PHONE_PLACEHOLDER, PASSWORD_PLACEHOLDER } from '../constants'
import type { Country, City } from '../api/types'
import './LoginModal.css'

interface LoginModalProps {
  isOpen: boolean
  onClose: () => void
}

type AuthMode = 'register' | 'client-login' | 'send-otp' | 'verify-otp'

function LoginModal({ isOpen, onClose }: LoginModalProps) {
  const [mode, setMode] = useState<AuthMode>('client-login')
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [telegram, setTelegram] = useState('')
  const [cityId, setCityId] = useState<number | undefined>()
  const [otpCode, setOtpCode] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  // Cities data
  const [countries, setCountries] = useState<Country[]>([])
  const [cities, setCities] = useState<City[]>([])
  const [citySearch, setCitySearch] = useState('')
  const [showCityDropdown, setShowCityDropdown] = useState(false)
  const [selectedCountry, setSelectedCountry] = useState<number>(1) // Russia by default

  useEffect(() => {
    if (isOpen) {
      loadCountries()
    }
  }, [isOpen])

  useEffect(() => {
    if (isOpen && mode === 'register') {
      loadCities(selectedCountry)
    }
  }, [isOpen, mode, selectedCountry])

  const loadCountries = async () => {
    try {
      const { data } = await citiesApi.getCountries()
      setCountries(data)
    } catch { /* ignore */ }
  }

  const loadCities = async (countryId: number, search?: string) => {
    try {
      const params: Record<string, any> = { country_id: countryId, page_size: 200 }
      if (search) params.search = search
      const { data } = await citiesApi.getCities(params)
      setCities(data)
    } catch { /* ignore */ }
  }

  const handleCitySearch = (value: string) => {
    setCitySearch(value)
    if (value.length >= 2) {
      loadCities(selectedCountry, value)
    } else {
      loadCities(selectedCountry)
    }
  }

  const handleCitySelect = (city: City) => {
    setCityId(city.id)
    setCitySearch(city.name_ru)
    setShowCityDropdown(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)
    try {
      if (mode === 'register') {
        await authApi.register({
          name, email, password, phone,
          telegram_username: telegram || undefined,
          role: 'master',
          city_id: cityId,
        })
        setSuccess('Регистрация успешна! Теперь войдите.')
        setMode('client-login')
      } else if (mode === 'client-login') {
        await authApi.sendOtp(phone)
        setMode('verify-otp')
      } else if (mode === 'verify-otp') {
        await authApi.verifyOtp(phone, otpCode)
        setSuccess('Вход выполнен!')
        setTimeout(onClose, 1000)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка')
    } finally { setLoading(false) }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>
          {mode === 'register' && 'Регистрация мастера'}
          {mode === 'client-login' && 'Вход для клиента'}
          {mode === 'send-otp' && 'Отправка кода'}
          {mode === 'verify-otp' && 'Ввод кода'}
        </h3>
        {success && <div className="success-message">{success}</div>}
        {error && <div className="error-message">{error}</div>}
        <form onSubmit={handleSubmit}>
          {/* Registration */}
          {mode === 'register' && (
            <>
              <div className="login-group">
                <label>Имя</label>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Иван Иванов" required />
              </div>
              <div className="login-group">
                <label>Email</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" required />
              </div>
              <div className="login-group">
                <label>Пароль</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={PASSWORD_PLACEHOLDER} required />
              </div>
              <div className="login-group">
                <label>Телефон</label>
                <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={PHONE_PLACEHOLDER} maxLength={18} required />
              </div>
              <div className="login-group">
                <label>Telegram</label>
                <input type="text" value={telegram} onChange={(e) => setTelegram(e.target.value)} placeholder="@username" />
              </div>
              <div className="login-group">
                <label>Страна</label>
                <select value={selectedCountry} onChange={(e) => setSelectedCountry(Number(e.target.value))}>
                  {countries.map((c) => (
                    <option key={c.id} value={c.id}>{c.name_ru}</option>
                  ))}
                </select>
              </div>
              <div className="login-group">
                <label>Город</label>
                <div style={{ position: 'relative' }}>
                  <input
                    value={citySearch}
                    onChange={(e) => { handleCitySearch(e.target.value); setShowCityDropdown(true) }}
                    onFocus={() => setShowCityDropdown(true)}
                    placeholder="Начните вводить город..."
                    required
                  />
                  {showCityDropdown && cities.length > 0 && (
                    <div style={{
                      position: 'absolute', top: '100%', left: 0, right: 0,
                      background: 'white', border: '1px solid #ccc',
                      maxHeight: 200, overflowY: 'auto', zIndex: 1000,
                    }}>
                      {cities.map((city) => (
                        <div
                          key={city.id}
                          style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid #eee' }}
                          onMouseDown={() => handleCitySelect(city)}
                        >
                          {city.name_ru}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {/* Client login - enter phone */}
          {mode === 'client-login' && (
            <div className="login-group">
              <label>Телефон</label>
              <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={PHONE_PLACEHOLDER} maxLength={18} required />
            </div>
          )}

          {/* Verify OTP */}
          {mode === 'verify-otp' && (
            <div className="login-group">
              <label>Код из SMS</label>
              <input
                type="text"
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="Введите 6-значный код"
                maxLength={6}
                required
              />
              <small style={{ color: '#666', marginTop: 4 }}>Код отправлен на {phone}</small>
            </div>
          )}

          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Отправка...' : (
              mode === 'register' ? 'Зарегистрироваться' :
              mode === 'client-login' ? 'Отправить код' :
              mode === 'verify-otp' ? 'Подтвердить' : 'Войти'
            )}
          </button>
        </form>
        <p style={{ marginTop: 16, textAlign: 'center' }}>
          {mode === 'register' && (
            <>Уже есть аккаунт? <a href="#" onClick={(e) => { e.preventDefault(); setMode('client-login') }}>Войти</a></>
          )}
          {(mode === 'client-login' || mode === 'verify-otp') && (
            <>Нет аккаунта? <a href="#" onClick={(e) => { e.preventDefault(); setMode('register') }}>Зарегистрироваться</a></>
          )}
        </p>
        <button className="btn btn-ghost" onClick={onClose} style={{ marginTop: 8 }}>Закрыть</button>
      </div>
    </div>
  )
}

export default LoginModal
