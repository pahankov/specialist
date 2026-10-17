import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi } from '../api/client';
import { PASSWORD_PLACEHOLDER } from '../constants';
import { passwordError } from '../utils/password';
import SocialAuthButton from './common/SocialAuthButton';
import VkIdWidget from './common/VkIdWidget';
import MaxIcon from './common/icons/MaxIcon';
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

type ModalMode = 'login' | 'register' | 'max' | 'vk' | 'yandex';

interface LoginFormState {
  identifier: string; // email or phone
  password: string;
  /** Segmented switch: which cabinet to enter (replaces the dead checkbox). */
  loginAs: RoleChoice;
  isRegister: boolean;
}

interface RegisterFormState {
  phone: string;
  password: string;
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
    phone: '',
    password: '',
    consent: false,
  });
  const [loading, setLoading] = useState(false);
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);

  // MAX chat-bot auth: code arrives INTO the MAX dialog, user types it on site
  const [maxPhone, setMaxPhone] = useState('');
  const [maxOffer, setMaxOffer] = useState<MaxStartResponse | null>(null);
  const [maxCodeInput, setMaxCodeInput] = useState('');
  // 152-FZ consent checkbox (same offer + privacy policy as registration);
  // stamped server-side when the MAX code creates/backfills the account.
  const [maxConsent, setMaxConsent] = useState(false);

  // VK ID widget: 152-FZ consent gates the OAuthList (VK/OK/Mail) widget;
  // PKCE + the signed state are handled inside VkIdWidget.
  const [vkConsent, setVkConsent] = useState(false);

  // Yandex OAuth (plain redirect, no PKCE): consent gates the redirect; the
  // signed state + consent flag are stashed for the /auth/yandex/callback.
  const [yandexConsent, setYandexConsent] = useState(false);

  /* After the VK widget establishes the backend session (cookies set), land
     by role — admins to their section, masters to the panel, else the client
     cabinet. Mirrors the old /auth/vk/callback landing logic. */
  const handleVkSuccess = () => {
    toast.success('Вход через VK выполнен!');
    setTimeout(() => {
      onClose();
      try {
        const payload = decodeJwtPayload(getCookie('access_token') ?? '');
        if (payload?.is_admin === true) {
          navigate(`${SUPER_PREFIX}/dashboard`, { replace: true });
          return;
        }
        if (redirectTo) {
          try {
            sessionStorage.removeItem('postLoginTo');
          } catch {
            /* ignore */
          }
          navigate(redirectTo, { replace: true });
          return;
        }
        if (payload?.role === 'MASTER') {
          navigate(`${ADMIN_PREFIX}/dashboard`, { replace: true });
          return;
        }
        navigate('/cabinet', { replace: true });
      } catch {
        navigate('/cabinet', { replace: true });
      }
    }, 400);
  };

  /* Yandex OAuth start: consent must be given first (152-FZ), then we fetch
     a signed state + authorize URL from the backend and hand the browser
     over to Yandex. The callback page posts the code back for a server-side
     exchange — the app secret never reaches the client. */
  const handleYandexStart = async () => {
    if (!yandexConsent) {
      toast.error('Подтвердите согласие на обработку персональных данных');
      return;
    }
    setLoading(true);
    try {
      const resp = await authApi.yandexStart();
      try {
        sessionStorage.setItem('yandex_state', resp.data.state);
        sessionStorage.setItem('yandex_consent', yandexConsent ? '1' : '0');
      } catch {
        /* storage unavailable — the callback will rely on the echoed state */
      }
      window.location.href = resp.data.authorize_url;
    } catch (err: any) {
      setLoading(false);
      toast.error(
        err.response?.status === 503
          ? 'Вход через Яндекс не настроен'
          : 'Ошибка входа через Яндекс',
      );
    }
  };

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
    if (!maxConsent) {
      toast.error('Подтвердите согласие на обработку персональных данных');
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
      const resp = await authApi.maxVerify(maxPhone, maxCodeInput.trim(), maxConsent);
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
    if (!registerValid) {
      toast.error('Заполните все обязательные поля корректно');
      return;
    }
    setLoading(true);
    try {
      await authApi.registerUnified({
        phone: registerForm.phone,
        password: registerForm.password,
        consent: registerForm.consent,
      });
      // register-unified logs in immediately: everyone lands in the client
      // cabinet — profile is filled in later, becoming a master is separate.
      toast.success('Добро пожаловать! Вы вошли в аккаунт.');
      landByRole('client');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка регистрации');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (newMode: ModalMode) => {
    resetMaxState();
    setMaxConsent(false);
    setMode(newMode);
    setLoginForm({
      identifier: '',
      password: '',
      loginAs: 'client',
      isRegister: false,
    });
    setRegisterForm({
      phone: '',
      password: '',
      consent: false,
    });
    setShowLoginPassword(false);
    setShowRegisterPassword(false);
  };

  /* ── Register validation: mirrors backend rules, submit stays disabled
      until every required field is valid (item: disabled until valid). */
  const registerPwdError = passwordError(registerForm.password);
  const registerPhoneOk = isCompletePhone(registerForm.phone);
  const registerValid =
    registerPhoneOk &&
    registerPwdError === null &&
    registerForm.consent;

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

      {/* 152-ФЗ + оферта: same consent as registration, stamped on the
          account created (or backfilled) by the MAX code. */}
      <div className="checkbox-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={maxConsent}
            onChange={(e) => setMaxConsent(e.target.checked)}
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

      <button
        type="submit"
        className="btn btn-primary btn-submit"
        disabled={loading || !maxConsent}
      >
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
            <span className="social-auth-icon">
              <MaxIcon size={18} />
            </span>
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

  /* VK ID widget: consent is captured here BEFORE the widget renders, then
     the VK/OK/Mail OAuthList block is shown. The account is created on the
     first successful exchange — registration and login are one flow. */
  const vkForm = (
    <form
      onSubmit={(e) => {
        e.preventDefault();
      }}
    >
      <p style={{ fontSize: 14, color: '#555', marginBottom: 16 }}>
        Войдите через ВКонтакте, Одноклассники или Mail — аккаунт создастся
        автоматически при первом входе, email и пароль не нужны.
      </p>

      {/* 152-ФЗ + оферта: same consent as registration, required before the
          widget renders (VK returns the profile data we then process). */}
      <div className="checkbox-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={vkConsent}
            onChange={(e) => setVkConsent(e.target.checked)}
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

      {/* VK + OK + Mail OAuthList widget (renders only once consent is given).
          The backend exchange stays server-side — tokens never touch the browser. */}
      <VkIdWidget consent={vkConsent} onSuccess={handleVkSuccess} />

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

  /* Yandex OAuth: consent is captured here, then the browser is handed to
     Yandex and returns at /auth/yandex/callback (the registered redirect). */
  const yandexForm = (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        handleYandexStart();
      }}
    >
      <p style={{ fontSize: 14, color: '#555', marginBottom: 16 }}>
        Войдите через Яндекс — аккаунт создастся автоматически при первом
        входе, email и пароль не нужны.
      </p>

      {/* 152-ФЗ + оферта: same consent as registration, required before the
          redirect (Yandex then returns the profile data we process). */}
      <div className="checkbox-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={yandexConsent}
            onChange={(e) => setYandexConsent(e.target.checked)}
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

      <button
        type="submit"
        className="btn btn-primary btn-submit"
        disabled={loading || !yandexConsent}
      >
        {loading ? 'Перенаправляем...' : 'Продолжить через Яндекс'}
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
  );

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title={
        mode === 'login'
          ? 'Вход в систему'
          : mode === 'register'
            ? 'Регистрация'
            : mode === 'vk'
              ? 'Вход через VK, OK или Mail'
              : mode === 'yandex'
                ? 'Вход через Яндекс'
                : 'Вход и регистрация через MAX'
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

          <div className="social-auth-divider">или</div>
          {/* One-click MAX auth: logs in AND registers on first use. */}
          <SocialAuthButton
            provider="max"
            action="login"
            onClick={() => switchMode('max')}
          />
          <div style={{ marginTop: 8 }}>
            <SocialAuthButton provider="vk" action="login" onClick={() => switchMode('vk')} />
          </div>
          <div style={{ marginTop: 8 }}>
            <SocialAuthButton
              provider="yandex"
              action="login"
              onClick={() => switchMode('yandex')}
            />
          </div>

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
          </p>
        </form>
      ) : mode === 'max' ? (
        /* MAX CHAT-BOT FORM (SMS-style: code arrives in MAX, typed here) */
        maxForm
      ) : mode === 'vk' ? (
        /* VK ID CONSENT PANEL (redirect flow; account created on first exchange) */
        vkForm
      ) : mode === 'yandex' ? (
        /* YANDEX CONSENT PANEL (redirect flow; account created on first exchange) */
        yandexForm
      ) : (
        /* ─── REGISTER FORM ─── */
        <form onSubmit={handleRegister}>
          {/* Phone */}
          <div className="login-group">
            <label>Телефон *</label>
            <PhoneInput
              value={registerForm.phone}
              onChange={(phone) => setRegisterForm((prev) => ({ ...prev, phone }))}
              placeholder="+7 (999) 123-45-67"
              required
            />
            {registerForm.phone !== '' && !registerPhoneOk && (
              <p className="error-message">Введите телефон полностью</p>
            )}
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
            {registerForm.password !== '' && registerPwdError && (
              <p className="error-message">{registerPwdError}</p>
            )}
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

          <button
            type="submit"
            className="btn btn-primary btn-submit"
            disabled={loading || !registerValid}
          >
            {loading ? 'Регистрация...' : 'Зарегистрироваться'}
          </button>

          <div className="social-auth-divider">или</div>
          {/* Same MAX flow for registration: the account is created on the
              first verified code — no email/password needed. */}
          <SocialAuthButton
            provider="max"
            action="register"
            onClick={() => switchMode('max')}
          />
          <div style={{ marginTop: 8 }}>
            <SocialAuthButton provider="vk" action="register" onClick={() => switchMode('vk')} />
          </div>
          <div style={{ marginTop: 8 }}>
            <SocialAuthButton
              provider="yandex"
              action="register"
              onClick={() => switchMode('yandex')}
            />
          </div>

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
