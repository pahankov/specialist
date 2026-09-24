import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { mastersApi, servicesApi } from '../../api/client'
import type { Master, Service } from '../../api/types'
import LoginModal from '../../components/LoginModal'
import { ReviewsSection } from '../../components/reviews'
import './HomePage.css'

// Helper: shuffle array (Fisher-Yates)
function shuffleArray<T>(array: T[]): T[] {
  const shuffled = [...array]
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled
}

// Helper: pick random N items
function pickRandom<T>(array: T[], count: number): T[] {
  return shuffleArray(array).slice(0, count)
}

function HomePage() {
  const [allMasters, setAllMasters] = useState<Master[]>([])
  const [allServices, setAllServices] = useState<Service[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showLogin, setShowLogin] = useState(false)
  
  // Carousel state
  const [currentSlide, setCurrentSlide] = useState(0)
  const slideIntervalRef = useRef<number | null>(null)
  const totalSlides = 3 // services, masters, reviews

  const SLIDE_DURATION = 4000 // 4 seconds

  // Random selection on each page load (memoized)
  const randomServices = useMemo(() => pickRandom(allServices, 6), [allServices])
  const randomMasters = useMemo(() => pickRandom(allMasters, 6), [allMasters])

  // Handle infinite loop — when reaching cloned slide 3, jump to 0 instantly
  useEffect(() => {
    if (currentSlide === 3) {
      // Disable transition for instant jump
      const track = document.querySelector('.carousel-track') as HTMLElement
      if (track) {
        track.style.transition = 'none'
        track.style.transform = 'translateX(0)'
        // Force reflow
        void track.offsetHeight
        // Re-enable transition
        requestAnimationFrame(() => {
          track.style.transition = 'transform 0.6s cubic-bezier(0.4, 0, 0.2, 1)'
          setCurrentSlide(0)
        })
      }
    }
  }, [currentSlide])

  const goToSlide = useCallback((index: number) => {
    setCurrentSlide(index)
  }, [])

  const nextSlide = useCallback(() => {
    setCurrentSlide((prev) => prev + 1)
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

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const [mastersRes, servicesRes] = await Promise.all([
          mastersApi.getAll(),
          servicesApi.getAll(),
        ])
        setAllMasters(mastersRes.data)
        setAllServices(servicesRes.data)
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
      <div className="carousel-container">
        <div className="carousel-wrapper">
          <button 
            className="carousel-btn carousel-btn-prev" 
            onClick={prevSlide}
            aria-label="Предыдущий слайд"
          >
            ‹
          </button>

          <div 
            className="carousel-track"
            style={{ transform: `translateX(-${currentSlide * 100}%)` }}
          >
            {/* Slide 1: Services */}
            <div className={`carousel-slide ${currentSlide === 0 ? 'active' : ''}`}>
              {randomServices.length > 0 && (
                <section className="services-section">
                  <div className="container">
                    <h2>Наши услуги</h2>
                    <div className="services-grid">
                      {randomServices.map((service) => (
                        <div 
                          key={service.id} 
                          className="service-card card"
                          onMouseEnter={() => { if (slideIntervalRef.current) clearInterval(slideIntervalRef.current) }}
                          onMouseLeave={() => { slideIntervalRef.current = setInterval(nextSlide, SLIDE_DURATION) }}
                        >
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
              {randomMasters.length > 0 && (
                <section className="masters-section">
                  <div className="container">
                    <h2>Наши мастера</h2>
                    <div className="masters-grid">
                      {randomMasters.map((master) => (
                        <div 
                          key={master.id} 
                          className="master-card card"
                          onMouseEnter={() => { if (slideIntervalRef.current) clearInterval(slideIntervalRef.current) }}
                          onMouseLeave={() => { slideIntervalRef.current = setInterval(nextSlide, SLIDE_DURATION) }}
                        >
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

            {/* Slide 4: Cloned Services for infinite loop */}
            <div className={`carousel-slide ${currentSlide === 3 ? 'active' : ''}`}>
              {randomServices.length > 0 && (
                <section className="services-section">
                  <div className="container">
                    <h2>Наши услуги</h2>
                    <div className="services-grid">
                      {randomServices.map((service) => (
                        <div 
                          key={`clone-${service.id}`} 
                          className="service-card card"
                          onMouseEnter={() => { if (slideIntervalRef.current) clearInterval(slideIntervalRef.current) }}
                          onMouseLeave={() => { slideIntervalRef.current = setInterval(nextSlide, SLIDE_DURATION) }}
                        >
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
              className={`carousel-indicator ${currentSlide % totalSlides === index ? 'active' : ''}`}
              onClick={() => goToSlide(index)}
              aria-label={`Перейти к слайду ${index + 1}`}
            />
          ))}
        </div>

        {/* Slide labels */}
        <div className="carousel-labels">
          <span className={`carousel-label ${currentSlide % totalSlides === 0 ? 'active' : ''}`}>Услуги</span>
          <span className={`carousel-label ${currentSlide % totalSlides === 1 ? 'active' : ''}`}>Мастера</span>
          <span className={`carousel-label ${currentSlide % totalSlides === 2 ? 'active' : ''}`}>Отзывы</span>
        </div>
      </div>

      {/* Login Modal */}
      <LoginModal isOpen={showLogin} onClose={() => setShowLogin(false)} />
    </div>
  )
}

export default HomePage
