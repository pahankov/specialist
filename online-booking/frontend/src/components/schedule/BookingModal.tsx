import { useState } from 'react'
import type { Client, Service } from '../../api/types'
import { getFilteredClients, getFilteredServices, formatPrice, formatHour } from './helpers'
import Modal from '../common/Modal'
import './ScheduleComponents.css'

interface BookingModalProps {
  open: boolean
  date: Date | null
  hour: number | null
  clientId: number | null
  serviceId: number | null
  status: 'pending' | 'confirmed'
  notes: string
  clients: Client[]
  services: Service[]
  bookingLoading: boolean
  onClose: () => void
  onUpdate: (field: string, value: any) => void
  onBook: () => void
  /** MasterProfile.id to scope the services list (superadmin booking for a master) */
  servicesMasterId?: number | ''
}

export function BookingModal({
  open,
  date,
  hour,
  clientId,
  serviceId,
  status,
  notes,
  clients,
  services,
  bookingLoading,
  onClose,
  onUpdate,
  onBook,
  servicesMasterId,
}: BookingModalProps) {
  const [clientSearch, setClientSearch] = useState('')
  const [serviceSearch, setServiceSearch] = useState('')
  const [showClientDropdown, setShowClientDropdown] = useState(false)
  const [showServiceDropdown, setShowServiceDropdown] = useState(false)

  // Scope services to the booking target master (superadmin sees all otherwise)
  const scopedServices = servicesMasterId !== '' && servicesMasterId != null
    ? services.filter(s => s.master_id === servicesMasterId)
    : services
  const filteredClients = getFilteredClients(clients, clientSearch)
  const filteredServices = getFilteredServices(scopedServices, serviceSearch)
  const selectedClient = clients.find(c => c.id === clientId)
  const selectedService = scopedServices.find(s => s.id === serviceId)

  const clearClient = () => { onUpdate('clientId', null); setClientSearch(''); setShowClientDropdown(false) }
  const clearService = () => { onUpdate('serviceId', null); setServiceSearch(''); setShowServiceDropdown(false) }

  return (
    <Modal open={open} onClose={onClose} title="📅 Записать клиента" wide>
        <p className="booking-modal-date">
          {date?.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })} в {formatHour(hour!)}
        </p>

        <div className="form-group">
          <label>Клиент</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <input
                type="text"
                value={selectedClient?.name || clientSearch}
                onChange={(e) => { setClientSearch(e.target.value); setShowClientDropdown(true) }}
                onFocus={() => { if (!selectedClient) setShowClientDropdown(true) }}
                placeholder="Начните вводить имя или телефон..."
                className="form-input"
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
              {showClientDropdown && (
                <div className="dropdown-list">
                  {filteredClients.length === 0 ? (
                    <div className="dropdown-empty">Ничего не найдено</div>
                  ) : (
                    filteredClients.map(c => (
                      <div
                        key={c.id}
                        className={`dropdown-item ${clientId === c.id ? 'selected' : ''}`}
                        onClick={() => { onUpdate('clientId', c.id); setShowClientDropdown(false); setClientSearch('') }}
                      >
                        <strong>{c.name}</strong> — {c.phone}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
            {(selectedClient || clientSearch) && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={clearClient} title="Очистить выбор" aria-label="Очистить клиента">✕</button>
            )}
          </div>
          {!selectedClient && (
            <div className="field-hint">Выберите клиента из списка — кнопка записи активна только после выбора</div>
          )}
        </div>

        <div className="form-group">
          <label>Услуга</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <input
                type="text"
                value={selectedService?.name || serviceSearch}
                onChange={(e) => { setServiceSearch(e.target.value); setShowServiceDropdown(true) }}
                onFocus={() => { if (!selectedService) setShowServiceDropdown(true) }}
                placeholder="Начните вводить название..."
                className="form-input"
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
              {showServiceDropdown && (
                <div className="dropdown-list">
                  {filteredServices.length === 0 ? (
                    <div className="dropdown-empty">Ничего не найдено</div>
                  ) : (
                    filteredServices.map(s => (
                      <div
                        key={s.id}
                        className={`dropdown-item ${serviceId === s.id ? 'selected' : ''}`}
                        onClick={() => { onUpdate('serviceId', s.id); setShowServiceDropdown(false); setServiceSearch('') }}
                      >
                        <strong>{s.name}</strong> — {s.duration_minutes} мин, {formatPrice(s.price)} ₽
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
            {(selectedService || serviceSearch) && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={clearService} title="Очистить выбор" aria-label="Очистить услугу">✕</button>
            )}
          </div>
          {!selectedService && (
            <div className="field-hint">Выберите услугу из списка — кнопка записи активна только после выбора</div>
          )}
          {scopedServices.length === 0 && (
            <div className="field-hint">У мастера пока нет услуг — добавьте их в разделе «Услуги», иначе записать некого</div>
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
            onChange={(e) => onUpdate('notes', e.target.value)}
            placeholder="Доп. информация..."
            rows={2}
            className="form-input"
          />
        </div>

        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
          <button
            className="btn btn-primary"
            onClick={onBook}
            disabled={!clientId || !serviceId || bookingLoading}
          >
            {bookingLoading ? 'Запись...' : 'Записать'}
          </button>
        </div>
    </Modal>
  )
}
