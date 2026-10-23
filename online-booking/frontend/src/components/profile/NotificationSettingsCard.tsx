import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  notificationsApi,
  type NotificationChannelSetting,
  type NotificationSettings,
} from '../../api/cabinet';
import { getApiErrorMessage } from '../../utils/apiError';
import './ProfileCards.css';

interface ChannelMeta {
  key: 'max' | 'vk' | 'email';
  label: string;
  emptyHint: string;
  unavailableHint: string;
}

const CHANNELS: ChannelMeta[] = [
  {
    key: 'max',
    label: 'MAX',
    emptyHint: 'Привяжите MAX в карточке «Вход и привязки».',
    unavailableHint: 'Бот MAX не настроен на сервере.',
  },
  {
    key: 'vk',
    label: 'VK',
    emptyHint: 'Привяжите VK ID в карточке «Вход и привязки».',
    unavailableHint: 'Отправка в VK не подключена: нужен токен сообщества.',
  },
  {
    key: 'email',
    label: 'Почта',
    emptyHint: 'Добавьте и подтвердите почту в контактах.',
    unavailableHint: 'Отправка почты не настроена на сервере.',
  },
];

function ChannelRow({
  meta,
  channel,
  onChange,
}: {
  meta: ChannelMeta;
  channel: NotificationChannelSetting;
  onChange: (checked: boolean) => void;
}) {
  const hint = !channel.bound
    ? meta.emptyHint
    : !channel.available
      ? meta.unavailableHint
      : meta.key === 'email' && channel.value
        ? channel.value
        : undefined;
  return (
    <label className={`notify-channel${channel.available ? '' : ' disabled'}`}>
      <input
        type="checkbox"
        checked={channel.enabled && channel.available}
        disabled={!channel.available}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="notify-channel-body">
        <span className="notify-channel-name">{meta.label}</span>
        {hint && <span className="notify-channel-hint">{hint}</span>}
      </span>
    </label>
  );
}

/** Notification delivery settings shared by the client cabinet and master panel. */
function NotificationSettingsCard() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [data, setData] = useState<NotificationSettings | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const { data: payload } = await notificationsApi.getSettings();
        setData(payload);
      } catch (err: unknown) {
        toast.error(getApiErrorMessage(err, 'Не удалось загрузить настройки уведомлений'));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const update = (patch: Partial<NotificationSettings>) => {
    setData((prev) => (prev ? { ...prev, ...patch } : prev));
  };

  const updateChannel = (key: ChannelMeta['key'], enabled: boolean) => {
    setData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        channels: {
          ...prev.channels,
          [key]: { ...prev.channels[key], enabled },
        },
      };
    });
  };

  const save = async () => {
    if (!data) return;
    setSaving(true);
    try {
      const { data: payload } = await notificationsApi.updateSettings({
        instant_enabled: data.instant_enabled,
        reminders_enabled: data.reminders_enabled,
        preferred_channel: data.preferred_channel,
        master_digest_enabled: data.master_digest_enabled,
        digest_lead_minutes: data.digest_lead_minutes,
        max_enabled: data.channels.max.enabled,
        vk_enabled: data.channels.vk.enabled,
        email_enabled: data.channels.email.enabled,
      });
      setData(payload);
      toast.success('Настройки уведомлений сохранены');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось сохранить настройки'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="card notify-card">
        <h3>🔔 Уведомления</h3>
        <p className="profile-card-hint">Загружаем настройки…</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="card notify-card">
      <h3>🔔 Уведомления</h3>
      <p className="profile-card-hint">
        Колокольчик в приложении работает всегда. Здесь можно выбрать, куда дополнительно присылать
        сообщения о записях.
      </p>

      <div className="notify-section">
        <label className="notify-toggle">
          <input
            type="checkbox"
            checked={data.instant_enabled}
            onChange={(event) => update({ instant_enabled: event.target.checked })}
          />
          <span>
            <strong>Мгновенные уведомления</strong>
            <span className="notify-channel-hint">
              Новые записи, отмены, ответы и оценки — сразу в выбранный канал.
            </span>
          </span>
        </label>
        <label className="notify-toggle">
          <input
            type="checkbox"
            checked={data.reminders_enabled}
            onChange={(event) => update({ reminders_enabled: event.target.checked })}
          />
          <span>
            <strong>Напоминания о записи</strong>
            <span className="notify-channel-hint">За 24 часа и за 2 часа до визита.</span>
          </span>
        </label>
      </div>

      <div className="notify-section">
        <div className="notify-section-title">Каналы</div>
        {CHANNELS.map((meta) => (
          <ChannelRow
            key={meta.key}
            meta={meta}
            channel={data.channels[meta.key]}
            onChange={(checked) => updateChannel(meta.key, checked)}
          />
        ))}
      </div>

      <div className="form-group notify-select">
        <label htmlFor="notify-preferred">Основной канал</label>
        <select
          id="notify-preferred"
          value={data.preferred_channel}
          onChange={(event) =>
            update({
              preferred_channel: event.target.value as NotificationSettings['preferred_channel'],
            })
          }
        >
          <option value="auto">Как я вошёл в приложение</option>
          <option value="max" disabled={!data.channels.max.available}>
            MAX
          </option>
          <option value="vk" disabled={!data.channels.vk.available}>
            VK
          </option>
          <option value="email" disabled={!data.channels.email.available}>
            Почта
          </option>
          <option value="bell">Только колокольчик</option>
        </select>
        <span className="notify-channel-hint">
          «Как я вошёл» выбирает MAX, VK или почту по последнему способу входа.
        </span>
      </div>

      {data.is_master && (
        <div className="notify-section">
          <label className="notify-toggle">
            <input
              type="checkbox"
              checked={data.master_digest_enabled}
              onChange={(event) => update({ master_digest_enabled: event.target.checked })}
            />
            <span>
              <strong>Утренняя сводка</strong>
              <span className="notify-channel-hint">
                Записи на сегодня — за час до начала приёма. Время можно изменить.
              </span>
            </span>
          </label>
          <div className="form-group notify-select">
            <label htmlFor="notify-digest-lead">Когда присылать сводку</label>
            <select
              id="notify-digest-lead"
              value={String(data.digest_lead_minutes)}
              disabled={!data.master_digest_enabled}
              onChange={(event) => update({ digest_lead_minutes: Number(event.target.value) })}
            >
              <option value="30">За 30 минут до начала приёма</option>
              <option value="60">За час до начала приёма</option>
              <option value="120">За 2 часа до начала приёма</option>
            </select>
          </div>
        </div>
      )}

      <button type="button" className="btn btn-primary" disabled={saving} onClick={save}>
        {saving ? 'Сохранение…' : 'Сохранить настройки'}
      </button>
    </div>
  );
}

export default NotificationSettingsCard;
