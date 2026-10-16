import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi } from '../api/client';
import { PASSWORD_PLACEHOLDER } from '../constants';
import { capitalizeWords } from '../utils/names';
import AddressSelect from './common/AddressSelect';
import type { MaxStartResponse } from '../api/auth';
import PhoneInput, { maskPhone, isCompletePhone, PHONE_MAX_DIGITS } from './common/PhoneInput';
import { getCookie, decodeJwtPayload, getUserRole } from '../utils/cookies';
import { ADMIN_PREFIX, SUPER_PREFIX } from '../utils/section';
import RoleSwitch, { type RoleChoice } from './common/RoleSwitch';
import Modal from './common/Modal';
import './LoginModal.css';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** After any successful auth, land here instead of the role default. */
  redirectTo?: string | null;
}

type ModalMode = 'login' | 'register' | 'max';

interface LoginFormState {
  identifier: string; // email or phone
  password: string;
  /** Segmented switch: which cabinet to enter (replaces the dead checkbox). */
  loginAs: RoleChoice;
  isRegister: boolean;
}

interface RegisterFormState {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  password: string;
  address: string;
  addressCity: string;
  telegramUsername: string;
  isMaster: boolean;
  consent: boolean;
}

function LoginModal({ isOpen, onClose, redirectTo }: LoginModalProps) {
  const navigate = useNavigate();

  const [mode, setMode] = useState<ModalMode>('login');
  const [loginForm, setLoginForm] = useState<LoginFormState>({
    identifier: '',
    password: '',
    loginAs: 'client',
    isRegister: false,
  });
  const [registerForm, setRegisterForm] = useState<RegisterFormState>({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    password: '',
    address: '',
    addressCity: '',
    telegramUsername: '',
    isMaster: false,
    consent: false,
  });
  const [loading, setLoading] = useState(false);
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);

  // MAX chat-bot auth: code arrives INTO the MAX dialog, user types it on site
  const [maxPhone, setMaxPhone] = useState('');
  const [maxOffer, setMaxOffer] = useState<MaxStartResponse | null>(null);
  const [maxCodeInput, setMaxCodeInput] = useState('');

  const landByRole = (loginAs: RoleChoice = 'client') => {
    setTimeout(() => {
      onClose();
      const role = getUserRole();
      // Admins always land in their section; everyone else follows
      // the segmented switch (dual-role: masters open the client cabinet).
      try {
        if (decodeJwtPayload(getCookie('access_token') ?? '')?.is_admin === true) {
          navigate(`${SUPER_PREFIX}/dashboard`, { replace: true });
          return;
        }
      } catch {
        /* fall through to role landing */
      }
      // Deep-link continue (e.g. carousel "Записаться" → cabinet booking).
      if (redirectTo) {
        try {
          sessionStorage.removeItem('postLoginTo');
        } catch {
          /* ignore */
        }
        navigate(redirectTo, { replace: true });
        return;
      }
      if (loginAs === 'client') {
        navigate('/cabinet', { replace: true });
        return;
      }
      if (role === 'MASTER') {
        navigate(`${ADMIN_PREFIX}/dashboard`, { replace: true });
        return;
      }
      // A client entering "as master" goes to the application form —
      // no instant access, the profile opens after admin approval.
      navigate('/cabinet/become-master', { replace: true });
    }, 800);
  };

  // Live identifier mode: mask while the input is unambiguously a phone
  // (starts with +/7/8, digits only); free text otherwise. Emails may start
  // with digits too ("123user@mail.ru"), so digit-led input stays unmasked
  // until '@'/letters prove it an email — and is normalized on submit.
  const handleIdentifierChange = (value: string) => {
    if (value === '') {
      setLoginForm((prev) => ({ ...prev, identifier: '' }));
      return;
    }
    if (value.includes('@') || /[a-zа-яё]/i.test(value)) {
      // Email mode: drop mask artifacts (spaces/parens, leading +) so a
      // digit-led email survives the switch ("+7 (123u" -> "7123u" worst
      // case stays visible and editable — never a dead end).
      const cleaned = value.replace(/[\s()]/g, '').replace(/^\+/, '');
      setLoginForm((prev) => ({ ...prev, identifier: cleaned }));
      return;
    }
    if (/^[+78]/.test(value)) {
      setLoginForm((prev) => ({ ...prev, identifier: maskPhone(value) }));
      return;
    }
    setLoginForm((prev) => ({ ...prev, identifier: value }));
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    // The field accepts email OR phone (so no fixed mask): validate locally so
    // garbage like "+7 (923) 521-12-321ghgh" never reaches the server.
    const raw = loginForm.identifier.trim();
    if (!raw) {
      toast.error('Введите email или телефон');
      return;
    }
    let identifier = raw;
    if (raw.includes('@')) {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(raw)) {
        toast.error('Введите корректный email или телефон');
        return;
      }
    } else if (/[a-zа-яё]/i.test(raw)) {
      // Letters but no @ — neither a phone nor an email.
      toast.error('Введите корректный телефон (11 цифр) или email');
      return;
    } else {
      // Pure digits: 11 total, or 10 with no country code (mask adds +7).
      // 10 digits starting with 7/8 are a truncated number, not a full one.
      const digits = raw.replace(/\D/g, '');
      const complete =
        digits.length === PHONE_MAX_DIGITS ||
        (digits.length === PHONE_MAX_DIGITS - 1 && !/^[78]/.test(digits));
      if (!complete) {
        toast.error('Введите корректный телефон (11 цифр) или email');
        return;
      }
      identifier = maskPhone(raw);
    }
    setLoading(true);
    try {
      await authApi.loginUnified(identifier, loginForm.password);
      toast.success('Вход выполнен!');
      landByRole(loginForm.loginAs);
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
    if (!registerForm.consent) {
      toast.error('Подтвердите согласие на обработку персональных данных');
      return;
    }
    setLoading(true);
    try {
      await authApi.registerUnified({
        name: registerForm.firstName.trim(),
        last_name: registerForm.lastName.trim() || null,
        email: registerForm.email,
        phone: registerForm.phone,
        password: registerForm.password,
        // Location string (cabinet for masters, home for clients) + the
        // city parsed from the DaData suggestion (primary matching key).
        address: registerForm.address.trim() || null,
        city_name: registerForm.addressCity.trim() || null,
        telegram_username: registerForm.telegramUsername || null,
        is_master: registerForm.isMaster,
      });
      // register-unified logs in immediately: land straight in the section.
      toast.success('Добро пожаловать! Вы вошли в аккаунт.');
      landByRole(registerForm.isMaster ? 'master' : 'client');
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
      loginAs: 'client',
      isRegister: false,
    });
    setRegisterForm({
      firstName: '',
      lastName: '',
      email: '',
      phone: '',
      password: '',
      address: '',
      addressCity: '',
      telegramUsername: '',
      isMaster: false,
      consent: false,
    });
    setShowLoginPassword(false);
    setShowRegisterPassword(false);
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

      <button
        type="button"
        className="btn btn-ghost btn-submit"
        style={{ marginTop: 8 }}
        onClick={() => switchMode('login')}
      >
        ← Назад ко входу
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
          {maxOffer.delivered ? (
            <>Код уже отправлен в MAX — откройте бота</>
          ) : (
            <>Нажмите кнопку — бот сам встретит вас и пришлёт код</>
          )}
        </p>
        {(maxOffer.deeplink || maxOffer.bot_url) && (
          <a
            className="btn btn-primary btn-submit max-bot-btn"
            href={maxOffer.deeplink || maxOffer.bot_url}
            target="_blank"
            rel="noreferrer"
          >
            Открыть бота {maxOffer.bot_username}
          </a>
        )}
        <p className="max-hint">
          На телефоне кнопка сразу откроет диалог. На компьютере без приложения MAX на странице бота
          нажмите «Открыть в браузере».
        </p>
        <p className="max-hint">
          Не нашли бота? Поделитесь номером внутри диалога — код придёт туда. Введите код ниже:
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

      <button
        type="button"
        className="btn btn-ghost btn-submit"
        style={{ marginTop: 8 }}
        onClick={() => switchMode('login')}
      >
        ← Назад ко входу
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
              onChange={(e) => handleIdentifierChange(e.target.value)}
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

          <div className="login-group">
            <label>Войти как</label>
            <RoleSwitch
              value={loginForm.loginAs}
              onChange={(v) => setLoginForm((prev) => ({ ...prev, loginAs: v }))}
              labels={{ client: '👤 Клиент', master: '💼 Мастер' }}
            />
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
          {/* Location: cabinet address (master) or home location (client).
              City for matching is parsed from the DaData pick. */}
          <div className="login-group">
            <AddressSelect
              value={registerForm.address}
              onChange={(address, city) =>
                setRegisterForm((prev) => ({
                  ...prev,
                  address,
                  addressCity: city || prev.addressCity,
                }))
              }
              label={registerForm.isMaster ? 'Адрес кабинета *' : 'Ваш адрес *'}
              placeholder="Город, улица, дом..."
              required
            />
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

          {/* Name + surname (auto-capitalized, editable later in profile) */}
          <div className="login-row">
            <div className="login-group">
              <label>Имя *</label>
              <input
                type="text"
                value={registerForm.firstName}
                onChange={(e) =>
                  setRegisterForm((prev) => ({
                    ...prev,
                    firstName: capitalizeWords(e.target.value),
                  }))
                }
                placeholder="Иван"
                required
              />
            </div>
            <div className="login-group">
              <label>Фамилия *</label>
              <input
                type="text"
                value={registerForm.lastName}
                onChange={(e) =>
                  setRegisterForm((prev) => ({
                    ...prev,
                    lastName: capitalizeWords(e.target.value),
                  }))
                }
                placeholder="Петров"
                required
              />
            </div>
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

          {/* Register as client or master */}
          <div className="login-group">
            <label>Регистрируюсь как</label>
            <RoleSwitch
              value={registerForm.isMaster ? 'master' : 'client'}
              onChange={(v) => setRegisterForm((prev) => ({ ...prev, isMaster: v === 'master' }))}
              labels={{ client: '👤 Клиент', master: '💼 Мастер' }}
            />
          </div>

          {/* 152-ФЗ + оферта: explicit consent, blocks submit */}
          <div className="checkbox-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={registerForm.consent}
                onChange={(e) =>
                  setRegisterForm((prev) => ({ ...prev, consent: e.target.checked }))
                }
              />
              <span>
                Соглашаюсь с{' '}
                <Link to="/offer" target="_blank" rel="noreferrer">
                  Офертой
                </Link>{' '}
                и{' '}
                <Link to="/privacy" target="_blank" rel="noreferrer">
                  Политикой обработки ПДн
                </Link>
              </span>
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
