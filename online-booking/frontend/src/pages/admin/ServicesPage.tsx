import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { adminApi } from '../../api/client';
import { ConfirmDialog, DataTable, Skeleton, EmptyState, Pager } from '../../components/common';
import type { FitColumnDef } from '../../components/common';
import { usePersistentState } from '../../utils/persistentState';
import type { Service } from '../../api/types';
import type { Bundle } from '../../api/cabinet';
import { formatPrice } from '../../components/schedule/helpers';
import { getApiErrorMessage, getApiErrorStatus } from '../../utils/apiError';
import '../../styles/tables.css';
import './ServicesPage.css';

function ServicesPage() {
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
  const [picked, setPicked] = useState<Set<number>>(new Set());
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      if (editingId) {
        await adminApi.updateService(editingId, {
          name,
          description,
          duration_minutes: duration,
          price,
          category: category || undefined,
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
      setPicked(new Set(b.service_ids));
      const dm: Record<number, number> = {};
      for (const s of b.services) dm[s.id] = s.duration_minutes;
      setDurMap(dm);
    } else {
      setEditingBundleId(null);
      setBundleName('');
      setBundlePrice('');
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
    if (picked.size < 2) {
      setError('Выберите минимум 2 услуги');
      return;
    }
    const price = bundlePrice.trim() === '' ? undefined : Number(bundlePrice);
    if (price !== undefined && !(price >= 0)) {
      setError('Некорректная цена');
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
        });
        toast.success('Комплекс обновлён');
      } else {
        await adminApi.createBundle({ name, service_ids: [...picked], durations, price });
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
        accessorFn: (s) => Number(s.price) || 0,
        cell: ({ row }) => `${formatPrice(row.original.price)} ₽`,
        meta: { minWidth: 80, maxWidth: 140, label: 'Цена' },
      },
      {
        id: 'actions',
        header: 'Действия',
        cell: ({ row }) => {
          const s = row.original;
          return (
            <span style={{ display: 'inline-flex', gap: 4 }}>
              <button className="btn btn-sm btn-edit" onClick={() => handleEdit(s)}>
                ✏️ Редактировать
              </button>
              <button className="btn btn-sm btn-delete" onClick={() => setDeletingId(s.id)}>
                🗑️ Удалить
              </button>
            </span>
          );
        },
        meta: { minWidth: 200, hideable: false, label: 'Действия' },
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
              </div>
              <div className="form-group">
                <label>Услуги в комплексе (минимум 2)</label>
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
                      {picked.has(s.id) && (
                        <span className="bundle-pick-mins">
                          <input
                            type="number"
                            min={5}
                            max={480}
                            value={effDur(s)}
                            aria-label={`Минут на услугу ${s.name} в комплексе`}
                            onChange={(e) =>
                              setDurMap((prev) => ({ ...prev, [s.id]: Number(e.target.value) }))
                            }
                            onClick={(e) => e.preventDefault()}
                          />
                          мин
                        </span>
                      )}
                    </label>
                  ))}
                </div>
                <span style={{ fontSize: 12, color: '#666' }}>
                  Выбрано: {picked.size} · ⏱ {pickedDuration} мин · Σ {formatPrice(pickedSum)} ₽
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
                  ⏱ {b.duration_total} мин ·{' '}
                  {b.price != null ? (
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
                  >
                    🗑️
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deletingId}
        onClose={() => setDeletingId(null)}
        title="🗑️ Удалить услугу?"
        message="Это действие нельзя отменить. Услуга будет скрыта из списка."
        confirmLabel="Удалить"
        danger
        onConfirm={() => deletingId !== null && handleDelete(deletingId)}
      />

      <ConfirmDialog
        open={deletingBundleId !== null}
        onClose={() => setDeletingBundleId(null)}
        title="🗑️ Удалить комплекс?"
        message="Прошлые записи сохранят название комплекса."
        confirmLabel="Удалить"
        danger
        onConfirm={() => deletingBundleId !== null && handleBundleDelete(deletingBundleId)}
      />
    </div>
  );
}
export default ServicesPage;
