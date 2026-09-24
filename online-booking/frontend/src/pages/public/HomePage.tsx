import { useEffect, useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Swiper, SwiperSlide } from 'swiper/react'
import { Navigation, Autoplay } from 'swiper/modules'
import { mastersApi, servicesApi } from '../../api/client'
import type { Master, Service } from '../../api/types'
import LoginModal from '../../components/LoginModal'
import { ReviewsSection } from '../../components/reviews'
import 'swiper/css'
import 'swiper/css/navigation'
import 'swiper/css/autoplay'
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
  
  // Random selection on each page load (memoized)
  const randomServices = useMemo(() => pickRandom(allServices, 6), [allServices])
  const randomMasters = useMemo(() => pickRandom(allMasters, 6), [allMasters])

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
        <Swiper
          modules={[Navigation, Autoplay]}
          spaceBetween={30}
          slidesPerView={1}
          loop={true}
          autoplay={{
            delay: 4000,
            disableOnInteraction: false,
          }}
          navigation={{
            nextEl: '.carousel-btn-next',
            prevEl: '.carousel-btn-prev',
          }}
          pagination={{
            el: '.carousel-indicators',
            clickable: true,
          }}
          onSlideChange={() => {}}
          onSwiper={() => {}}
        >
          {/* Slide 1: Services */}
          <SwiperSlide>
            {randomServices.length > 0 && (
              <section className="services-section">
                <div className="container">
                  <h2>Наши услуги</h2>
                  <div className="services-grid">
                    {randomServices.map((service) => (
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
          </SwiperSlide>

          {/* Slide 2: Masters */}
          <SwiperSlide>
            {randomMasters.length > 0 && (
              <section className="masters-section">
                <div className="container">
                  <h2>Наши мастера</h2>
                  <div className="masters-grid">
                    {randomMasters.map((master) => (
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
          </SwiperSlide>

          {/* Slide 3: Reviews */}
          <SwiperSlide>
            <div className="reviews-carousel-slide">
              <ReviewsSection />
            </div>
          </SwiperSlide>
        </Swiper>

        {/* Navigation buttons */}
        <button className="carousel-btn carousel-btn-prev" aria-label="Предыдущий слайд">‹</button>
        <button className="carousel-btn carousel-btn-next" aria-label="Следующий слайд">›</button>

        {/* Pagination dots */}
        <div className="carousel-indicators" />
      </div>

      {/* Login Modal */}
      <LoginModal isOpen={showLogin} onClose={() => setShowLogin(false)} />
    </div>
  )
}

export default HomePage
