import { useEffect, useState } from 'react'
import { servicesApi, appointmentsApi } from '../api/client'
import type { Service } from '../api/types'
import './BookingPage.css'

function BookingPage() {
  const [services, setServices] = useState<Service[]>([])
  const [selectedService, setSelectedService] = useState<Service | null>(null)
  const [selectedDate, setSelectedDate] = useState<string>('')
  const [clientName, setClientName] = useState('')
  const [clientPhone, setClientPhone] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchServices = async () => {
      try {
        const res = await servicesApi.getAll()
        setServices(res.data)
        if (res.data.length > 0) {
          setSelectedService(res.data[0])
        }
      } catch (err) {
        setError('Failed to load services')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchServices()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!selectedService || !selectedDate || !clientName || !clientPhone) {
      setError('Please fill all fields')
      return
    }

    try {
      setSubmitting(true)
      setError(null)

      const appointmentData = {
        master_id: 1,
        service_id: selectedService.id,
        client_name: clientName,
        client_phone: clientPhone,
        appointment_date: new Date(selectedDate).toISOString(),
      }

      await appointmentsApi.create(appointmentData)

      setSuccess(true)
      setClientName('')
      setClientPhone('')
      setSelectedDate('')
    } catch (err) {
      setError('Failed to book appointment')
      console.error(err)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div className="booking-page">Loading...</div>

  if (success) {
    return (
      <div className="booking-page">
        <div className="success-message card">
          <h2>✅ Спасибо за запись!</h2>
          <p>Ваша запись успешно создана.</p>
          <p>Мы свяжемся с вами в ближайшее время.</p>
          <button className="btn btn-primary" onClick={() => setSuccess(false)}>
            Новая запись
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="booking-page">
      <div className="container">
        <h1>Запись на процедуру</h1>

        <form onSubmit={handleSubmit} className="booking-form card">
          {error && <div className="error-message">{error}</div>}

          <fieldset>
            <legend>1. Выберите услугу</legend>
            <div className="services-list">
              {services.map((service) => (
                <label key={service.id} className="service-option">
                  <input
                    type="radio"
                    value={service.id}
                    checked={selectedService?.id === service.id}
                    onChange={() => setSelectedService(service)}
                  />
                  <span className="service-label">
                    <strong>{service.name}</strong>
                    <span className="service-details">
                      {service.duration_minutes} мин • ₽{service.price}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend>2. Выберите дату и время</legend>
            <input
              type="datetime-local"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="input"
              required
            />
          </fieldset>

          <fieldset>
            <legend>3. Ваши данные</legend>
            <input
              type="text"
              placeholder="Ваше имя"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              className="input"
              required
            />
            <input
              type="tel"
              placeholder="Ваш телефон"
              value={clientPhone}
              onChange={(e) => setClientPhone(e.target.value)}
              className="input"
              required
            />
          </fieldset>

          <button
            type="submit"
            className="btn btn-primary btn-submit"
            disabled={submitting}
          >
            {submitting ? 'Записываем...' : 'Записаться'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default BookingPage