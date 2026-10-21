import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { referralApi } from '../../api/client';
import './ReferralPage.css';

const TOKEN_KEY = 'bs_referral_click';

function ReferralPage() {
  const { code } = useParams<{ code: string }>();
  const [state, setState] = useState<'loading' | 'ok' | 'error'>('loading');
  const [masterName, setMasterName] = useState('');
  const started = useRef(false);

  useEffect(() => {
    if (!code || started.current) return;
    started.current = true;
    referralApi
      .click(code)
      .then(({ data }) => {
        localStorage.setItem(
          TOKEN_KEY,
          JSON.stringify({ token: data.token, code: data.referral_code, at: Date.now() }),
        );
        setMasterName(data.master_name);
        setState('ok');
      })
      .catch(() => setState('error'));
  }, [code]);

  return (
    <div className="referral-landing">
      <div className="referral-card">
        <div className="referral-logo">✦ Beauty Specialist</div>
        {state === 'loading' && (
          <>
            <h1>Открываем приглашение…</h1>
            <p>Секунду, проверяем реферальную ссылку.</p>
          </>
        )}
        {state === 'ok' && (
          <>
            <div className="referral-emoji">🤝</div>
            <h1>Вас пригласил{masterName ? ` ${masterName}` : ' мастер'}</h1>
            <p>
              Войдите или зарегистрируйтесь — приглашение сохранится и привяжется к вашему аккаунту
              автоматически.
            </p>
            <div className="referral-rules">
              <div>
                <strong>14 дней</strong>
                <span>полного доступа к кабинету мастера</span>
              </div>
              <div>
                <strong>7 записей</strong>
                <span>от клиентов за первые 14 дней</span>
              </div>
              <div>
                <strong>125 ₽</strong>
                <span>бонус пригласившему после проверки</span>
              </div>
            </div>
            <Link className="referral-cta" to="/">
              Продолжить →
            </Link>
            <p className="referral-hint">
              Ссылка действует 60 дней. Приглашение не суммируется с другим мастером.
            </p>
          </>
        )}
        {state === 'error' && (
          <>
            <div className="referral-emoji">🔗</div>
            <h1>Ссылка не найдена</h1>
            <p>
              Возможно, она истекла или была скопирована с ошибкой. Попросите коллегу прислать
              новую.
            </p>
            <Link className="referral-cta" to="/">
              На главную →
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

export default ReferralPage;
