import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { mastersApi, servicesApi } from '../../api/client'
import type { Master, Service } from '../../api/types'
import LoginModal from '../../components/LoginModal'
import { ReviewsSection } from '../../components/reviews'
import './HomePage.css'

function HomePage() {
  const [masters, setMasters] = useState<Master[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showLogin, setShowLogin] = useState(false)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const [mastersRes, servicesRes] = await Promise.all([
          mastersApi.getAll(),
          servicesApi.getAll(),
        ])
        setMasters(mastersRes.data)
        setServices(servicesRes.data)
      } catch (err) {
        setError('Не удалось загрузить данные')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  if (loading) return <div className="home-page">Загрузка...</div>
  if (error) return <div className="home-page error">{error}</div>

  return (
    <div className="home-page">
      {/* Hero Banner */}
      <header className="hero">
        <div className="hero-content">
          <h1>Электронная запись</h1>
          <p>Запишитесь к лучшему мастеру красоты</p>
          <button className="btn btn-primary btn-login" onClick={() => setShowLogin(true)}>
            Вход в систему
          </button>
        </div>
      </header>

      {/* Services Section */}
      {services.length > 0 && (
        <section className="services-section">
          <div className="container">
            <h2>Наши услуги</h2>
            <div className="services-grid">
              {services.map((service) => (
                <div key={service.id} className="service-card card">
                  <h3>{service.name}</h3>
                  {service.description && <p>{service.description}</p>}
                  <div className="service-meta">
                    <span className="duration">⏱️ {service.duration_minutes} мин</span>
                    <span className="price">₽{service.price}</span>
                  </div>
                  <Link to={`/booking?master_id=${service.master_id}`} className="btn btn-primary">
                    Записаться
                  </Link>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Masters Section */}
      {masters.length > 0 && (
        <section className="masters-section">
          <div className="container">
            <h2>Наши мастера</h2>
            <div className="masters-grid">
              {masters.map((master) => (
                <div key={master.id} className="master-card card">
                  <h3>{master.name}</h3>
                  {master.description && <p>{master.description}</p>}
                  {master.phone && <p className="phone">📱 {master.phone}</p>}
                  <Link to={`/booking?master_id=${master.id}`} className="btn btn-primary">
                    Записаться
                  </Link>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Login Modal */}
      <LoginModal isOpen={showLogin} onClose={() => setShowLogin(false)} />

      {/* Reviews Section */}
      <ReviewsSection />
    </div>
  )
}

export default HomePage
