import { useState, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi } from '../api/client';
import { PASSWORD_PLACEHOLDER } from '../constants';
import { passwordError } from '../utils/password';
import SocialAuthButton, { SocialAuthIconButton } from './common/SocialAuthButton';
import VkIdWidget from './common/VkIdWidget';
import YandexSuggestButton from './common/YandexSuggestButton';
import MaxIcon from './common/icons/MaxIcon';
import type { MaxStartResponse } from '../api/auth';
import PhoneInput, { maskPhone, isCompletePhone, PHONE_MAX_DIGITS } from './common/PhoneInput';
import { getCookie, decodeJwtPayload } from '../utils/cookies';
import { SUPER_PREFIX } from '../utils/section';
import Modal from './common/Modal';
import './LoginModal.css';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** After any successful auth, land here instead of the role default. */
  redirectTo?: string | null;
}

/** Modes: VK widget inline, Yandex — the official suggest widget (with the
    plain redirect button as fallback). */
type ModalMode = 'login' | 'register' | 'max';

interface LoginFormState {
  identifier: string; // email or phone
  password: string;
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
  });
  const [registerForm, setRegisterForm] = useState<RegisterFormState>({
    phone: '',
    password: '',
    consent: false,
  });
  const [loading, setLoading] = useState(false);
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);
  /** The 152-FZ checkbox on the register form — it gates the social block
      above the manual fields, so the consent-gate hint can jump back to it. */
  const consentRef = useRef<HTMLInputElement>(null);
  const focusConsent = () => consentRef.current?.focus();

  /** Yandex: the official suggest widget normally renders inline; when it
      cannot run here (third-party cookies blocked, SDK/config unavailable)
      the plain redirect button takes its place — both tabs switch together. */
  const [yandexRedirect, setYandexRedirect] = useState(false);

  // MAX chat-bot auth: code arrives INTO the MAX dialog, user types it on site
  const [maxPhone, setMaxPhone] = useState('');
  const [maxOffer, setMaxOffer] = useState<MaxStartResponse | null>(null);
  const [maxCodeInput, setMaxCodeInput] = useState('');

  /** Land by role: admins → their section, deep-link honored, everyone else
      (clients AND masters) → the client cabinet. Masters switch to the panel
      from inside the cabinet; there is no «войти как» switch anymore. */
  const landByRole = () => {
    setTimeout(() => {
      onClose();
      try {
        if (decodeJwtPayload(getCookie('access_token') ?? '')?.is_admin === true) {
          navigate(`${SUPER_PREFIX}/dashboard`, { replace: true });
          return;
        }
      } catch {
        /* fall through to cabinet */
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
      navigate('/cabinet', { replace: true });
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
      landByRole();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Ошибка входа');
    } finally {
      setLoading(false);
    }
  };

  /* Yandex OAuth redirect — the fallback path (the official suggest widget
     handles the normal case; this one works even without third-party
     cookies). No separate consent screen: 152-FZ consent is taken at
     registration, and a first social login IS a registration that stamps it
     implicitly. Fetch a signed state + authorize URL, stash the state, hand
     the browser to Yandex; the callback posts the code back for a
     server-side exchange. */
  const handleYandexStart = async () => {
    setLoading(true);
    try {
      const resp = await authApi.yandexStart();
      try {
        sessionStorage.setItem('yandex_state', resp.data.state);
        sessionStorage.setItem('yandex_consent', '1');
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
      // consent=true: a first MAX login is a registration (stamps 152-FZ);
      // for returning users the backend only backfills legacy NULL consent.
      const resp = await authApi.maxVerify(maxPhone, maxCodeInput.trim(), true);
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
      landByRole();
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
  const registerValid = registerPhoneOk && registerPwdError === null && registerForm.consent;

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

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title={
        mode === 'login'
          ? 'Вход в систему'
          : mode === 'register'
            ? 'Регистрация'
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

          <button type="submit" className="btn btn-primary btn-submit" disabled={loading}>
            {loading ? 'Входим...' : 'Войти'}
          </button>

          <div className="social-auth-divider">или</div>

          {/* VK + OK + Mail: the official OAuthList widget rendered INLINE —
              no separate screen, no consent checkbox (taken at registration). */}
          <VkIdWidget onSuccess={landByRole} />

          {/* Yandex: the official «мгновенная авторизация» widget; the plain
              redirect button only appears if the widget cannot run here. */}
          <div style={{ marginTop: 8 }}>
            {yandexRedirect ? (
              <SocialAuthButton
                provider="yandex"
                action="login"
                disabled={loading}
                onClick={handleYandexStart}
              />
            ) : (
              <YandexSuggestButton
                variant="login"
                onSuccess={landByRole}
                onUnavailable={() => setYandexRedirect(true)}
              />
            )}
          </div>
          <div style={{ marginTop: 8 }}>
            <SocialAuthButton provider="max" action="login" onClick={() => switchMode('max')} />
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
      ) : (
        /* ─── REGISTER FORM (the only place 152-FZ consent is asked) ─── */
        <form onSubmit={handleRegister}>
          {/* 152-ФЗ + оферта — the gate for everything below: the submit
              button, the VK widget and the Yandex/MAX tiles. Registration
              stays one tap, but only after this box is ticked. */}
          <div className="checkbox-group checkbox-group--first">
            <label className="checkbox-label">
              <input
                ref={consentRef}
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

          {/* Social registration FIRST — a one-tap account via VK/OK/Mail
              (the official widget) plus the Yandex/MAX tiles that continue its
              row. The whole block only exists once the consent box above is
              ticked: the widget is not mounted, the tiles are not rendered —
              no tick, no social sign-up. */}
          {registerForm.consent ? (
            <>
              <VkIdWidget onSuccess={landByRole} />
              <div className="social-icon-row">
                {yandexRedirect ? (
                  <SocialAuthIconButton
                    provider="yandex"
                    action="register"
                    disabled={loading}
                    onClick={handleYandexStart}
                  />
                ) : (
                  <YandexSuggestButton
                    variant="register"
                    onSuccess={landByRole}
                    onUnavailable={() => setYandexRedirect(true)}
                  />
                )}
                <SocialAuthIconButton
                  provider="max"
                  action="register"
                  disabled={loading}
                  onClick={() => switchMode('max')}
                />
              </div>
            </>
          ) : (
            <button type="button" className="social-gate" onClick={focusConsent}>
              Отметьте согласие с Офертой и Политикой — появятся кнопки VK, Яндекс и MAX
            </button>
          )}

          <div className="social-auth-divider">или заполните форму</div>

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

          <button
            type="submit"
            className="btn btn-primary btn-submit"
            disabled={loading || !registerValid}
          >
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
