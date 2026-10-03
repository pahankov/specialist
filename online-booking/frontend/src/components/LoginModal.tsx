import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { authApi } from '../api/client'
import { dadataApi, type DadataSuggestion } from '../api/dadata'
import { PASSWORD_PLACEHOLDER } from '../constants'
import { formatPhone } from '../utils/formatPhone'
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
  cityId: string | null  // DAData returns string value, not number id
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
  const [loading, setLoading] = useState(false)
  const [showLoginPassword, setShowLoginPassword] = useState(false)
  const [showRegisterPassword, setShowRegisterPassword] = useState(false)

  // DAData city autocomplete
  const [citySuggestions, setCitySuggestions] = useState<DadataSuggestion[]>([])
  const [showCityDropdown, setShowCityDropdown] = useState(false)
  const [cityInput, setCityInput] = useState('')

  const cityInputRef = useRef<HTMLInputElement>(null)
  const cityDropdownRef = useRef<HTMLDivElement>(null)

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

  const handleCitySearch = async (value: string) => {
    setCityInput(value)
    if (value.length >= 2) {
      try {
        const suggestions = await dadataApi.searchCities(value, 10)
        setCitySuggestions(suggestions)
        setShowCityDropdown(suggestions.length > 0)
      } catch { /* ignore */ }
    } else {
      setCitySuggestions([])
      setShowCityDropdown(false)
    }
  }

  const handleCitySelect = (suggestion: DadataSuggestion) => {
    setCityInput(suggestion.value)
    setShowCityDropdown(false)
    setCitySuggestions([])
    // DAData doesn't return cityId, use value as identifier
    setRegisterForm(prev => ({ ...prev, cityId: suggestion.value }))
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await authApi.loginUnified(loginForm.identifier, loginForm.password)
      toast.success('Вход выполнен!')
      setTimeout(() => {
        onClose()
        navigate('/admin/dashboard', { replace: true })
      }, 800)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка входа')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await authApi.registerUnified({
        name: registerForm.name,
        email: registerForm.email,
        phone: registerForm.phone,
        password: registerForm.password,
        city_name: registerForm.cityId,
        telegram_username: registerForm.telegramUsername || null,
        is_master: registerForm.isMaster,
      })
      toast.success('Регистрация успешна! Теперь войдите.')
      setMode('login')
      setLoginForm({
        identifier: registerForm.email,
        password: '',
        isMaster: registerForm.isMaster,
        isRegister: false,
      })
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка регистрации')
    } finally {
      setLoading(false)
    }
  }

  const switchMode = (newMode: ModalMode) => {
    setMode(newMode)
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
    setCityInput('')
    setCitySuggestions([])
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal login-modal" onClick={(e) => e.stopPropagation()}>
        <h3>
          {mode === 'login' ? 'Вход в систему' : 'Регистрация'}
        </h3>

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
            {/* City (DAData) */}
            <div className="login-group">
              <label>Город *</label>
              <div style={{ position: 'relative' }}>
                <input
                  ref={cityInputRef}
                  value={cityInput}
                  onChange={(e) => handleCitySearch(e.target.value)}
                  onFocus={() => {
                    if (citySuggestions.length > 0) setShowCityDropdown(true)
                  }}
                  placeholder="Начните вводить город..."
                  required
                />
                {showCityDropdown && citySuggestions.length > 0 && (
                  <div
                    ref={cityDropdownRef}
                    className="city-dropdown"
                  >
                    {citySuggestions.map((suggestion, index) => (
                      <div
                        key={index}
                        className="city-option"
                        onClick={() => handleCitySelect(suggestion)}
                      >
                        {suggestion.value}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Phone */}
            <div className="login-group">
              <label>Телефон *</label>
              <input
                type="tel"
                value={registerForm.phone}
                onChange={(e) => setRegisterForm(prev => ({ ...prev, phone: formatPhone(e.target.value) }))}
                placeholder="+7 (999) 123-45-67"
                required
              />
            </div>

            {/* Password */}
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

            {/* Name */}
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

            {/* Email */}
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

            {/* Telegram */}
            <div className="login-group">
              <label>Telegram (необязательно)</label>
              <input
                type="text"
                value={registerForm.telegramUsername}
                onChange={(e) => setRegisterForm(prev => ({ ...prev, telegramUsername: e.target.value }))}
                placeholder="@username"
              />
            </div>

            {/* Register as master */}
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
