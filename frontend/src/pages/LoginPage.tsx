import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminApi } from '../../api/adminClient'
import './LoginPage.css'

function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const resp = await adminApi.login(email, password)
      localStorage.setItem('access_token', resp.data.access_token)
      navigate('/admin/dashboard')
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Ошибка входа'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card card">
        <h1>🔐 Вход для мастера</h1>
        <p className="login-subtitle">Админ-панель Sugar Booking</p>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="master@example.com"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Пароль</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Введите пароль"
              required
            />
          </div>

          <button type="submit" className="btn btn-primary btn-submit" disabled={loading}>
            {loading ? 'Входим...' : 'Войти'}
          </button>
        </form>

        <div className="login-footer">
          <a href="/">← Вернуться на главную</a>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
