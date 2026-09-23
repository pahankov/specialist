import { useState } from 'react'
import { authApi } from '../api/client'
import { PHONE_PLACEHOLDER, PASSWORD_PLACEHOLDER } from '../constants'
import './LoginModal.css'

interface LoginModalProps {
  isOpen: boolean
  onClose: () => void
}

function LoginModal({ isOpen, onClose }: LoginModalProps) {
  const [isRegister, setIsRegister] = useState(false)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [telegram, setTelegram] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)
    try {
      if (isRegister) {
        await authApi.register({ name, email, password, phone, telegram_username: telegram || undefined })
        setSuccess('Регистрация успешна! Теперь войдите.')
        setIsRegister(false)
      } else {
        await authApi.clientLogin(phone)
        setSuccess('Код отправлен (демо: вход сразу)')
        onClose()
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка')
    } finally { setLoading(false) }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{isRegister ? 'Регистрация' : 'Вход для клиента'}</h3>
        {success && <div className="success-message">{success}</div>}
        {error && <div className="error-message">{error}</div>}
        <form onSubmit={handleSubmit}>
          {isRegister && (
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
            </>
          )}
          {!isRegister && (
            <div className="login-group">
              <label>Телефон</label>
              <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder={PHONE_PLACEHOLDER} maxLength={18} required />
            </div>
          )}
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Отправка...' : (isRegister ? 'Зарегистрироваться' : 'Войти')}
          </button>
        </form>
        <p style={{ marginTop: 16, textAlign: 'center' }}>
          {isRegister ? 'Уже есть аккаунт? ' : 'Нет аккаунта? '}
          <a href="#" onClick={(e) => { e.preventDefault(); setIsRegister(!isRegister) }}>
            {isRegister ? 'Войти' : 'Зарегистрироваться'}
          </a>
        </p>
        <button className="btn btn-ghost" onClick={onClose} style={{ marginTop: 8 }}>Закрыть</button>
      </div>
    </div>
  )
}

export default LoginModal
