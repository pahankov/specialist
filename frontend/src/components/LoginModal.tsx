import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi, citiesApi } from '../api/client'
import { PHONE_PLACEHOLDER, PASSWORD_PLACEHOLDER } from '../constants'
import type { Country, City } from '../api/types'
import './LoginModal.css'

interface LoginModalProps {
  isOpen: boolean
  onClose: () => void
}

type ModalMode = 'login' | 'register'

interface LoginFormState {
  identifier: string  // email or phone
  password: string
  isMaster: boolean
  isRegister: boolean
}

interface RegisterFormState {
  name: string
  email: string
  phone: string
  password: string
  cityId: number | null
  telegramUsername: string
  isMaster: boolean
}

function LoginModal({ isOpen, onClose }: LoginModalProps) {
  const navigate = useNavigate()
  const [mode, setMode] = useState<ModalMode>('login')
  const [loginForm, setLoginForm] = useState<LoginFormState>({
    identifier: '',
    password: '',
    isMaster: false,
    isRegister: false,
  })
  const [registerForm, setRegisterForm] = useState<RegisterFormState>({
    name: '',
    email: '',
    phone: '',
    password: '',
    cityId: null,
    telegramUsername: '',
    isMaster: false,
  })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const [showLoginPassword, setShowLoginPassword] = useState(false)
  const [showRegisterPassword, setShowRegisterPassword] = useState(false)

  // Cities data
  const [countries, setCountries] = useState<Country[]>([])
  const [cities, setCities] = useState<City[]>([])
  const [citySearch, setCitySearch] = useState('')
  const [showCityDropdown, setShowCityDropdown] = useState(false)
  const [selectedCountry, setSelectedCountry] = useState<number | null>(null)

  const cityInputRef = useRef<HTMLInputElement>(null)
  const cityDropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isOpen) {
      loadCountries()
    }
  }, [isOpen])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (cityDropdownRef.current && !cityDropdownRef.current.contains(e.target as Node)) {
        setShowCityDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const loadCountries = async () => {
    try {
      const { data } = await citiesApi.getCountries()
      setCountries(data)
      // Default to Russia
      const russia = data.find(c => c.code === 'RU')
      if (russia) {
        setSelectedCountry(russia.id)
        loadCities(russia.id)
      }
    } catch { /* ignore */ }
  }

  const loadCities = async (countryId: number, search?: string) => {
    try {
      const params: Record<string, any> = { country_id: countryId, page_size: 500 }
      if (search) params.search = search
      const { data } = await citiesApi.getCities(params)
      setCities(data)
    } catch { /* ignore */ }
  }

  const handleCitySearch = (value: string) => {
    setCitySearch(value)
    if (value.length >= 2 && selectedCountry) {
      loadCities(selectedCountry, value)
    } else if (selectedCountry) {
      loadCities(selectedCountry)
    }
  }

  const handleCitySelect = (city: City) => {
    setRegisterForm(prev => ({ ...prev, cityId: city.id }))
    setCitySearch(city.name_ru)
    setShowCityDropdown(false)
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)
    try {
      await authApi.loginUnified(loginForm.identifier, loginForm.password)
      setSuccess('Вход выполнен!')
      setTimeout(() => {
        onClose()
        navigate('/admin/dashboard', { replace: true })
      }, 800)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка входа')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)
    try {
      await authApi.registerUnified({
        name: registerForm.name,
        email: registerForm.email,
        phone: registerForm.phone,
        password: registerForm.password,
        city_id: registerForm.cityId,
        telegram_username: registerForm.telegramUsername || null,
        is_master: registerForm.isMaster,
      })
      setSuccess('Регистрация успешна! Теперь войдите.')
      setMode('login')
      setLoginForm({
        identifier: registerForm.email,
        password: '',
        isMaster: registerForm.isMaster,
        isRegister: false,
      })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка регистрации')
    } finally {
      setLoading(false)
    }
  }

  const switchMode = (newMode: ModalMode) => {
    setMode(newMode)
    setError('')
    setSuccess('')
    setLoginForm({
      identifier: '',
      password: '',
      isMaster: false,
      isRegister: false,
    })
    setRegisterForm({
      name: '',
      email: '',
      phone: '',
      password: '',
      cityId: null,
      telegramUsername: '',
      isMaster: false,
    })
    setShowLoginPassword(false)
    setShowRegisterPassword(false)
    setCitySearch('')
    setSelectedCountry(null)
    setCities([])
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal login-modal" onClick={(e) => e.stopPropagation()}>
        <h3>
          {mode === 'login' ? 'Вход в систему' : 'Регистрация'}
        </h3>

        {success && <div className="success-message">{success}</div>}
        {error && <div className="error-message">{error}</div>}

        {mode === 'login' ? (
          /* ─── LOGIN FORM ─── */
          <form onSubmit={handleLogin}>
            <div className="login-group">
              <label>Email или телефон</label>
              <input
                type="text"
                value={loginForm.identifier}
                onChange={(e) => setLoginForm(prev => ({ ...prev, identifier: e.target.value }))}
                placeholder="email@example.com или +7 (999) 123-45-67"
                required
              />
            </div>

            <div className="login-group">
              <label>Пароль</label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showLoginPassword ? 'text' : 'password'}
                  value={loginForm.password}
                  onChange={(e) => setLoginForm(prev => ({ ...prev, password: e.target.value }))}
                  placeholder="Введите пароль"
                  required
                  style={{ paddingRight: 44 }}
                />
                <button
                  type="button"
                  onClick={() => setShowLoginPassword(!showLoginPassword)}
                  style={{
                    position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, padding: '4px 8px',
                    color: '#666', lineHeight: 1
                  }}
                  title={showLoginPassword ? 'Скрыть пароль' : 'Показать пароль'}
                >
                  {showLoginPassword ? '🙈' : '👁️'}
                </button>
              </div>
            </div>

            <div className="checkbox-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={loginForm.isMaster}
                  onChange={(e) => setLoginForm(prev => ({ ...prev, isMaster: e.target.checked }))}
                />
                <span>Я мастер / специалист</span>
              </label>
            </div>

            <button type="submit" className="btn btn-primary btn-submit" disabled={loading}>
              {loading ? 'Входим...' : 'Войти'}
            </button>

            <p className="login-footer">
              Нет аккаунта?{' '}
              <a href="#" onClick={(e) => { e.preventDefault(); switchMode('register') }}>
                Зарегистрироваться
              </a>
            </p>
          </form>
        ) : (
          /* ─── REGISTER FORM ─── */
          <form onSubmit={handleRegister}>
            <div className="login-group">
              <label>Имя *</label>
              <input
                type="text"
                value={registerForm.name}
                onChange={(e) => setRegisterForm(prev => ({ ...prev, name: e.target.value }))}
                placeholder="Иван Иванов"
                required
              />
            </div>

            <div className="login-group">
              <label>Email *</label>
              <input
                type="email"
                value={registerForm.email}
                onChange={(e) => setRegisterForm(prev => ({ ...prev, email: e.target.value }))}
                placeholder="email@example.com"
                required
              />
            </div>

            <div className="login-group">
              <label>Телефон *</label>
              <input
                type="tel"
                value={registerForm.phone}
                onChange={(e) => {
                  const raw = e.target.value.replace(/\D/g, '').slice(0, 10)
                  let formatted = raw
                  if (raw.length > 0) formatted = `+7`
                  if (raw.length > 1) formatted += ` (${raw.slice(1, 4)}`
                  if (raw.length > 4) formatted += `) ${raw.slice(4, 7)}`
                  if (raw.length > 7) formatted += `-${raw.slice(7, 9)}`
                  if (raw.length > 9) formatted += `-${raw.slice(9, 11)}`
                  setRegisterForm(prev => ({ ...prev, phone: formatted }))
                }}
                placeholder={PHONE_PLACEHOLDER}
                required
              />
            </div>

            <div className="login-group">
              <label>Пароль *</label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showRegisterPassword ? 'text' : 'password'}
                  value={registerForm.password}
                  onChange={(e) => setRegisterForm(prev => ({ ...prev, password: e.target.value }))}
                  placeholder={PASSWORD_PLACEHOLDER}
                  required
                  style={{ paddingRight: 44 }}
                />
                <button
                  type="button"
                  onClick={() => setShowRegisterPassword(!showRegisterPassword)}
                  style={{
                    position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, padding: '4px 8px',
                    color: '#666', lineHeight: 1
                  }}
                  title={showRegisterPassword ? 'Скрыть пароль' : 'Показать пароль'}
                >
                  {showRegisterPassword ? '🙈' : '👁️'}
                </button>
              </div>
            </div>

            {/* Country & City */}
            <div className="login-group">
              <label>Страна</label>
              <select
                value={selectedCountry || ''}
                onChange={(e) => {
                  const countryId = Number(e.target.value)
                  setSelectedCountry(countryId)
                  setCitySearch('')
                  loadCities(countryId)
                }}
              >
                <option value="">Выберите страну</option>
                {countries.map((c) => (
                  <option key={c.id} value={c.id}>{c.name_ru}</option>
                ))}
              </select>
            </div>

            <div className="login-group">
              <label>Город</label>
              <div style={{ position: 'relative' }}>
                <input
                  ref={cityInputRef}
                  value={citySearch}
                  onChange={(e) => {
                    handleCitySearch(e.target.value)
                    setShowCityDropdown(true)
                  }}
                  onFocus={() => {
                    if (cities.length > 0) setShowCityDropdown(true)
                  }}
                  placeholder="Начните вводить город..."
                />
                {showCityDropdown && cities.length > 0 && (
                  <div
                    ref={cityDropdownRef}
                    className="city-dropdown"
                  >
                    {cities.map((city) => (
                      <div
                        key={city.id}
                        className="city-option"
                        onClick={() => handleCitySelect(city)}
                      >
                        {city.name_ru}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="login-group">
              <label>Telegram (необязательно)</label>
              <input
                type="text"
                value={registerForm.telegramUsername}
                onChange={(e) => setRegisterForm(prev => ({ ...prev, telegramUsername: e.target.value }))}
                placeholder="@username"
              />
            </div>

            <div className="checkbox-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={registerForm.isMaster}
                  onChange={(e) => setRegisterForm(prev => ({ ...prev, isMaster: e.target.checked }))}
                />
                <span>Зарегистрироваться как мастер</span>
              </label>
            </div>

            <button type="submit" className="btn btn-primary btn-submit" disabled={loading}>
              {loading ? 'Регистрация...' : 'Зарегистрироваться'}
            </button>

            <p className="login-footer">
              Уже есть аккаунт?{' '}
              <a href="#" onClick={(e) => { e.preventDefault(); switchMode('login') }}>
                Войти
              </a>
            </p>
          </form>
        )}

        <button className="btn btn-ghost" onClick={onClose} style={{ marginTop: 12 }}>
          Закрыть
        </button>
      </div>
    </div>
  )
}

export default LoginModal
