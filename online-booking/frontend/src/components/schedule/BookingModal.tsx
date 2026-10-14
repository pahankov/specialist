import { useEffect, useState } from 'react';
import type { Client, Service } from '../../api/types';
import type { Bundle } from '../../api/cabinet';
import { getFilteredClients, getFilteredServices, formatPrice, formatHour } from './helpers';
import Modal from '../common/Modal';
import './ScheduleComponents.css';

interface BookingModalProps {
  open: boolean;
  date: Date | null;
  hour: number | null;
  clientId: number | null;
  serviceId: number | null;
  bundleId: number | null;
  status: 'pending' | 'confirmed';
  notes: string;
  clients: Client[];
  services: Service[];
  bundles: Bundle[];
  bookingLoading: boolean;
  onClose: () => void;
  onUpdate: (field: string, value: any) => void;
  onBook: () => void;
  /** MasterProfile.id to scope the services list (superadmin booking for a master) */
  servicesMasterId?: number | '';
}

export function BookingModal({
  open,
  date,
  hour,
  clientId,
  serviceId,
  bundleId,
  status,
  notes,
  clients,
  services,
  bundles,
  bookingLoading,
  onClose,
  onUpdate,
  onBook,
  servicesMasterId,
}: BookingModalProps) {
  const [clientSearch, setClientSearch] = useState('');
  const [serviceSearch, setServiceSearch] = useState('');
  const [showClientDropdown, setShowClientDropdown] = useState(false);
  const [showServiceDropdown, setShowServiceDropdown] = useState(false);

  // Fresh state on every open: stale search text/selection must never leak
  // into the next booking (e.g. second client on the same day).
  useEffect(() => {
    if (open) {
      setClientSearch('');
      setServiceSearch('');
      setShowClientDropdown(false);
      setShowServiceDropdown(false);
    }
  }, [open]);

  // Scope services to the booking target master (superadmin sees all otherwise)
  const scopedServices =
    servicesMasterId !== '' && servicesMasterId != null
      ? services.filter((s) => s.master_id === servicesMasterId)
      : services;
  const scopedBundles = bundles.filter((b) => b.is_active !== false);
  const filteredClients = getFilteredClients(clients, clientSearch);
  const filteredServices = getFilteredServices(scopedServices, serviceSearch);
  const filteredBundles = scopedBundles.filter((b) =>
    serviceSearch.trim() === ''
      ? true
      : b.name.toLowerCase().includes(serviceSearch.trim().toLowerCase()),
  );
  const selectedClient = clients.find((c) => c.id === clientId);
  const selectedService = scopedServices.find((s) => s.id === serviceId);
  const selectedBundle = scopedBundles.find((b) => b.id === bundleId);

  const clearClient = () => {
    onUpdate('clientId', null);
    setClientSearch('');
    setShowClientDropdown(false);
  };
  const clearService = () => {
    onUpdate('serviceId', null);
    onUpdate('bundleId', null);
    setServiceSearch('');
    setShowServiceDropdown(false);
  };

  return (
    <Modal open={open} onClose={onClose} title="📅 Записать клиента" wide>
      <p className="booking-modal-date">
        {date?.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })} в{' '}
        {formatHour(hour!)}
      </p>

      <div className="form-group">
        <label>Клиент</label>
        <div style={{ position: 'relative' }}>
          <input
            type="text"
            value={selectedClient?.name || clientSearch}
            onChange={(e) => {
              setClientSearch(e.target.value);
              setShowClientDropdown(true);
            }}
            onFocus={() => {
              if (!selectedClient) setShowClientDropdown(true);
            }}
            placeholder="Начните вводить имя или телефон..."
            className="form-input"
            style={{ paddingRight: 34 }}
          />
          {(selectedClient || clientSearch) && (
            <button
              type="button"
              className="input-clear"
              onClick={clearClient}
              title="Очистить выбор"
              aria-label="Очистить клиента"
            >
              ✕
            </button>
          )}
          {showClientDropdown && (
            <div className="dropdown-list">
              {filteredClients.length === 0 ? (
                <div className="dropdown-empty">Ничего не найдено</div>
              ) : (
                filteredClients.map((c) => (
                  <div
                    key={c.id}
                    className={`dropdown-item ${clientId === c.id ? 'selected' : ''}`}
                    onClick={() => {
                      onUpdate('clientId', c.id);
                      setShowClientDropdown(false);
                      setClientSearch('');
                    }}
                  >
                    <strong>{c.name}</strong> — {c.phone}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
        {!selectedClient && (
          <div className="field-hint">
            Выберите клиента из списка — кнопка записи активна только после выбора
          </div>
        )}
      </div>

      <div className="form-group">
        <label>Услуга или комплекс</label>
        <div style={{ position: 'relative' }}>
          <input
            type="text"
            value={selectedBundle?.name || selectedService?.name || serviceSearch}
            onChange={(e) => {
              setServiceSearch(e.target.value);
              setShowServiceDropdown(true);
            }}
            onFocus={() => {
              if (!selectedService && !selectedBundle) setShowServiceDropdown(true);
            }}
            placeholder="Начните вводить название..."
            className="form-input"
            style={{ paddingRight: 34 }}
          />
          {(selectedService || selectedBundle || serviceSearch) && (
            <button
              type="button"
              className="input-clear"
              onClick={clearService}
              title="Очистить выбор"
              aria-label="Очистить услугу"
            >
              ✕
            </button>
          )}
          {showServiceDropdown && (
            <div className="dropdown-list">
              {filteredBundles.length === 0 && filteredServices.length === 0 ? (
                <div className="dropdown-empty">Ничего не найдено</div>
              ) : (
                <>
                  {filteredBundles.map((b) => (
                    <div
                      key={`bundle-${b.id}`}
                      className={`dropdown-item ${bundleId === b.id ? 'selected' : ''}`}
                      onClick={() => {
                        onUpdate('bundleId', b.id);
                        onUpdate('serviceId', null);
                        setShowServiceDropdown(false);
                        setServiceSearch('');
                      }}
                    >
                      <strong>🎁 {b.name}</strong> — {b.duration_total} мин,{' '}
                      {formatPrice(b.effective_price)} ₽
                    </div>
                  ))}
                  {filteredServices.map((s) => (
                    <div
                      key={s.id}
                      className={`dropdown-item ${serviceId === s.id ? 'selected' : ''}`}
                      onClick={() => {
                        onUpdate('serviceId', s.id);
                        onUpdate('bundleId', null);
                        setShowServiceDropdown(false);
                        setServiceSearch('');
                      }}
                    >
                      <strong>{s.name}</strong> — {s.duration_minutes} мин, {formatPrice(s.price)} ₽
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
        {!selectedService && !selectedBundle && (
          <div className="field-hint">
            Выберите услугу или комплекс из списка — кнопка записи активна только после выбора
          </div>
        )}
        {scopedServices.length === 0 && (
          <div className="field-hint">
            У мастера пока нет услуг — добавьте их в разделе «Услуги», иначе записать некого
          </div>
        )}
        {selectedBundle && hour !== null && (
          <div className="field-hint">
            {(() => {
              const dur = selectedBundle.duration_total || 60;
              const endH = hour + Math.floor(dur / 60);
              const endM = dur % 60;
              const end = `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;
              return `Займёт гранулы ${formatHour(hour)}–${end}`;
            })()}
          </div>
        )}
        {selectedService && hour !== null && (
          <div className="field-hint">
            {(() => {
              const span = Math.max(
                1,
                Math.ceil((Number(selectedService.duration_minutes) || 60) / 60),
              );
              const endH = hour + Math.floor((Number(selectedService.duration_minutes) || 60) / 60);
              const endM = (Number(selectedService.duration_minutes) || 60) % 60;
              const end = `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;
              return `Займёт гранулы ${formatHour(hour)}–${end}${span > 1 ? ` (${span} шт.) — соседние тоже станут заняты` : ''}`;
            })()}
          </div>
        )}
      </div>

      <div className="form-group">
        <label>Статус</label>
        <select
          value={status}
          onChange={(e) => onUpdate('status', e.target.value)}
          className="form-input"
        >
          <option value="pending">⏳ Ожидает</option>
          <option value="confirmed">✅ Подтверждена</option>
        </select>
      </div>

      <div className="form-group">
        <label>Примечания</label>
        <textarea
          value={notes}
          onChange={(e) => onUpdate('notes', e.target.value.slice(0, 140))}
          placeholder="Доп. информация..."
          rows={2}
          className="form-input"
          maxLength={140}
        />
        <span className="hint">{notes.length}/140</span>
      </div>

      <div className="modal-actions">
        <button className="btn btn-ghost" onClick={onClose}>
          Отмена
        </button>
        <button
          className="btn btn-primary"
          onClick={onBook}
          disabled={!clientId || (!serviceId && !bundleId) || bookingLoading}
        >
          {bookingLoading ? 'Запись...' : 'Записать'}
        </button>
      </div>
    </Modal>
  );
}
