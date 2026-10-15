import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { cabinetApi, mastersApi, servicesApi, assetUrl } from '../../api/client';
import type { Bundle } from '../../api/cabinet';
import type { Master, Service, Appointment } from '../../api/types';
import { ConfirmDialog, BackendImg, EmptyState, Modal, Skeleton } from '../../components/common';
import { Calendar } from '../../components/schedule/Calendar';
import CitySelect from '../../components/common/CitySelect';
import {
  appointmentSpanHours,
  formatDate,
  formatHour,
  getAppointmentsForSlot,
  getCoveringLive,
  isSlotPast,
} from '../../components/schedule/helpers';
import { getApiErrorMessage } from '../../utils/apiError';
import './CabinetBookPage.css';

function formatRating(rating?: number | null): string {
  if (rating === null || rating === undefined) return '';
  return `★ ${rating.toFixed(1)}`;
}

/** Effective price (discount applied) with struck full price for chips. */
function PriceTag({
  full,
  effective,
  discount,
  until,
  fixed,
}: {
  full: number;
  effective: number;
  discount?: number | null;
  until?: string | null;
  fixed?: number | string | null;
}) {
  const hasDisc = !!discount || Number(fixed) > 0;
  if (hasDisc && effective < full) {
    const bits: string[] = [];
    if (discount) bits.push(`−${discount}%`);
    if (Number(fixed) > 0) bits.push(`−${fixed} ₽`);
    let tag = bits.join(' ');
    if (until) {
      try {
        tag += ` (до ${new Date(until).toLocaleDateString('ru-RU', { day: 'numeric', month: 'numeric' })})`;
      } catch {
        /* ignore */
      }
    }
    return (
      <span
        style={{ whiteSpace: 'nowrap' }}
        title={until ? `Скидка действует до ${new Date(until).toLocaleString('ru-RU')}` : 'Скидка'}
      >
        <s style={{ color: '#999' }}>{full} ₽</s>{' '}
        <strong style={{ color: '#e5484d' }}>{effective} ₽</strong> {tag}
      </span>
    );
  }
  return <span>{effective} ₽</span>;
}

function serviceLabel(s: Service): string {
  const full = Number(s.price) || 0;
  const eff = Number(s.effective_price ?? s.price) || 0;
  const base = `${s.name} — ${s.duration_minutes} мин, ${eff} ₽`;
  if (!(eff < full)) return base;
  const bits: string[] = [];
  if (s.discount_percent) bits.push(`−${s.discount_percent}%`);
  if (Number(s.discount_fixed) > 0) bits.push(`−${s.discount_fixed} ₽`);
  if (bits.length === 0) return base;
  const until = s.discount_until
    ? ` до ${new Date(s.discount_until).toLocaleDateString('ru-RU', { day: 'numeric', month: 'numeric' })}`
    : '';
  return `${base} (${bits.join(' ')}${until})`;
}

/** Read-only granules for clients: free ones open the booking modal. */
function ClientSlots({
  date,
  windowStart,
  windowEnd,
  activeHours,
  busy,
  onPick,
}: {
  date: Date;
  windowStart: number;
  windowEnd: number;
  activeHours: Record<string, boolean>;
  busy: Appointment[];
  onPick: (hour: number) => void;
}) {
  const dateStr = formatDate(date);
  const rows = [];
  for (let h = windowStart; h < windowEnd; h++) {
    const starters = getAppointmentsForSlot(busy, date, h).filter((s) => s.status !== 'cancelled');
    const coveredBy = starters.length === 0 ? getCoveringLive(busy, date, h) : null;
    const past = isSlotPast(date, h);
    const hourActive = !!activeHours[`${dateStr}-${h}`];
    const live = starters[0] ?? coveredBy;
    const free = !past && hourActive && !live;
    rows.push(
      <button
        key={h}
        type="button"
        disabled={!free}
        onClick={() => onPick(h)}
        className={`slot-row${live ? ` slot-${live.status}` : ''}${!hourActive ? ' slot-off' : ''}${past ? ' slot-past' : ''}`}
        title={
          live
            ? `Занято (${live.client_name || 'запись'})`
            : !hourActive
              ? 'Мастер не работает в этот час'
              : past
                ? 'Время прошло'
                : `Записаться на ${formatHour(h)}`
        }
      >
        <span className="slot-time">{formatHour(h)}</span>
        {live ? (
          <span className="slot-who">
            Занято
            {appointmentSpanHours(live) > 1 ? ` · ${appointmentSpanHours(live)} гр.` : ''}
          </span>
        ) : (
          <span className="slot-free">{past ? 'Прошёл' : hourActive ? '+ Записаться' : '—'}</span>
        )}
      </button>,
    );
  }
  return <div className="slot-list">{rows}</div>;
}

function CabinetBookPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // Deep link from the home carousel: /cabinet/book?master_id=X preselects.
  const deepMasterId = Number(searchParams.get('master_id')) || null;
  const deepMasterDone = useRef(false);
  const [cityId, setCityId] = useState<number | null>(null);
  const [cityName, setCityName] = useState('');
  const [masters, setMasters] = useState<Master[]>([]);
  const [mastersLoading, setMastersLoading] = useState(true);
  const [servicesByMaster, setServicesByMaster] = useState<Record<number, Service[]>>({});
  const [serviceFilter, setServiceFilter] = useState('');
  const [masterQuery, setMasterQuery] = useState('');
  const [selectedMaster, setSelectedMaster] = useState<Master | null>(null);

  const [monthISO, setMonthISO] = useState(() => new Date().toISOString().slice(0, 7));
  const currentMonth = useMemo(() => new Date(`${monthISO}-01T00:00:00`), [monthISO]);
  const [windowRange, setWindowRange] = useState({ start: 8, end: 22 });
  const [schedule, setSchedule] = useState<Record<string, { start: number; end: number }>>({});
  const [activeHours, setActiveHours] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState<Appointment[]>([]);
  const [scheduleLoading, setScheduleLoading] = useState(false);

  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [slotHour, setSlotHour] = useState<number | null>(null);
  const [modalServiceId, setModalServiceId] = useState<number | ''>('');
  const [modalBundle, setModalBundle] = useState<Bundle | null>(null);
  const [notes, setNotes] = useState('');
  const [bookingLoading, setBookingLoading] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [aboutMaster, setAboutMaster] = useState<Master | null>(null);
  const scheduleRef = useRef<HTMLDivElement>(null);

  const pickMaster = (m: Master) => {
    setSelectedMaster(m);
    // The schedule renders below a long list — bring it into view at once.
    requestAnimationFrame(() => {
      scheduleRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  // Own city first (trip? pick another — masters reload).
  // Own user id too: a master-as-client never sees (or books) themselves.
  // Deep link wins over the city: the carousel master may be elsewhere.
  const [myUserId, setMyUserId] = useState<number | null>(null);
  useEffect(() => {
    cabinetApi
      .me()
      .then((resp) => {
        if (deepMasterId) {
          setCityId(null);
          setCityName('');
        } else if (resp.data.city_id) {
          setCityId(resp.data.city_id);
          setCityName(resp.data.city_name || '');
        }
        setMyUserId(resp.data.id);
      })
      .catch(() => {
        /* public flow without a city */
      });
  }, []);

  // Masters of the city + their services (for the service filter).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setMastersLoading(true);
      setSelectedMaster(null);
      try {
        const res = await mastersApi.getAll(cityId ?? undefined);
        if (cancelled) return;
        setMasters(res.data);
        const entries = await Promise.all(
          res.data.map(async (m) => {
            try {
              const s = await servicesApi.getAll(m.id);
              return [m.id, (s.data || []).filter((x) => x.is_active !== false)] as const;
            } catch (err) {
              console.warn('[CabinetBook] services failed for master', m.id, err);
              return [m.id, []] as const;
            }
          }),
        );
        if (!cancelled) setServicesByMaster(Object.fromEntries(entries));
      } catch {
        if (!cancelled) toast.error('Не удалось загрузить мастеров');
      } finally {
        if (!cancelled) setMastersLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [cityId]);

  // Deep link: once masters arrive, jump straight to the carousel master
  // (schedule loads via the selectedMaster effect below).
  useEffect(() => {
    if (!deepMasterId || deepMasterDone.current || masters.length === 0) return;
    const found = masters.find((m) => m.id === deepMasterId) ?? null;
    deepMasterDone.current = true;
    if (found && found.user_id !== myUserId) pickMaster(found);
    else toast.error('Мастер не найден — выберите вручную');
  }, [masters, myUserId]);

  const serviceNames = useMemo(() => {
    const set = new Set<string>();
    for (const list of Object.values(servicesByMaster)) {
      for (const s of list) set.add(s.name);
    }
    return [...set].sort((a, b) => a.localeCompare(b, 'ru'));
  }, [servicesByMaster]);

  const visibleMasters = useMemo(() => {
    const q = masterQuery.trim().toLowerCase();
    return masters.filter((m) => {
      // No self-booking: hide your own master profile (backend also 400s).
      if (myUserId !== null && m.user_id === myUserId) return false;
      if (q && !m.name.toLowerCase().includes(q)) return false;
      if (serviceFilter && !(servicesByMaster[m.id] || []).some((s) => s.name === serviceFilter))
        return false;
      return true;
    });
  }, [masters, masterQuery, serviceFilter, servicesByMaster, myUserId]);

  // Complexes of the chosen master (booking modal only — never a
  // standalone list: complexes belong to their master).
  const [bundlesByMaster, setBundlesByMaster] = useState<Record<number, Bundle[]>>({});
  useEffect(() => {
    if (!selectedMaster) return;
    let cancelled = false;
    cabinetApi.bundles(selectedMaster.id).then(
      (r) => {
        if (!cancelled) {
          setBundlesByMaster((prev) => ({ ...prev, [selectedMaster.id]: r.data || [] }));
        }
      },
      () => {
        if (!cancelled) {
          setBundlesByMaster((prev) => ({ ...prev, [selectedMaster.id]: [] }));
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [selectedMaster?.id]);

  // Active schedule of the chosen master.
  useEffect(() => {
    if (!selectedMaster) return;
    let cancelled = false;
    (async () => {
      setScheduleLoading(true);
      setSelectedDate(null);
      try {
        const { data } = await cabinetApi.getBookSchedule(selectedMaster.id, monthISO);
        if (cancelled) return;
        setWindowRange({ start: data.window.start_hour, end: data.window.end_hour });
        const hours: Record<string, boolean> = {};
        const sched: Record<string, { start: number; end: number }> = {};
        for (const w of data.working_hours) {
          const s = Number(String(w.start).slice(0, 2));
          const e = Number(String(w.end).slice(0, 2));
          sched[w.date] = { start: s, end: e };
          for (let h = s; h < e; h++) hours[`${w.date}-${h}`] = true;
        }
        setSchedule(sched);
        setActiveHours(hours);
        setBusy(
          (data.busy || []).map((b, i) => ({
            id: -(i + 1),
            master_id: data.master_id,
            service_id: 0,
            appointment_date: b.appointment_date,
            status: b.status as Appointment['status'],
            service_duration: b.service_duration,
          })) as Appointment[],
        );
      } catch (err: unknown) {
        if (!cancelled) toast.error(getApiErrorMessage(err, 'Не удалось загрузить расписание'));
      } finally {
        if (!cancelled) setScheduleLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedMaster?.id, monthISO]);

  const openSlot = (hour: number) => {
    const list = selectedMaster ? servicesByMaster[selectedMaster.id] || [] : [];
    // A pre-picked complex stays locked; otherwise default to first service.
    if (!(modalBundle && selectedMaster && modalBundle.master_id === selectedMaster.id)) {
      setModalBundle(null);
      setModalServiceId(list.length > 0 ? list[0].id : '');
    } else {
      setModalServiceId('');
    }
    setNotes('');
    setPromo('');
    setPromoResult(null);
    setPromoError('');
    setSlotHour(hour);
    // Own usable codes of this master (datalist under the promo field).
    if (selectedMaster) {
      cabinetApi
        .myCoupons(selectedMaster.id)
        .then((r) => setPromoOptions((r.data || []).map((c) => ({ code: c.code, terms: c.terms }))))
        .catch(() => setPromoOptions([]));
    }
  };

  const modalServices = selectedMaster ? servicesByMaster[selectedMaster.id] || [] : [];
  const modalService = modalServices.find((s) => s.id === modalServiceId) ?? null;
  // Complexes of the chosen master, first in the service select.
  const modalBundles = selectedMaster ? bundlesByMaster[selectedMaster.id] || [] : [];
  const modalPickValue =
    modalBundle && selectedMaster && modalBundle.master_id === selectedMaster.id
      ? `bundle:${modalBundle.id}`
      : modalServiceId === ''
        ? ''
        : `service:${modalServiceId}`;

  const handleModalPick = (value: string) => {
    if (value.startsWith('bundle:')) {
      const b = modalBundles.find((x) => x.id === Number(value.slice(7))) ?? null;
      setModalBundle(b);
      setModalServiceId('');
    } else if (value.startsWith('service:')) {
      setModalBundle(null);
      const id = Number(value.slice(8));
      setModalServiceId(value === '' || Number.isNaN(id) ? '' : id);
    } else {
      setModalBundle(null);
      setModalServiceId('');
    }
    // A different item may have a different price — re-check the promo.
    setPromoResult(null);
    setPromoError('');
  };

  // Promo code: preview against the current pick, applied on booking.
  const [promo, setPromo] = useState('');
  const [promoOptions, setPromoOptions] = useState<{ code: string; terms: string }[]>([]);
  const [promoResult, setPromoResult] = useState<{
    code: string;
    terms: string;
    base_price: number;
    discount: number;
    new_price: number;
  } | null>(null);
  const [promoError, setPromoError] = useState('');
  const [promoChecking, setPromoChecking] = useState(false);

  const applyPromo = async () => {
    if (!selectedMaster || (!modalBundle && modalServiceId === '')) return;
    const code = promo.trim();
    if (!code) return;
    setPromoChecking(true);
    setPromoError('');
    try {
      const { data } = await cabinetApi.previewCoupon({
        master_id: selectedMaster.id,
        ...(modalBundle ? { bundle_id: modalBundle.id } : { service_id: Number(modalServiceId) }),
        code,
      });
      setPromoResult(data);
    } catch (err: unknown) {
      setPromoResult(null);
      setPromoError(getApiErrorMessage(err, 'Купон не подошёл'));
    } finally {
      setPromoChecking(false);
    }
  };

  const handleBook = async () => {
    if (!selectedMaster || !selectedDate || slotHour === null) return;
    if (!modalBundle && modalServiceId === '') return;
    const y = selectedDate.getFullYear();
    const m = String(selectedDate.getMonth() + 1).padStart(2, '0');
    const d = String(selectedDate.getDate()).padStart(2, '0');
    // Typed but never applied: validate silently so the code still counts.
    let coupon = promoResult;
    if (!coupon && promo.trim()) {
      try {
        const { data } = await cabinetApi.previewCoupon({
          master_id: selectedMaster.id,
          ...(modalBundle ? { bundle_id: modalBundle.id } : { service_id: Number(modalServiceId) }),
          code: promo.trim(),
        });
        coupon = data;
        setPromoResult(data);
      } catch (err: unknown) {
        toast.error(getApiErrorMessage(err, 'Купон не подошёл — запись без скидки?'));
        return;
      }
    }
    setBookingLoading(true);
    try {
      const { data } = await cabinetApi.bookAppointment({
        master_id: selectedMaster.id,
        ...(modalBundle ? { bundle_id: modalBundle.id } : { service_id: Number(modalServiceId) }),
        appointment_date: `${y}-${m}-${d}T${String(slotHour).padStart(2, '0')}:00:00`,
        notes: notes.trim() || undefined,
        ...(coupon ? { coupon_code: coupon.code } : {}),
      });
      // The server decides: auto-confirm masters return confirmed at once.
      if (data.status === 'confirmed') {
        toast.success('Запись подтверждена ✅ Ждём вас!');
      } else {
        toast.success('Заявка отправлена! Мастер подтвердит запись 🔔');
      }
      setSlotHour(null);
      setModalBundle(null);
      setPromo('');
      setPromoResult(null);
      setPromoError('');
      navigate('/cabinet');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось записаться'));
    } finally {
      setBookingLoading(false);
    }
  };

  return (
    <div className="cabinet-book-page">
      <div className="page-header">
        <div>
          <h1>💅 Записаться</h1>
          <p>Мастера вашего города → расписание → свободная гранула</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="book-filters">
          <div className="filter-cell">
            <label className="filter-label">📍 Город {cityId ? '' : '(все города)'}</label>
            <CitySelect
              value={cityId}
              valueName={cityName}
              onChange={(c) => {
                setCityId(c?.id ?? null);
                setCityName(c?.name ?? '');
              }}
              label=""
            />
          </div>
          <div className="filter-cell">
            <label className="filter-label">💇 Услуга</label>
            <select
              className="filter-control"
              value={serviceFilter}
              onChange={(e) => setServiceFilter(e.target.value)}
            >
              <option value="">Все услуги</option>
              {serviceNames.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-cell">
            <label className="filter-label">🔍 Мастер</label>
            <input
              type="text"
              className="filter-control"
              placeholder="Имя мастера..."
              value={masterQuery}
              onChange={(e) => setMasterQuery(e.target.value)}
            />
          </div>
        </div>
      </div>

      {mastersLoading ? (
        <div className="card">
          <Skeleton rows={3} />
        </div>
      ) : visibleMasters.length === 0 ? (
        <EmptyState
          icon="👨‍💼"
          title={cityId ? 'В этом городе мастеров нет' : 'Мастеров пока нет'}
          description="Попробуйте другой город или сбросьте фильтры"
        />
      ) : (
        <div className="master-pick-list">
          {visibleMasters.map((m) => (
            <label
              key={m.id}
              className={`master-pick${selectedMaster?.id === m.id ? ' selected' : ''}`}
            >
              <input
                type="radio"
                name="cabinet-master"
                checked={selectedMaster?.id === m.id}
                onChange={() => pickMaster(m)}
              />
              {m.avatar_preset ? (
                <span
                  className="master-pick-avatar master-pick-emoji"
                  role="img"
                  aria-label={m.name}
                >
                  {m.avatar_preset}
                </span>
              ) : m.avatar_url ? (
                <BackendImg
                  src={assetUrl(m.avatar_url)}
                  alt={m.name}
                  className="master-pick-avatar"
                  fallbackEmoji="📷"
                />
              ) : null}
              <span className="master-pick-main">
                <strong>
                  {m.name} {formatRating(m.avg_rating)}
                </strong>
                {[m.cabinet_address, m.city_name].filter(Boolean).join(' • ') || 'Адрес уточняйте'}
                {m.experience_years != null && <span> · опыт {m.experience_years} лет</span>}
                {m.description && <span className="master-pick-desc">{m.description}</span>}
                <span>
                  <button
                    type="button"
                    className="master-about-btn"
                    onClick={(e) => {
                      // Inside a <label>: block the radio toggle, open profile.
                      e.preventDefault();
                      setAboutMaster(m);
                    }}
                  >
                    О мастере →
                  </button>
                </span>
              </span>
            </label>
          ))}
        </div>
      )}

      {selectedMaster && (
        <div className="card" style={{ marginTop: 12 }}>
          <details>
            <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
              💇 Услуги и наборы мастера — цены и время
            </summary>
            <div style={{ marginTop: 8 }}>
              {(servicesByMaster[selectedMaster.id] || []).map((s) => (
                <div key={s.id} className="bundle-chip" style={{ margin: '0 6px 6px 0' }}>
                  {s.name} · {s.duration_minutes} мин ·{' '}
                  <PriceTag
                    full={Number(s.price) || 0}
                    effective={Number(s.effective_price ?? s.price) || 0}
                    discount={s.discount_percent}
                    until={s.discount_until}
                    fixed={s.discount_fixed}
                  />
                </div>
              ))}
              {(servicesByMaster[selectedMaster.id] || []).length === 0 && (
                <p className="hint">Услуги уточняйте у мастера</p>
              )}
              {(bundlesByMaster[selectedMaster.id] || []).map((b) => (
                <div key={`b-${b.id}`} className="bundle-chip" style={{ margin: '0 6px 6px 0' }}>
                  🎁 {b.name} · {b.duration_total} мин ·{' '}
                  <PriceTag
                    full={b.price != null ? b.price : b.price_total}
                    effective={b.effective_price}
                    discount={b.discount_percent}
                    until={b.discount_until}
                    fixed={b.discount_fixed}
                  />
                </div>
              ))}
            </div>
          </details>
        </div>
      )}

      {selectedMaster && (
        <div className="card" id="cabinet-schedule" ref={scheduleRef} style={{ marginTop: 16 }}>
          <div className="card-header">
            <h3>📅 {selectedMaster.name} — активное расписание</h3>
          </div>
          {scheduleLoading ? (
            <Skeleton rows={4} />
          ) : (
            <>
              <Calendar
                currentMonth={currentMonth}
                schedule={schedule}
                appointments={busy}
                selectedDate={selectedDate}
                onPrevMonth={() =>
                  setMonthISO((iso) => {
                    const [y, mo] = iso.split('-').map(Number);
                    const d = new Date(y, mo - 2, 1);
                    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
                  })
                }
                onNextMonth={() =>
                  setMonthISO((iso) => {
                    const [y, mo] = iso.split('-').map(Number);
                    const d = new Date(y, mo, 1);
                    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
                  })
                }
                onSelectDate={setSelectedDate}
                onToggleDay={() => undefined}
                interactive={false}
              />
              {selectedDate &&
                (schedule[formatDate(selectedDate)] ? (
                  <ClientSlots
                    date={selectedDate}
                    windowStart={windowRange.start}
                    windowEnd={windowRange.end}
                    activeHours={activeHours}
                    busy={busy}
                    onPick={openSlot}
                  />
                ) : (
                  <EmptyState title="В этот день мастер не работает" icon="😴" />
                ))}
            </>
          )}
        </div>
      )}

      <Modal
        open={slotHour !== null}
        onClose={() => {
          // Don't lose a half-filled booking on an accidental X.
          if (slotHour !== null && (modalServiceId !== '' || modalBundle)) setConfirmCancel(true);
          else setSlotHour(null);
        }}
        title="📅 Подтвердите запись"
      >
        {selectedMaster && selectedDate && slotHour !== null && (
          <div className="book-confirm">
            <p>
              <strong>{selectedMaster.name}</strong>
              <br />
              {selectedDate.toLocaleDateString('ru-RU', {
                weekday: 'long',
                day: 'numeric',
                month: 'long',
              })}{' '}
              в {formatHour(slotHour)}
            </p>
            <div className="form-group">
              <label>Услуга</label>
              {modalBundle && selectedMaster && modalBundle.master_id === selectedMaster.id ? (
                <div className="book-bundle-lock">
                  <div>
                    <strong>🎁 {modalBundle.name}</strong>
                    <div className="hint">
                      {modalBundle.services
                        .map((s) => `${s.name} (${s.duration_minutes} мин)`)
                        .join(' + ')}{' '}
                      · ⏱ {modalBundle.duration_total} мин ·{' '}
                      <PriceTag
                        full={
                          modalBundle.price != null ? modalBundle.price : modalBundle.price_total
                        }
                        effective={modalBundle.effective_price}
                        discount={modalBundle.discount_percent}
                        until={modalBundle.discount_until}
                        fixed={modalBundle.discount_fixed}
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-sm btn-ghost"
                    onClick={() => {
                      setModalBundle(null);
                      const list = servicesByMaster[selectedMaster.id] || [];
                      setModalServiceId(list.length > 0 ? list[0].id : '');
                    }}
                  >
                    Сменить
                  </button>
                </div>
              ) : (
                <select
                  value={modalPickValue}
                  aria-label="Выбор услуги или комплекса"
                  onChange={(e) => handleModalPick(e.target.value)}
                >
                  <option value="" disabled>
                    Выберите услугу…
                  </option>
                  {modalBundles.length > 0 && (
                    <optgroup label="🎁 Комплексы">
                      {modalBundles.map((b) => {
                        const bits: string[] = [];
                        if (b.discount_percent) bits.push(`−${b.discount_percent}%`);
                        if (Number(b.discount_fixed) > 0) bits.push(`−${b.discount_fixed} ₽`);
                        let suffix = '';
                        if (bits.length > 0) {
                          suffix = ` (${bits.join(' ')}`;
                          if (b.discount_until) {
                            try {
                              suffix += ` до ${new Date(b.discount_until).toLocaleDateString('ru-RU', { day: 'numeric', month: 'numeric' })}`;
                            } catch {
                              /* ignore */
                            }
                          }
                          suffix += ')';
                        }
                        return (
                          <option key={b.id} value={`bundle:${b.id}`}>
                            🎁 {b.name} — {b.duration_total} мин, {b.effective_price} ₽{suffix}
                          </option>
                        );
                      })}
                    </optgroup>
                  )}
                  <optgroup label="Услуги">
                    {modalServices.map((s) => (
                      <option key={s.id} value={`service:${s.id}`}>
                        {serviceLabel(s)}
                      </option>
                    ))}
                  </optgroup>
                </select>
              )}
              {modalService && (
                <span className="hint">
                  Займёт {formatHour(slotHour)}–
                  {(() => {
                    const dur = Number(modalService.duration_minutes) || 60;
                    const endH = slotHour + Math.floor(dur / 60);
                    const endM = dur % 60;
                    return `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;
                  })()}
                </span>
              )}
              {modalBundle && selectedMaster && modalBundle.master_id === selectedMaster.id && (
                <span className="hint">
                  Займёт {formatHour(slotHour)}–
                  {(() => {
                    const dur = modalBundle.duration_total || 60;
                    const endH = slotHour + Math.floor(dur / 60);
                    const endM = dur % 60;
                    return `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;
                  })()}
                </span>
              )}
            </div>
            <div className="form-group">
              <label>Комментарий (необязательно)</label>
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Пожелания мастеру..."
                maxLength={140}
              />
              <span className="hint">
                {notes.length}/140 — коротко, чтобы влезло в слот расписания
              </span>
            </div>
            <div className="form-group">
              <label>Промокод (если мастер выдал купон)</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  value={promo}
                  onChange={(e) => {
                    setPromo(e.target.value);
                    setPromoResult(null);
                    setPromoError('');
                  }}
                  placeholder="XXXX-XXXX"
                  style={{ textTransform: 'uppercase' }}
                  maxLength={24}
                  list="promo-codes"
                />
                <datalist id="promo-codes">
                  {promoOptions.map((o) => (
                    <option key={o.code} value={o.code}>
                      {o.terms}
                    </option>
                  ))}
                </datalist>
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  disabled={promoChecking || !promo.trim()}
                  onClick={applyPromo}
                  style={{ flex: '0 0 auto' }}
                >
                  {promoChecking ? '…' : 'Применить'}
                </button>
              </div>
              {promoError && (
                <span className="hint" style={{ color: '#e5484d' }}>
                  {promoError}
                </span>
              )}
              {promoResult && (
                <span className="hint" style={{ color: '#0f766e', fontWeight: 600 }}>
                  🎟 {promoResult.terms}: {promoResult.base_price} → {promoResult.new_price} ₽
                </span>
              )}
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setSlotHour(null)}>
                Отмена
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={(!modalBundle && modalServiceId === '') || bookingLoading}
                onClick={handleBook}
              >
                {bookingLoading ? 'Записываем…' : 'Записаться'}
              </button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={aboutMaster !== null}
        onClose={() => setAboutMaster(null)}
        title={`👤 ${aboutMaster?.name || ''}`}
      >
        {aboutMaster && (
          <div className="master-about">
            <div className="master-about-head">
              {aboutMaster.avatar_preset ? (
                <span className="master-about-avatar" role="img" aria-label={aboutMaster.name}>
                  {aboutMaster.avatar_preset}
                </span>
              ) : aboutMaster.avatar_url ? (
                <BackendImg
                  src={assetUrl(aboutMaster.avatar_url)}
                  alt={aboutMaster.name}
                  className="master-about-avatar"
                  fallbackEmoji="📷"
                />
              ) : (
                <span className="master-about-avatar master-about-empty">📷</span>
              )}
              <div>
                <strong>
                  {aboutMaster.name} {formatRating(aboutMaster.avg_rating)}
                </strong>
                <div className="master-about-sub">{aboutMaster.city_name || 'Город уточняйте'}</div>
                <div className="master-about-sub">
                  Кабинет: {aboutMaster.cabinet_address || 'адрес уточняйте'}
                </div>
                {aboutMaster.experience_years != null && (
                  <div className="master-about-sub">Опыт: {aboutMaster.experience_years} лет</div>
                )}
              </div>
            </div>
            <h4>О себе</h4>
            {aboutMaster.description ? (
              <p className="master-about-desc">{aboutMaster.description}</p>
            ) : (
              <p className="master-about-sub">Мастер пока ничего не рассказал о себе</p>
            )}
            <h4>Сертификаты</h4>
            {!aboutMaster.certificates || aboutMaster.certificates.length === 0 ? (
              <p className="master-about-sub">Пока нет</p>
            ) : (
              <div className="master-about-certs">
                {aboutMaster.certificates.map((c, i) => (
                  <div key={`${c.name}-${i}`} className="master-about-cert">
                    {c.url && (
                      <a href={assetUrl(c.url) || ''} target="_blank" rel="noreferrer">
                        <BackendImg src={assetUrl(c.url)} alt={c.name} />
                      </a>
                    )}
                    <span>{c.name}</span>
                  </div>
                ))}
              </div>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  if (aboutMaster) pickMaster(aboutMaster);
                  setAboutMaster(null);
                }}
              >
                Выбрать
              </button>
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={confirmCancel}
        onClose={() => setConfirmCancel(false)}
        title="Закрыть без записи?"
        message="Выбранные услуга и время не сохранятся."
        confirmLabel="Закрыть"
        onConfirm={() => {
          setConfirmCancel(false);
          setSlotHour(null);
        }}
      />
    </div>
  );
}

export default CabinetBookPage;
