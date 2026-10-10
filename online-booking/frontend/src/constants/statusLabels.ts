/** Shared human-readable labels (single copy - was triplicated across pages). */

export const statusLabels: Record<string, string> = {
  pending: '⏳ Ожидает',
  confirmed: '✅ Подтверждена',
  cancelled: '❌ Отменена',
  completed: '🏁 Завершена',
};

export const entityLabels: Record<string, string> = {
  appointment: '📅 Запись',
  service: '💇 Услуга',
  client: '👤 Клиент',
  working_hour: '🕐 Расписание',
  master: '👨‍💼 Мастер',
  auth: '🔑 Вход/выход',
};

export const actionLabels: Record<string, string> = {
  confirm: '✅ Подтверждение',
  cancel: '❌ Отмена',
  complete: '🏁 Завершение',
  delete: '🗑️ Удаление',
  create: '➕ Создание',
  update: '✏️ Обновление',
  toggle_active: '🔒 Блокировка',
  toggle_admin: '👑 Смена прав',
  'no-show': '⚠️ Неявка',
};

export const levelLabels: Record<string, string> = {
  info: 'ℹ️ INFO',
  warning: '⚠️ WARNING',
  error: '🚫 ERROR',
};
