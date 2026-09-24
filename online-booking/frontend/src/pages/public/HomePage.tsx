import { useEffect, useState, useRef, useCallback } from 'react'
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
  
  // Carousel state
  const [currentSlide, setCurrentSlide] = useState(0)
  const [isTransitioning, setIsTransitioning] = useState(false)
  const slideIntervalRef = useRef<number | null>(null)
  const totalSlides = 3 // services, masters, reviews

  const SLIDE_DURATION = 4000 // 4 seconds

  const goToSlide = useCallback((index: number) => {
    if (isTransitioning) return
    setIsTransitioning(true)
    setCurrentSlide(index)
    setTimeout(() => setIsTransitioning(false), 600)
  }, [isTransitioning])

  const nextSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev + 1) % totalSlides)
  }, [])

  const prevSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev - 1 + totalSlides) % totalSlides)
  }, [])

  // Auto-play
  useEffect(() => {
    slideIntervalRef.current = setInterval(nextSlide, SLIDE_DURATION)
    
    return () => {
      if (slideIntervalRef.current) {
        clearInterval(slideIntervalRef.current)
      }
    }
  }, [nextSlide])

  // Pause on hover
  const handleMouseEnter = () => {
    if (slideIntervalRef.current) {
      clearInterval(slideIntervalRef.current)
    }
  }

  const handleMouseLeave = () => {
    slideIntervalRef.current = setInterval(nextSlide, SLIDE_DURATION)
  }

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

      {/* Carousel Section */}
      <div 
        className="carousel-container"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        <div className="carousel-wrapper">
          <button 
            className="carousel-btn carousel-btn-prev" 
            onClick={prevSlide}
            aria-label="Предыдущий слайд"
          >
            ‹
          </button>

          <div className="carousel-track">
            {/* Slide 1: Services */}
            <div className={`carousel-slide ${currentSlide === 0 ? 'active' : ''}`}>
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
            </div>

            {/* Slide 2: Masters */}
            <div className={`carousel-slide ${currentSlide === 1 ? 'active' : ''}`}>
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
            </div>

            {/* Slide 3: Reviews */}
            <div className={`carousel-slide ${currentSlide === 2 ? 'active' : ''}`}>
              <div className="reviews-carousel-slide">
                <ReviewsSection />
              </div>
            </div>
          </div>

          <button 
            className="carousel-btn carousel-btn-next" 
            onClick={nextSlide}
            aria-label="Следующий слайд"
          >
            ›
          </button>
        </div>

        {/* Carousel indicators */}
        <div className="carousel-indicators">
          {[0, 1, 2].map((index) => (
            <button
              key={index}
              className={`carousel-indicator ${currentSlide === index ? 'active' : ''}`}
              onClick={() => goToSlide(index)}
              aria-label={`Перейти к слайду ${index + 1}`}
            />
          ))}
        </div>

        {/* Slide labels */}
        <div className="carousel-labels">
          <span className={`carousel-label ${currentSlide === 0 ? 'active' : ''}`}>Услуги</span>
          <span className={`carousel-label ${currentSlide === 1 ? 'active' : ''}`}>Мастера</span>
          <span className={`carousel-label ${currentSlide === 2 ? 'active' : ''}`}>Отзывы</span>
        </div>
      </div>

      {/* Login Modal */}
      <LoginModal isOpen={showLogin} onClose={() => setShowLogin(false)} />
    </div>
  )
}

export default HomePage
