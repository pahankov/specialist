import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { createPortal } from 'react-dom';
import { toast } from 'sonner';
import { authApi } from '../api/client';
import { dadataApi, type DadataSuggestion } from '../api/dadata';
import { PASSWORD_PLACEHOLDER } from '../constants';
import type { MaxStartResponse } from '../api/auth';
import PhoneInput, { isCompletePhone } from './common/PhoneInput';
import { getCookie, decodeJwtPayload } from '../utils/cookies';
import { ADMIN_PREFIX, SUPER_PREFIX } from '../utils/section';
import Modal from './common/Modal';
import './LoginModal.css';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type ModalMode = 'login' | 'register' | 'max';

interface LoginFormState {
  identifier: string; // email or phone
  password: string;
  isMaster: boolean;
  isRegister: boolean;
}

interface RegisterFormState {
  name: string;
  email: string;
  phone: string;
  password: string;
  selectedCity: DadataSuggestion | null;
  telegramUsername: string;
  isMaster: boolean;
}

function LoginModal({ isOpen, onClose }: LoginModalProps) {
  const navigate = useNavigate();

  const [mode, setMode] = useState<ModalMode>('login');
  const [loginForm, setLoginForm] = useState<LoginFormState>({
    identifier: '',
    password: '',
    isMaster: false,
    isRegister: false,
  });
  const [registerForm, setRegisterForm] = useState<RegisterFormState>({
    name: '',
    email: '',
    phone: '',
    password: '',
    selectedCity: null,
    telegramUsername: '',
    isMaster: false,
  });
  const [loading, setLoading] = useState(false);
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);

  // MAX chat-bot auth: code arrives INTO the MAX dialog, user types it on site
  const [maxPhone, setMaxPhone] = useState('');
  const [maxOffer, setMaxOffer] = useState<MaxStartResponse | null>(null);
  const [maxCodeInput, setMaxCodeInput] = useState('');

  // DAData city autocomplete (debounced: each keystroke must not burn quota)
  const [citySuggestions, setCitySuggestions] = useState<DadataSuggestion[]>([]);
  const [showCityDropdown, setShowCityDropdown] = useState(false);
  const [cityInput, setCityInput] = useState('');
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0, width: 0 });

  const cityInputRef = useRef<HTMLInputElement>(null);
  const cityDropdownRef = useRef<HTMLDivElement>(null);
  const citySearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const citySearchSeq = useRef(0);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (cityDropdownRef.current && !cityDropdownRef.current.contains(e.target as Node)) {
        setShowCityDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      if (citySearchTimer.current) clearTimeout(citySearchTimer.current);
    };
  }, []);

  const handleCitySearch = (value: string) => {
    setCityInput(value);
    if (citySearchTimer.current) clearTimeout(citySearchTimer.current);
    if (value.length < 2) {
      setCitySuggestions([]);
      setShowCityDropdown(false);
      return;
    }
    const seq = ++citySearchSeq.current;
    citySearchTimer.current = setTimeout(async () => {
      try {
        const suggestions = await dadataApi.searchCities(value, 10);
        if (seq !== citySearchSeq.current) return; // stale response
        setCitySuggestions(suggestions);
        setShowCityDropdown(suggestions.length > 0);
      } catch {
        /* ignore: quota/network — dropdown stays empty */
      }
    }, 400);
  };

  const handleCitySelect = (suggestion: DadataSuggestion) => {
    setCityInput(suggestion.value);
    setShowCityDropdown(false);
    setCitySuggestions([]);
    setRegisterForm((prev) => ({ ...prev, selectedCity: suggestion }));
  };

  useEffect(() => {
    if (showCityDropdown && cityInputRef.current) {
      const rect = cityInputRef.current.getBoundingClientRect();
      setDropdownPosition({
        top: rect.bottom + window.scrollY,
        left: rect.left + window.scrollX,
        width: rect.width,
      });
    }
  }, [showCityDropdown, cityInput]);

  const landByRole = () => {
    setTimeout(() => {
      onClose();
      // Role-based landing: superadmins get their own section
      let home = `${ADMIN_PREFIX}/dashboard`;
      try {
        if (decodeJwtPayload(getCookie('access_token') ?? '')?.is_admin === true) {
          home = `${SUPER_PREFIX}/dashboard`;
        }
      } catch {
        /* default to master section */
      }
      navigate(home, { replace: true });
    }, 800);
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await authApi.loginUnified(loginForm.identifier, loginForm.password);
      toast.success('Вход выполнен!');
      landByRole();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка входа');
    } finally {
      setLoading(false);
    }
  };

  const handleMaxStart = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isCompletePhone(maxPhone)) {
      toast.error('Введите корректный номер телефона (11 цифр)');
      return;
    }
    setLoading(true);
    try {
      const resp = await authApi.maxStart(maxPhone);
      setMaxOffer(resp.data);
      setMaxCodeInput('');
      toast.success('Откройте бота в MAX — код придёт туда');
    } catch (err: any) {
      toast.error(err.response?.status === 503 ? 'Вход через MAX не настроен' : 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  const handleMaxVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^\d{6}$/.test(maxCodeInput.trim())) {
      toast.error('Код — 6 цифр из сообщения бота');
      return;
    }
    setLoading(true);
    try {
      const resp = await authApi.maxVerify(maxPhone, maxCodeInput.trim());
      toast.success(
        resp.data.is_new_user ? 'Добро пожаловать! Аккаунт создан.' : 'Вход через MAX выполнен!',
      );
      landByRole();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Неверный код');
    } finally {
      setLoading(false);
    }
  };

  const resetMaxState = () => {
    setMaxOffer(null);
    setMaxCodeInput('');
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      // Transform DadataSuggestion to backend DadataSuggestion format
      const cityData = registerForm.selectedCity
        ? {
            value: registerForm.selectedCity.value,
            unrestricted_value: registerForm.selectedCity.unrestricted_value,
            data: {
              country: registerForm.selectedCity.country,
              country_iso_code: registerForm.selectedCity.data?.country_iso_code,
              region: registerForm.selectedCity.data?.region,
              city: registerForm.selectedCity.city,
              postal_code: registerForm.selectedCity.data?.postal_code,
              geo_lat: registerForm.selectedCity.data?.lat
                ? parseFloat(registerForm.selectedCity.data.lat)
                : undefined,
              geo_lon: registerForm.selectedCity.data?.lon
                ? parseFloat(registerForm.selectedCity.data.lon)
                : undefined,
              capital_marker: registerForm.selectedCity.data?.capital_marker,
            },
          }
        : null;

      await authApi.registerUnified({
        name: registerForm.name,
        email: registerForm.email,
        phone: registerForm.phone,
        password: registerForm.password,
        city_data: cityData,
        telegram_username: registerForm.telegramUsername || null,
        is_master: registerForm.isMaster,
      });
      toast.success('Регистрация успешна! Теперь войдите.');
      setMode('login');
      setLoginForm({
        identifier: registerForm.email,
        password: '',
        isMaster: registerForm.isMaster,
        isRegister: false,
      });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка регистрации');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (newMode: ModalMode) => {
    resetMaxState();
    setMode(newMode);
    setLoginForm({
      identifier: '',
      password: '',
      isMaster: false,
      isRegister: false,
    });
    setRegisterForm({
      name: '',
      email: '',
      phone: '',
      password: '',
      selectedCity: null,
      telegramUsername: '',
      isMaster: false,
    });
    setShowLoginPassword(false);
    setShowRegisterPassword(false);
    setCityInput('');
    setCitySuggestions([]);
  };

  const maxForm = !maxOffer ? (
    <form onSubmit={handleMaxStart}>
      <div className="login-group">
        <label>Телефон *</label>
        <PhoneInput
          value={maxPhone}
          onChange={setMaxPhone}
          placeholder="+7 (999) 123-45-67"
          required
        />
      </div>

      <button type="submit" className="btn btn-primary btn-submit" disabled={loading}>
        {loading ? 'Отправляем...' : 'Получить код в MAX'}
      </button>

      <p className="login-footer">
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            switchMode('login');
          }}
        >
          Войти по паролю
        </a>
      </p>
    </form>
  ) : (
    <form onSubmit={handleMaxVerify}>
      <div className="max-code-box">
        <p>
          Бот пришлёт код в MAX
          {maxOffer.bot_url ? (
            <>
              {' '}
              (
              <a href={maxOffer.bot_url} target="_blank" rel="noreferrer">
                открыть {maxOffer.bot_username}
              </a>
              )
            </>
          ) : (
            <> — найдите {maxOffer.bot_username} вручную</>
          )}
          . Введите его ниже:
        </p>
        <input
          className="max-code-input"
          value={maxCodeInput}
          onChange={(e) => setMaxCodeInput(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="––––––"
          inputMode="numeric"
          autoComplete="one-time-code"
          required
        />
        <button type="submit" className="btn btn-primary btn-submit" disabled={loading}>
          {loading ? 'Проверяем...' : 'Войти'}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ marginTop: 8 }}
          onClick={resetMaxState}
        >
          Запросить новый код
        </button>
      </div>

      <p className="login-footer">
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            switchMode('login');
          }}
        >
          Войти по паролю
        </a>
      </p>
    </form>
  );

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title={
        mode === 'login' ? 'Вход в систему' : mode === 'register' ? 'Регистрация' : 'Вход через MAX'
      }
      className="login-modal"
    >
      {mode === 'login' ? (
        /* ─── LOGIN FORM ─── */
        <form onSubmit={handleLogin}>
          <div className="login-group">
            <label>Email или телефон</label>
            <input
              type="text"
              value={loginForm.identifier}
              onChange={(e) => setLoginForm((prev) => ({ ...prev, identifier: e.target.value }))}
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
                onChange={(e) => setLoginForm((prev) => ({ ...prev, password: e.target.value }))}
                placeholder="Введите пароль"
                required
                style={{ paddingRight: 44 }}
              />
              <button
                type="button"
                onClick={() => setShowLoginPassword(!showLoginPassword)}
                style={{
                  position: 'absolute',
                  right: 8,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: 18,
                  padding: '4px 8px',
                  color: '#666',
                  lineHeight: 1,
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
                onChange={(e) => setLoginForm((prev) => ({ ...prev, isMaster: e.target.checked }))}
              />
              <span>Я мастер / специалист</span>
            </label>
          </div>

          <button type="submit" className="btn btn-primary btn-submit" disabled={loading}>
            {loading ? 'Входим...' : 'Войти'}
          </button>

          <p className="login-footer">
            Нет аккаунта?{' '}
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                switchMode('register');
              }}
            >
              Зарегистрироваться
            </a>
            {' · '}
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                switchMode('max');
              }}
            >
              Войти через MAX
            </a>
          </p>
        </form>
      ) : mode === 'max' ? (
        /* MAX CHAT-BOT FORM (SMS-style: code arrives in MAX, typed here) */
        maxForm
      ) : (
        /* ─── REGISTER FORM ─── */
        <form onSubmit={handleRegister}>
          {/* City (DAData) */}
          <div className="login-group">
            <label>Город *</label>
            <div style={{ position: 'relative', overflow: 'visible' }}>
              <input
                ref={cityInputRef}
                value={cityInput}
                onChange={(e) => handleCitySearch(e.target.value)}
                onFocus={() => {
                  if (citySuggestions.length > 0) setShowCityDropdown(true);
                }}
                placeholder="Начните вводить город..."
                required
              />
              {showCityDropdown && citySuggestions.length > 0 && (
                <>
                  {createPortal(
                    <div
                      ref={cityDropdownRef}
                      className="city-dropdown"
                      style={{
                        position: 'fixed',
                        top: dropdownPosition.top,
                        left: dropdownPosition.left,
                        width: dropdownPosition.width,
                        zIndex: 99999,
                      }}
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
                    </div>,
                    document.body,
                  )}
                </>
              )}
            </div>
          </div>

          {/* Phone */}
          <div className="login-group">
            <label>Телефон *</label>
            <PhoneInput
              value={registerForm.phone}
              onChange={(phone) => setRegisterForm((prev) => ({ ...prev, phone }))}
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
                onChange={(e) => setRegisterForm((prev) => ({ ...prev, password: e.target.value }))}
                placeholder={PASSWORD_PLACEHOLDER}
                required
                style={{ paddingRight: 44 }}
              />
              <button
                type="button"
                onClick={() => setShowRegisterPassword(!showRegisterPassword)}
                style={{
                  position: 'absolute',
                  right: 8,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: 18,
                  padding: '4px 8px',
                  color: '#666',
                  lineHeight: 1,
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
              onChange={(e) => setRegisterForm((prev) => ({ ...prev, name: e.target.value }))}
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
              onChange={(e) => setRegisterForm((prev) => ({ ...prev, email: e.target.value }))}
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
              onChange={(e) =>
                setRegisterForm((prev) => ({ ...prev, telegramUsername: e.target.value }))
              }
              placeholder="@username"
            />
          </div>

          {/* Register as master */}
          <div className="checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={registerForm.isMaster}
                onChange={(e) =>
                  setRegisterForm((prev) => ({ ...prev, isMaster: e.target.checked }))
                }
              />
              <span>Зарегистрироваться как мастер</span>
            </label>
          </div>

          <button type="submit" className="btn btn-primary btn-submit" disabled={loading}>
            {loading ? 'Регистрация...' : 'Зарегистрироваться'}
          </button>

          <p className="login-footer">
            Уже есть аккаунт?{' '}
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                switchMode('login');
              }}
            >
              Войти
            </a>
          </p>
        </form>
      )}

      <button className="btn btn-ghost" onClick={onClose} style={{ marginTop: 12 }}>
        Закрыть
      </button>
    </Modal>
  );
}

export default LoginModal;
