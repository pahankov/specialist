import { useState } from 'react'
import { authApi } from '../api/client'
import './LoginModal.css'

interface LoginModalProps {
  isOpen: boolean
  onClose: () => void
}

function LoginModal({ isOpen, onClose }: LoginModalProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isRegister, setIsRegister] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, '').slice(0, 11)
    setPhone(value)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    // Client login by phone
    if (phone && !email) {
      setLoading(true)
      try {
        const resp = await authApi.clientLogin(phone)
        localStorage.setItem('access_token', resp.data.access_token)
        window.location.href = '/client/appointments'
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Клиент не найден')
      } finally {
        setLoading(false)
      }
      return
    }

    // Master login or register
    if (isRegister) {
      setLoading(true)
      try {
        await authApi.register({ name, email, password, phone: phone || undefined })
        // Auto-login after successful registration
        const loginResp = await authApi.login(email, password)
        localStorage.setItem('access_token', loginResp.data.access_token)
        window.location.href = '/admin/dashboard'
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Ошибка регистрации')
      } finally {
        setLoading(false)
      }
      return
    }

    // Master login
    setLoading(true)
    try {
      const resp = await authApi.login(email, password)
      localStorage.setItem('access_token', resp.data.access_token)
      window.location.href = '/admin/dashboard'
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка входа')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="login-modal-overlay" onClick={onClose}>
      <div className="login-modal" onClick={(e) => e.stopPropagation()}>
        <button className="login-modal-close" onClick={onClose}>✕</button>
        
        <h2 className="login-title">Вход в систему</h2>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          {/* Master fields */}
          <div className="login-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="master@example.com"
            />
          </div>

          <div className="login-group">
            <label>Пароль</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Введите пароль"
                required={!isRegister}
                style={{ paddingRight: 44 }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer', fontSize: 18,
                  padding: '4px 8px', color: '#666'
                }}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>

          {/* Register fields */}
          {isRegister && (
            <>
              <div className="login-group">
                <label>Имя</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ваше имя"
                  required
                />
              </div>
              <div className="login-group">
                <label>Телефон</label>
                <input
                  type="tel"
                  value={phone}
                  onChange={handlePhoneChange}
                  placeholder="+7 (999) 123-45-67"
                  required
                />
              </div>
            </>
          )}

          {/* Client phone field */}
          {!isRegister && (
            <div className="login-group">
              <label>Или телефон (для клиентов)</label>
              <input
                type="tel"
                value={phone}
                onChange={handlePhoneChange}
                placeholder="+7 (999) 123-45-67"
              />
            </div>
          )}

          {/* Register checkbox */}
          <label className="login-checkbox">
            <input
              type="checkbox"
              checked={isRegister}
              onChange={(e) => setIsRegister(e.target.checked)}
            />
            <span>Зарегистрироваться как мастер</span>
          </label>

          <button type="submit" className="login-btn" disabled={loading}>
            {loading
              ? isRegister ? 'Регистрация...' : 'Входим...'
              : isRegister ? 'Зарегистрироваться' : 'Войти'
            }
          </button>
        </form>
      </div>
    </div>
  )
}

export default LoginModal
