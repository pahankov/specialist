import { useEffect, useState, useMemo, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Navigation, Autoplay } from 'swiper/modules';
import { toast } from 'sonner';
import { mastersApi, servicesApi, authApi } from '../../api/client';
import type { Master, Service } from '../../api/types';
import LoginModal from '../../components/LoginModal';
import { PublicFooter } from '../../components/common';
import { ReviewsSection } from '../../components/reviews';
import { getCookie, decodeJwtPayload, clearAuthCookies } from '../../utils/cookies';
import { ADMIN_PREFIX, SUPER_PREFIX } from '../../utils/section';
import 'swiper/css';
import 'swiper/css/navigation';
import 'swiper/css/autoplay';
import './HomePage.css';

// Helper: shuffle array (Fisher-Yates)
function shuffleArray<T>(array: T[]): T[] {
  const shuffled = [...array];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

// Helper: pick random N items
function pickRandom<T>(array: T[], count: number): T[] {
  return shuffleArray(array).slice(0, count);
}

function HomePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [allMasters, setAllMasters] = useState<Master[]>([]);
  const [allServices, setAllServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showLogin, setShowLogin] = useState(false);
  // Carousel "Записаться": guests authorize first, then continue booking.
  const [postLoginTo, setPostLoginTo] = useState<string | null>(null);
  const [authName, setAuthName] = useState<string | null>(null);
  const [authRole, setAuthRole] = useState<string | null>(null);
  const swiperInstance = useRef<any>(null);

  const bookMaster = (masterId: number) => {
    const to = `/cabinet/book?master_id=${masterId}`;
    if (getCookie('access_token')) {
      navigate(to);
    } else {
      setPostLoginTo(to);
      setShowLogin(true);
    }
  };

  // Guard redirect (RequireClient drops guests here with state.from).
  useEffect(() => {
    const from = (location.state as { from?: string } | null)?.from;
    if (from && !getCookie('access_token')) {
      setPostLoginTo(from);
      setShowLogin(true);
    }
  }, []);

  const refreshAuth = () => {
    try {
      const payload = decodeJwtPayload(getCookie('access_token') ?? '');
      if (payload?.sub) {
        setAuthName(payload.name || 'Гость');
        setAuthRole(payload.role || null);
        return;
      }
    } catch {
      /* not authenticated */
    }
    setAuthName(null);
    setAuthRole(null);
  };

  useEffect(() => {
    refreshAuth();
  }, [showLogin]);

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      /* proceed with local cleanup anyway */
    }
    clearAuthCookies();
    refreshAuth();
    toast.success('Вы вышли из аккаунта');
  };

  const homeForRole = () => {
    if (authRole === 'ADMIN') return `${SUPER_PREFIX}/dashboard`;
    if (authRole === 'MASTER') return `${ADMIN_PREFIX}/dashboard`;
    return '/cabinet';
  };

  // Random selection on each page load (memoized)
  const randomServices = useMemo(() => pickRandom(allServices, 6), [allServices]);
  const randomMasters = useMemo(() => pickRandom(allMasters, 6), [allMasters]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [mastersRes, servicesRes] = await Promise.all([
          mastersApi.getAll(),
          servicesApi.getAll(),
        ]);
        setAllMasters(mastersRes.data);
        setAllServices(servicesRes.data);
      } catch (err) {
        setError('Не удалось загрузить данные');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) return <div className="home-page">Загрузка...</div>;
  if (error) return <div className="home-page error">{error}</div>;

  return (
    <div className="home-page">
      {/* Hero Banner */}
      <header className="hero">
        <div className="hero-content">
          <h1>Электронная запись</h1>
          <p>Запишитесь к лучшему мастеру красоты</p>
          {authName ? (
            <div className="hero-auth">
              <span className="hero-user">👤 {authName}</span>
              <button className="btn btn-primary" onClick={() => navigate(homeForRole())}>
                {authRole === 'CLIENT' ? 'Мои записи' : 'Панель'}
              </button>
              <button className="btn btn-ghost" onClick={handleLogout}>
                Выйти
              </button>
            </div>
          ) : (
            <button className="btn btn-primary btn-login" onClick={() => setShowLogin(true)}>
              Вход в систему
            </button>
          )}
        </div>
      </header>

      {/* Carousel Section */}
      <div
        className="carousel-container"
        onMouseEnter={() => swiperInstance.current?.autoplay?.stop()}
        onMouseLeave={() => swiperInstance.current?.autoplay?.start()}
      >
        <Swiper
          modules={[Navigation, Autoplay]}
          spaceBetween={30}
          slidesPerView={1}
          loop={true}
          autoplay={{
            delay: 4000,
          }}
          navigation={{
            nextEl: '.carousel-btn-next',
            prevEl: '.carousel-btn-prev',
          }}
          pagination={{
            el: '.carousel-indicators',
            clickable: true,
          }}
          onSlideChange={() => {
            /* ignore */
          }}
          onSwiper={(swiper) => {
            swiperInstance.current = swiper;
          }}
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
                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={() => bookMaster(service.master_id)}
                        >
                          Записаться
                        </button>
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
                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={() => bookMaster(master.id)}
                        >
                          Записаться
                        </button>
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
        <button className="carousel-btn carousel-btn-prev" aria-label="Предыдущий слайд">
          ‹
        </button>
        <button className="carousel-btn carousel-btn-next" aria-label="Следующий слайд">
          ›
        </button>

        {/* Pagination dots */}
        <div className="carousel-indicators" />
      </div>

      {/* Login Modal */}
      <LoginModal
        isOpen={showLogin}
        onClose={() => {
          setShowLogin(false);
          setPostLoginTo(null);
        }}
        redirectTo={postLoginTo}
      />

      <PublicFooter />
    </div>
  );
}

export default HomePage;
