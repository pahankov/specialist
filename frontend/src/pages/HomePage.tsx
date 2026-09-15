import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { mastersApi, servicesApi } from '../api/client'
import type { Master, Service } from '../api/types'
import './HomePage.css'

function HomePage() {
  const [masters, setMasters] = useState<Master[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
        setError('Failed to load data')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  if (loading) return <div className="home-page">Loading...</div>
  if (error) return <div className="home-page error">{error}</div>

  return (
    <div className="home-page">
      <header className="hero">
        <div className="hero-content">
          <h1>Sugar Booking</h1>
          <p>Запишитесь к лучшему мастеру шугаринга</p>
        </div>
      </header>

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
                <Link to="/booking" className="btn btn-primary">
                  Записаться
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="masters-section">
        <div className="container">
          <h2>Наши мастера</h2>
          <div className="masters-grid">
            {masters.map((master) => (
              <div key={master.id} className="master-card card">
                {master.avatar_url && (
                  <img src={master.avatar_url} alt={master.name} className="avatar" />
                )}
                <h3>{master.name}</h3>
                {master.description && <p>{master.description}</p>}
                {master.phone && <p className="phone">📱 {master.phone}</p>}
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}

export default HomePage