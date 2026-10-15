import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { adminApi } from '../../api/client';
import { ConfirmDialog, DataTable, Skeleton, EmptyState, Pager } from '../../components/common';
import { RecipientPicker } from '../../components/common';
import type { RecipientOption } from '../../components/common';
import type { FitColumnDef } from '../../components/common';
import { usePersistentState } from '../../utils/persistentState';
import type { Service } from '../../api/types';
import type { Bundle } from '../../api/cabinet';
import { formatPrice, formatDiscountTag } from '../../components/schedule/helpers';
import { getApiErrorMessage, getApiErrorStatus } from '../../utils/apiError';
import '../../styles/tables.css';
import './ServicesPage.css';

/** 🏷 Inline discount editor: click the badge, set % + expiry right in the row.
 * Closes on ✓, ✕, Escape or a click outside. */
function DiscountBadge({
  pct,
  until,
  onSave,
}: {
  pct?: number | null;
  until?: string | null;
  onSave: (pct: number | null, until: string | null) => Promise<void> | void;
}) {
  const [open, setOpen] = useState(false);
  const [v, setV] = useState(pct ? String(pct) : '');
  const [u, setU] = useState(until ? String(until).slice(0, 16) : '');
  const [saving, setSaving] = useState(false);
  const boxRef = useRef<HTMLSpanElement>(null);

  // Escape + outside click close the editor (inputs keep working inside).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    const onDown = (e: PointerEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onDown);
    };
  }, [open]);

  const save = async () => {
    const num = v.trim() === '' ? null : Math.round(Number(v));
    if (num !== null && !(num >= 0 && num <= 90)) {
      toast.error('Скидка — от 0 до 90%');
      return;
    }
    setSaving(true);
    try {
      await onSave(num, u.trim() === '' ? null : new Date(u).toISOString());
      setOpen(false);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось сохранить скидку'));
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        className="btn btn-sm btn-ghost"
        onClick={() => {
          setV(pct ? String(pct) : '');
          setU(until ? String(until).slice(0, 16) : '');
          setOpen(true);
        }}
        title={pct ? `Скидка −${pct}% — нажать, чтобы изменить` : 'Назначить скидку'}
        aria-label="Скидка"
        style={pct ? { borderColor: '#e5484d', color: '#e5484d' } : undefined}
      >
        🏷️{pct ? ` −${pct}%` : ''}
      </button>
    );
  }
  return (
    <span
      ref={boxRef}
      style={{ display: 'inline-flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}
    >
      <input
        type="number"
        min={0}
        max={90}
        value={v}
        onChange={(e) => setV(e.target.value)}
        placeholder="%"
        aria-label="Скидка, %"
        style={{ width: 64 }}
      />
      <input
        type="datetime-local"
        value={u}
        onChange={(e) => setU(e.target.value)}
        aria-label="Скидка до"
        title="Скидка до (пусто = бессрочно)"
        style={{ width: 170 }}
      />
      <button
        type="button"
        className="btn btn-sm btn-primary"
        disabled={saving}
        onClick={save}
        title="Сохранить скидку"
      >
        ✓
      </button>
      <button
        type="button"
        className="btn btn-sm btn-ghost"
        onClick={() => setOpen(false)}
        title="Закрыть"
      >
        ✕
      </button>
    </span>
  );
}

interface CouponRow {
  id: number;
  code: string;
  kind: string;
  value: number;
  max_uses: number | null;
  used_count: number;
  uses_left: number | null;
  audience: string;
  user_ids: number[];
  valid_until: string | null;
  is_active: boolean;
}

function ServicesPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [duration, setDuration] = useState(30);
  const [price, setPrice] = useState(1000);
  // Discount % (empty = none, 0-90).
  const [discount, setDiscount] = useState('');
  // Discount expiry, datetime-local value (empty = no expiry).
  const [discountUntil, setDiscountUntil] = useState('');
  const [lastCategory, setLastCategory] = usePersistentState('services.lastCategory', '');
  const [category, setCategory] = useState('');
  const [categoryCustom, setCategoryCustom] = useState(false);

  // ─── Bundles (complexes): separate feature, assembled from services ───
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [allServices, setAllServices] = useState<Service[]>([]);
  const [showBundleForm, setShowBundleForm] = useState(false);
  const [editingBundleId, setEditingBundleId] = useState<number | null>(null);
  const [deletingBundleId, setDeletingBundleId] = useState<number | null>(null);
  const [bundleName, setBundleName] = useState('');
  const [bundlePrice, setBundlePrice] = useState('');
  const [bundleDiscount, setBundleDiscount] = useState('');
  const [bundleDiscountUntil, setBundleDiscountUntil] = useState('');
  // Manual total time: a complex often takes less than the member sum.
  // Empty = sum of per-service minutes above.
  const [bundleTime, setBundleTime] = useState('');
  const [picked, setPicked] = useState<Set<number>>(new Set());
  // ─── Coupons (personal codes to own clients) ───
  const [coupons, setCoupons] = useState<CouponRow[]>([]);
  const [showCouponForm, setShowCouponForm] = useState(false);
  const [couponKind, setCouponKind] = useState('percent');
  const [couponValue, setCouponValue] = useState('');
  const [couponUses, setCouponUses] = useState('');
  const [couponUntil, setCouponUntil] = useState('');
  const [couponClients, setCouponClients] = useState<RecipientOption[]>([]);
  const [couponPicked, setCouponPicked] = useState<Set<number>>(new Set());
  const [deletingCouponId, setDeletingCouponId] = useState<number | null>(null);
  // Per-service minutes inside the complex (default = service's own time).
  const [durMap, setDurMap] = useState<Record<number, number>>({});

  const existingCategories = [
    ...new Set(services.map((s) => s.category).filter(Boolean)),
  ] as string[];

  const fetchData = async () => {
    try {
      const s = await adminApi.getServices({ page, page_size: pageSize });
      setServices(s.data.items);
      setTotal(s.data.total);
      setTotalPages(s.data.total_pages || 1);
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) {
        window.location.href = '/admin/login';
      } else setError('Ошибка загрузки');
    } finally {
      setLoading(false);
    }
    try {
      const b = await adminApi.getBundles();
      setBundles(b.data || []);
    } catch (err) {
      // Secondary list: services error above already surfaces failures.
      console.warn('[Services] bundles failed', err);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page]);

  const resetForm = () => {
    setName('');
    setDescription('');
    setDuration(30);
    setPrice(1000);
    setDiscount('');
    setDiscountUntil('');
    setCategory('');
    setCategoryCustom(false);
    setEditingId(null);
    setShowForm(false);
  };

  const showError = (err: unknown) => {
    setError(getApiErrorMessage(err, 'Ошибка сервера'));
  };

  const openCreateForm = () => {
    setName('');
    setDescription('');
    setDuration(30);
    setPrice(1000);
    setDiscount('');
    setDiscountUntil('');
    setCategory(lastCategory);
    // Stale memory (category was deleted meanwhile) → free input, not a lie.
    setCategoryCustom(
      lastCategory !== '' &&
        ![...new Set(services.map((s) => s.category).filter(Boolean))].includes(lastCategory),
    );
    setEditingId(null);
    setShowForm(true);
    setError('');
  };

  const parseDiscount = (): number | undefined => {
    if (discount.trim() === '') return undefined;
    const v = Math.round(Number(discount));
    if (!(v >= 0 && v <= 90)) {
      setError('Скидка — от 0 до 90%');
      return undefined;
    }
    return v;
  };

  const parseUntil = (raw: string): string | null | undefined => {
    // undefined = leave as is (create: none); null = clear on edit.
    if (raw.trim() === '') return null;
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) {
      setError('Некорректная дата окончания скидки');
      return undefined;
    }
    return d.toISOString();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const disc = parseDiscount();
    if (discount.trim() !== '' && disc === undefined) return;
    const until = parseUntil(discountUntil);
    if (discountUntil.trim() !== '' && until === undefined) return;
    const wantDiscount = disc !== undefined || discountUntil.trim() !== '';
    try {
      if (editingId) {
        await adminApi.updateService(editingId, {
          name,
          description,
          duration_minutes: duration,
          price,
          category: category || undefined,
          ...(disc !== undefined ? { discount_percent: disc } : {}),
          ...(discountUntil.trim() !== '' ? { discount_until: until as string } : {}),
        });
        toast.success('Услуга обновлена');
        if (category) setLastCategory(category);
      } else {
        await adminApi.createService({
          name,
          description,
          duration_minutes: duration,
          price,
          category: category || undefined,
          ...(disc !== undefined ? { discount_percent: disc } : {}),
          ...(wantDiscount && until ? { discount_until: until } : {}),
        });
        toast.success('Услуга создана');
        if (category) setLastCategory(category);
      }
      resetForm();
      fetchData();
    } catch (err: unknown) {
      showError(err);
    }
  };

  const handleEdit = (s: Service) => {
    setName(s.name);
    setDescription(s.description || '');
    setDuration(s.duration_minutes);
    setPrice(Number(s.price));
    setDiscount(s.discount_percent ? String(s.discount_percent) : '');
    setDiscountUntil(s.discount_until ? String(s.discount_until).slice(0, 16) : '');
    setCategory(s.category || '');
    // Category from another page (pagination) isn't in the visible list.
    setCategoryCustom(
      !!s.category &&
        ![...new Set(services.map((x) => x.category).filter(Boolean))].includes(s.category),
    );
    setEditingId(s.id);
    setShowForm(true);
    setError('');
  };

  const handleDelete = async (id: number) => {
    try {
      await adminApi.deleteService(id);
      toast.success('Услуга удалена');
      fetchData();
    } catch (err: unknown) {
      showError(err);
    } finally {
      setDeletingId(null);
    }
  };

  // ─── Bundle form ───
  const openBundleForm = async (b?: Bundle) => {
    setError('');
    try {
      const all = await adminApi.getServices({ page: 1, page_size: 500 });
      setAllServices(all.data.items || []);
    } catch (err: unknown) {
      showError(err);
      return;
    }
    if (b) {
      setEditingBundleId(b.id);
      setBundleName(b.name);
      setBundlePrice(b.price != null ? String(b.price) : '');
      setBundleTime(b.duration_override != null ? String(b.duration_override) : '');
      setBundleDiscount(b.discount_percent ? String(b.discount_percent) : '');
      setBundleDiscountUntil(b.discount_until ? String(b.discount_until).slice(0, 16) : '');
      setPicked(new Set(b.service_ids));
      const dm: Record<number, number> = {};
      for (const s of b.services) dm[s.id] = s.duration_minutes;
      setDurMap(dm);
    } else {
      setEditingBundleId(null);
      setBundleName('');
      setBundlePrice('');
      setBundleTime('');
      setBundleDiscount('');
      setBundleDiscountUntil('');
      setPicked(new Set());
      setDurMap({});
    }
    setShowBundleForm(true);
  };

  const pickedServices = allServices.filter((s) => picked.has(s.id));
  const effDur = (s: Service) => durMap[s.id] ?? s.duration_minutes ?? 0;
  const pickedDuration = pickedServices.reduce((t, s) => t + effDur(s), 0);
  const pickedSum = pickedServices.reduce((t, s) => t + Number(s.price || 0), 0);

  const togglePicked = (id: number) => {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleBundleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = bundleName.trim();
    if (!name) {
      setError('Введите название комплекса');
      return;
    }
    if (pickedServices.length < 2) {
      setError('Выберите минимум 2 услуги');
      return;
    }
    const price = bundlePrice.trim() === '' ? undefined : Number(bundlePrice);
    if (price !== undefined && !(price >= 0)) {
      setError('Некорректная цена');
      return;
    }
    const time = bundleTime.trim() === '' ? undefined : Math.round(Number(bundleTime));
    if (time !== undefined && !(time >= 5 && time <= 480)) {
      setError('Время комплекса — от 5 до 480 мин (или пусто = сумма)');
      return;
    }
    const disc = bundleDiscount.trim() === '' ? undefined : Math.round(Number(bundleDiscount));
    if (disc !== undefined && !(disc >= 0 && disc <= 90)) {
      setError('Скидка — от 0 до 90% (или пусто)');
      return;
    }
    const discUntil =
      bundleDiscountUntil.trim() === '' ? null : new Date(bundleDiscountUntil).toISOString();
    if (
      bundleDiscountUntil.trim() !== '' &&
      discUntil !== null &&
      Number.isNaN(Date.parse(discUntil))
    ) {
      setError('Некорректная дата окончания скидки');
      return;
    }
    // Per-service minutes (clamped); backend re-validates.
    const durations: Record<number, number> = {};
    for (const s of pickedServices) {
      const v = Math.round(Number(effDur(s)) || 0);
      durations[s.id] = Math.min(480, Math.max(5, v));
    }
    setError('');
    try {
      if (editingBundleId) {
        await adminApi.updateBundle(editingBundleId, {
          name,
          service_ids: [...picked],
          durations,
          price: bundlePrice.trim() === '' ? null : Number(bundlePrice),
          duration_override: bundleTime.trim() === '' ? null : Number(bundleTime),
          discount_percent: disc ?? null,
          discount_until: discUntil,
        });
        toast.success('Комплекс обновлён');
      } else {
        await adminApi.createBundle({
          name,
          service_ids: [...picked],
          durations,
          price,
          duration_override: time,
          discount_percent: disc,
          ...(discUntil ? { discount_until: discUntil } : {}),
        });
        toast.success('Комплекс собран');
      }
      setShowBundleForm(false);
      setEditingBundleId(null);
      fetchData();
    } catch (err: unknown) {
      showError(err);
    }
  };

  const handleBundleDelete = async (id: number) => {
    try {
      await adminApi.deleteBundle(id);
      toast.success('Комплекс удалён');
      fetchData();
    } catch (err: unknown) {
      showError(err);
    } finally {
      setDeletingBundleId(null);
    }
  };

  const toggleBundleActive = async (b: Bundle) => {
    try {
      await adminApi.updateBundle(b.id, { is_active: !b.is_active });
      toast.success(b.is_active ? 'Комплекс скрыт' : 'Комплекс активен');
      fetchData();
    } catch (err: unknown) {
      showError(err);
    }
  };

  // ─── Coupons ───
  const fetchCoupons = async () => {
    try {
      const { data } = await adminApi.getCoupons();
      setCoupons(data || []);
    } catch (err) {
      console.warn('[Services] coupons failed', err);
    }
  };

  useEffect(() => {
    fetchCoupons();
  }, []);

  const openCouponForm = async (prefillIds?: number[]) => {
    setCouponKind('percent');
    setCouponValue('');
    setCouponUses('1');
    setCouponUntil('');
    setCouponPicked(new Set(prefillIds ?? []));
    try {
      const { data } = await adminApi.getClients({ page: 1, page_size: 200 });
      setCouponClients(
        (data.items || []).map((c: { id: number; name: string; phone?: string }) => ({
          id: c.id,
          name: c.name,
          sub: c.phone || undefined,
        })),
      );
    } catch {
      setCouponClients([]);
    }
    setShowCouponForm(true);
  };

  // Deep jump from Clients ("выдать купон"): form opens pre-addressed.
  useEffect(() => {
    const state = location.state as { couponFor?: { id: number; name: string } } | null;
    if (state?.couponFor) {
      const target = state.couponFor;
      navigate(location.pathname, { replace: true });
      openCouponForm([target.id]);
      toast.success(`Купон для клиента: ${target.name}`);
      requestAnimationFrame(() => {
        document.getElementById('coupons-card')?.scrollIntoView({ behavior: 'smooth' });
      });
    }
  }, []);

  const handleCouponSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const value = Number(couponValue);
    if (!(value > 0)) {
      setError('Укажите размер купона');
      return;
    }
    if (couponKind === 'percent' && value > 90) {
      setError('Процент — максимум 90');
      return;
    }
    const uses = couponUses.trim() === '' ? undefined : Math.round(Number(couponUses));
    if (uses !== undefined && !(uses >= 1)) {
      setError('Число использований — от 1 (или пусто = без лимита)');
      return;
    }
    setError('');
    try {
      const { data } = await adminApi.createCoupon({
        kind: couponKind,
        value,
        ...(uses !== undefined ? { max_uses: uses } : {}),
        ...(couponPicked.size > 0 ? { user_ids: [...couponPicked] } : {}),
        ...(couponUntil.trim() !== '' ? { valid_until: new Date(couponUntil).toISOString() } : {}),
      });
      toast.success(`Купон ${data.code} выдан (колокол ушёл клиентам)`);
      setShowCouponForm(false);
      fetchCoupons();
    } catch (err: unknown) {
      showError(err);
    }
  };

  const handleCouponDelete = async (id: number) => {
    try {
      await adminApi.deleteCoupon(id);
      toast.success('Купон выключен');
      fetchCoupons();
    } catch (err: unknown) {
      showError(err);
    } finally {
      setDeletingCouponId(null);
    }
  };

  const columns: FitColumnDef<Service>[] = useMemo(
    () => [
      {
        id: 'name',
        header: 'Название',
        accessorFn: (s) => s.name,
        cell: ({ row }) => <strong>{row.original.name}</strong>,
        meta: { minWidth: 140, label: 'Название' },
      },
      {
        id: 'category',
        header: 'Категория',
        accessorFn: (s) => s.category || '—',
        cell: ({ row }) => row.original.category || '—',
        meta: { minWidth: 100, label: 'Категория' },
      },
      {
        id: 'desc',
        header: 'Описание',
        accessorFn: (s) => s.description || '—',
        cell: ({ row }) => row.original.description || '—',
        meta: { minWidth: 150, label: 'Описание' },
      },
      {
        id: 'duration',
        header: 'Длительность',
        accessorFn: (s) => s.duration_minutes,
        cell: ({ row }) => `${row.original.duration_minutes} мин`,
        meta: { minWidth: 90, maxWidth: 140, label: 'Длительность' },
      },
      {
        id: 'price',
        header: 'Цена',
        accessorFn: (s) => Number(s.effective_price ?? s.price) || 0,
        cell: ({ row }) => {
          const s = row.original;
          const eff = Number(s.effective_price ?? s.price);
          const tag = formatDiscountTag(s.discount_percent, s.discount_until);
          return (
            <span
              style={{ display: 'inline-flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}
            >
              <DiscountBadge
                pct={s.discount_percent}
                until={s.discount_until}
                onSave={async (pct, until) => {
                  await adminApi.updateService(s.id, {
                    discount_percent: pct ?? 0,
                    discount_until: until,
                  });
                  fetchData();
                }}
              />
              {s.discount_percent ? (
                <span style={{ whiteSpace: 'nowrap' }}>
                  <s style={{ color: '#999' }}>{formatPrice(s.price)} ₽</s>{' '}
                  <strong style={{ color: '#e5484d' }}>{formatPrice(eff)} ₽</strong>{' '}
                  <span title="Скидка">{tag}</span>
                </span>
              ) : (
                `${formatPrice(s.price)} ₽`
              )}
            </span>
          );
        },
        meta: { minWidth: 220, maxWidth: 320, label: 'Цена' },
      },
      {
        id: 'actions',
        header: 'Действия',
        cell: ({ row }) => {
          const s = row.original;
          return (
            <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
              <button
                className="btn btn-sm btn-edit"
                onClick={() => handleEdit(s)}
                title="Редактировать услугу"
                aria-label="Редактировать услугу"
              >
                ✏️
              </button>
              <button
                className="btn btn-sm btn-delete"
                onClick={() => setDeletingId(s.id)}
                title="Удалить услугу"
                aria-label="Удалить услугу"
              >
                ✖
              </button>
            </span>
          );
        },
        meta: { minWidth: 110, hideable: false, label: 'Действия' },
      },
    ],
    [],
  );

  if (loading)
    return (
      <div>
        <Skeleton rows={6} />
      </div>
    );
  if (error)
    return (
      <div>
        <div className="error-message">{error}</div>
      </div>
    );

  return (
    <div>
      <div className="page-header">
        <h1>Управление услугами</h1>
        <p>Добавление, редактирование и удаление услуг</p>
      </div>
      {error && <div className="error-message">{error}</div>}

      {showForm && (
        <div className="card form-card">
          <h3>{editingId ? 'Редактировать услугу' : 'Новая услуга'}</h3>
          <form onSubmit={handleSubmit}>
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label>Категория</label>
              {!categoryCustom && existingCategories.length > 0 ? (
                <div style={{ display: 'flex', gap: 8 }}>
                  <select
                    value={existingCategories.includes(category) ? category : ''}
                    onChange={(e) => {
                      if (e.target.value === '__new__') {
                        setCategoryCustom(true);
                        setCategory('');
                      } else {
                        setCategory(e.target.value);
                      }
                    }}
                    style={{ flex: 1 }}
                    autoFocus={!editingId}
                  >
                    <option value="" disabled>
                      Выберите из созданных…
                    </option>
                    {existingCategories.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                    <option value="__new__">＋ Новая категория…</option>
                  </select>
                </div>
              ) : (
                <>
                  <input
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    placeholder="Например: Ногти, Шугаринг, Ресницы"
                    autoFocus={!editingId}
                  />
                  {existingCategories.length > 0 && (
                    <button
                      type="button"
                      className="btn btn-sm btn-ghost"
                      style={{ marginTop: 6, alignSelf: 'flex-start' }}
                      onClick={() => {
                        setCategoryCustom(false);
                        setCategory(lastCategory);
                      }}
                    >
                      ← Выбрать из созданных
                    </button>
                  )}
                </>
              )}
              {!editingId && lastCategory && (
                <span style={{ fontSize: 12, color: '#666' }}>
                  Последняя: {lastCategory} — подставлена автоматически
                </span>
              )}
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Название</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="Шугаринг ног"
                />
              </div>
              <div className="form-group">
                <label>Длительность (мин)</label>
                <input
                  type="number"
                  value={duration}
                  onChange={(e) => setDuration(+e.target.value)}
                  required
                  min="5"
                />
              </div>
              <div className="form-group">
                <label>Цена (₽)</label>
                <input
                  type="number"
                  value={price}
                  onChange={(e) => setPrice(+e.target.value)}
                  required
                  min="0"
                />
              </div>
              <div className="form-group">
                <label>Скидка, % (пусто = нет)</label>
                <input
                  type="number"
                  value={discount}
                  onChange={(e) => setDiscount(e.target.value)}
                  placeholder="0–90"
                  min="0"
                  max="90"
                />
              </div>
              <div className="form-group">
                <label>Скидка до (пусто = бессрочно)</label>
                <input
                  type="datetime-local"
                  value={discountUntil}
                  onChange={(e) => setDiscountUntil(e.target.value)}
                />
              </div>
            </div>
            <div className="form-group">
              <label>Описание</label>
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Описание услуги"
              />
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary">
                {editingId ? 'Сохранить' : 'Создать'}
              </button>
              <button type="button" className="btn btn-ghost" onClick={resetForm}>
                Отмена
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <h3>Список услуг ({total})</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            {services.length > 0 && (
              <>
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    openBundleForm();
                    requestAnimationFrame(() => {
                      document
                        .getElementById('bundles-card')
                        ?.scrollIntoView?.({ behavior: 'smooth' });
                    });
                  }}
                >
                  ＋ Собрать комплекс
                </button>
                <button className="btn btn-primary" onClick={openCreateForm}>
                  + Добавить услугу
                </button>
              </>
            )}
          </div>
        </div>
        {services.length === 0 ? (
          <EmptyState title="Нет услуг" actionLabel="Добавить услугу" onAction={openCreateForm} />
        ) : (
          <DataTable tableId="services" columns={columns} data={services} />
        )}
      </div>

      <Pager
        page={page - 1}
        totalPages={totalPages}
        onChange={(p) => setPage(p + 1)}
        label={`Страница ${page} из ${totalPages} (${total} услуг)`}
      />

      {/* ─── Complexes: separate list, never mixed with services ─── */}
      <div className="card" id="bundles-card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <h3>🎁 Комплексы ({bundles.length})</h3>
        </div>
        <p className="hint" style={{ margin: '0 0 12px' }}>
          Набор из созданных услуг: записываются одним слотом, время суммируется.
        </p>
        {showBundleForm && (
          <div className="card form-card" style={{ marginBottom: 12 }}>
            <h3>{editingBundleId ? 'Редактировать комплекс' : 'Новый комплекс'}</h3>
            <form onSubmit={handleBundleSubmit}>
              <div className="form-row">
                <div className="form-group">
                  <label>Название</label>
                  <input
                    value={bundleName}
                    onChange={(e) => setBundleName(e.target.value)}
                    required
                    placeholder="Например: Бикини + ноги"
                    autoFocus={!editingBundleId}
                  />
                </div>
                <div className="form-group">
                  <label>Своя цена (₽, пусто = сумма)</label>
                  <input
                    type="number"
                    min={0}
                    value={bundlePrice}
                    onChange={(e) => setBundlePrice(e.target.value)}
                    placeholder={`Сумма: ${formatPrice(pickedSum)} ₽`}
                  />
                </div>
                <div className="form-group">
                  <label>Своё время, мин (пусто = сумма услуг)</label>
                  <input
                    type="number"
                    min={5}
                    max={480}
                    value={bundleTime}
                    onChange={(e) => setBundleTime(e.target.value)}
                    placeholder={`Сумма: ${pickedDuration} мин`}
                  />
                </div>
                <div className="form-group">
                  <label>Скидка, % (пусто = нет)</label>
                  <input
                    type="number"
                    min={0}
                    max={90}
                    value={bundleDiscount}
                    onChange={(e) => setBundleDiscount(e.target.value)}
                    placeholder="0–90"
                  />
                </div>
                <div className="form-group">
                  <label>Скидка до (пусто = бессрочно)</label>
                  <input
                    type="datetime-local"
                    value={bundleDiscountUntil}
                    onChange={(e) => setBundleDiscountUntil(e.target.value)}
                  />
                </div>
              </div>
              <div className="form-group">
                <label>Услуги в комплексе (минимум 2)</label>
                <div className="hint" style={{ marginBottom: 6 }}>
                  Отметьте услуги и задайте минуты каждой справа — время суммируется в итог ниже
                </div>
                <div className="bundle-pick-list">
                  {allServices.map((s) => (
                    <label key={s.id} className="bundle-pick">
                      <input
                        type="checkbox"
                        checked={picked.has(s.id)}
                        onChange={() => togglePicked(s.id)}
                      />
                      <span className="bundle-pick-name">
                        <strong>{s.name}</strong> · {s.duration_minutes} мин ·{' '}
                        {formatPrice(s.price)} ₽
                      </span>
                      <span
                        className="bundle-pick-mins"
                        title="Минут на услугу в комплексе (можно менять)"
                      >
                        <input
                          type="number"
                          min={5}
                          max={480}
                          value={effDur(s)}
                          disabled={!picked.has(s.id)}
                          aria-label={`Минут на услугу ${s.name} в комплексе`}
                          onChange={(e) =>
                            setDurMap((prev) => ({ ...prev, [s.id]: Number(e.target.value) }))
                          }
                          onClick={(e) => e.preventDefault()}
                        />
                        мин
                      </span>
                    </label>
                  ))}
                </div>
                <span style={{ fontSize: 12, color: '#666' }}>
                  Выбрано: {pickedServices.length} · ⏱ {pickedDuration} мин · Σ{' '}
                  {formatPrice(pickedSum)} ₽
                </span>
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary">
                  {editingBundleId ? 'Сохранить' : 'Собрать'}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setShowBundleForm(false)}
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        )}
        {bundles.length === 0 && !showBundleForm ? (
          <EmptyState
            title="Нет комплексов"
            actionLabel="Собрать комплекс"
            onAction={() => openBundleForm()}
          />
        ) : (
          <div className="bundle-list">
            {bundles.map((b) => (
              <div key={b.id} className={`bundle-card${b.is_active ? '' : ' bundle-off'}`}>
                <div className="bundle-head">
                  <strong>{b.name}</strong>
                  {!b.is_active && <span className="bundle-badge">скрыт</span>}
                </div>
                <div className="bundle-comp">
                  {b.services.map((s) => (
                    <span key={s.id} className="bundle-chip">
                      {s.name} · {s.duration_minutes} мин
                    </span>
                  ))}
                </div>
                <div className="bundle-totals">
                  <DiscountBadge
                    pct={b.discount_percent}
                    until={b.discount_until}
                    onSave={async (pct, until) => {
                      await adminApi.updateBundle(b.id, {
                        discount_percent: pct ?? null,
                        discount_until: until,
                      });
                      fetchData();
                    }}
                  />{' '}
                  ⏱ {b.duration_total} мин
                  {b.duration_override != null ? (
                    <span title="Задано вручную, а не суммой услуг"> (своё)</span>
                  ) : null}{' '}
                  {b.discount_percent ? (
                    <>
                      <s>{formatPrice(b.price != null ? b.price : b.price_total)} ₽</s>{' '}
                      <strong style={{ color: '#e5484d' }}>
                        {formatPrice(b.effective_price)} ₽
                      </strong>{' '}
                      <span title="Скидка комплекса">
                        {formatDiscountTag(b.discount_percent, b.discount_until)}
                      </span>
                    </>
                  ) : b.price != null ? (
                    <>
                      <s>{formatPrice(b.price_total)} ₽</s>{' '}
                      <strong>{formatPrice(b.effective_price)} ₽</strong>
                    </>
                  ) : (
                    <strong>{formatPrice(b.effective_price)} ₽</strong>
                  )}
                </div>
                <div className="bundle-actions">
                  <button
                    className="btn btn-sm btn-ghost"
                    onClick={() => toggleBundleActive(b)}
                    title={b.is_active ? 'Скрыть от клиентов' : 'Показать клиентам'}
                  >
                    {b.is_active ? '👁️' : '🚫'}
                  </button>
                  <button className="btn btn-sm btn-edit" onClick={() => openBundleForm(b)}>
                    ✏️
                  </button>
                  <button
                    className="btn btn-sm btn-delete"
                    onClick={() => setDeletingBundleId(b.id)}
                    title="Удалить комплекс"
                    aria-label="Удалить комплекс"
                  >
                    ✖
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ─── Coupons: personal codes to own clients ─── */}
      <div className="card" id="coupons-card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <h3>🎟 Купоны ({coupons.filter((c) => c.is_active).length})</h3>
          <button className="btn btn-primary" onClick={() => openCouponForm()}>
            + Выдать купон
          </button>
        </div>
        <p className="hint" style={{ margin: '0 0 12px' }}>
          Персональный код на −% или −₽ своим клиентам: код улетает им в колокольчик, клиент вводит
          его в поле «Промокод» при записи.
        </p>
        {showCouponForm && (
          <div className="card form-card" style={{ marginBottom: 12 }}>
            <h3>Новый купон</h3>
            <form onSubmit={handleCouponSubmit}>
              <div className="form-row">
                <div className="form-group">
                  <label>Вид</label>
                  <select value={couponKind} onChange={(e) => setCouponKind(e.target.value)}>
                    <option value="percent">−% от цены</option>
                    <option value="fixed">−₽ от цены</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>{couponKind === 'percent' ? 'Процент (1–90)' : 'Рублей'}</label>
                  <input
                    type="number"
                    min={1}
                    max={couponKind === 'percent' ? 90 : undefined}
                    value={couponValue}
                    onChange={(e) => setCouponValue(e.target.value)}
                    required
                    placeholder={couponKind === 'percent' ? '20' : '500'}
                  />
                </div>
                <div className="form-group">
                  <label>Использований (пусто = без лимита)</label>
                  <input
                    type="number"
                    min={1}
                    value={couponUses}
                    onChange={(e) => setCouponUses(e.target.value)}
                    placeholder="1"
                  />
                </div>
                <div className="form-group">
                  <label>Действует до (пусто = бессрочно)</label>
                  <input
                    type="datetime-local"
                    value={couponUntil}
                    onChange={(e) => setCouponUntil(e.target.value)}
                  />
                </div>
              </div>
              <div className="form-group">
                <label>Кому (пусто = всем своим клиентам)</label>
                <RecipientPicker
                  items={couponClients}
                  selected={couponPicked}
                  onChange={setCouponPicked}
                  placeholder="Имя клиента…"
                />
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn-primary">
                  Выдать + уведомить
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setShowCouponForm(false)}
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        )}
        {coupons.length === 0 ? (
          <EmptyState
            title="Купонов пока нет"
            description="Выдайте первый — код придёт клиентам в колокольчик"
          />
        ) : (
          <div className="bundle-list">
            {coupons.map((c) => (
              <div key={c.id} className={`bundle-card${c.is_active ? '' : ' bundle-off'}`}>
                <div className="bundle-head">
                  <strong>🎟 {c.code}</strong>
                  <span className="bundle-chip">
                    {c.kind === 'percent' ? `−${c.value}%` : `−${c.value} ₽`}
                  </span>
                  {!c.is_active && <span className="bundle-badge">выкл</span>}
                </div>
                <div className="bundle-comp">
                  <span className="bundle-chip">
                    {c.audience === 'selected'
                      ? `👥 ${c.user_ids.length} получател.`
                      : '👥 всем своим'}
                  </span>
                  <span className="bundle-chip">
                    Использовано: {c.used_count}
                    {c.max_uses ? ` из ${c.max_uses}` : ''}
                  </span>
                  {c.valid_until && (
                    <span className="bundle-chip">
                      до {new Date(c.valid_until).toLocaleString('ru-RU')}
                    </span>
                  )}
                </div>
                <div className="bundle-actions">
                  {c.is_active && (
                    <button
                      className="btn btn-sm btn-delete"
                      onClick={() => setDeletingCouponId(c.id)}
                      title="Выключить купон"
                    >
                      ✖
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deletingId}
        onClose={() => setDeletingId(null)}
        title="🗑 Удалить услугу?"
        message="Это действие нельзя отменить. Услуга будет скрыта из списка."
        confirmLabel="Удалить"
        danger
        onConfirm={() => deletingId !== null && handleDelete(deletingId)}
      />

      <ConfirmDialog
        open={deletingBundleId !== null}
        onClose={() => setDeletingBundleId(null)}
        title="🗑 Удалить комплекс?"
        message="Прошлые записи сохранят название комплекса."
        confirmLabel="Удалить"
        danger
        onConfirm={() => deletingBundleId !== null && handleBundleDelete(deletingBundleId)}
      />

      <ConfirmDialog
        open={deletingCouponId !== null}
        onClose={() => setDeletingCouponId(null)}
        title="Выключить купон?"
        message="Код перестанет работать. История использований сохранится."
        confirmLabel="Выключить"
        danger
        onConfirm={() => deletingCouponId !== null && handleCouponDelete(deletingCouponId)}
      />
    </div>
  );
}
export default ServicesPage;
