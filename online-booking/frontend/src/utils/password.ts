/** Mirror of backend `validate_password_strength` — keep in sync
 * (backend/app/utils/security.py). Returns the first violated rule as a
 * user-facing message, or null when the password satisfies the policy. */
const SPECIALS = /[!@#$%^&*()_+\-=[\]{}|;:,.<>?]/;

export function passwordError(password: string): string | null {
  if (password.length < 8) return 'Пароль должен содержать минимум 8 символов';
  if (!/[A-ZА-ЯЁ]/.test(password)) return 'Добавьте хотя бы одну заглавную букву';
  if (!/[a-zа-яё]/.test(password)) return 'Добавьте хотя бы одну строчную букву';
  if (!/\d/.test(password)) return 'Добавьте хотя бы одну цифру';
  if (!SPECIALS.test(password)) return 'Добавьте хотя бы один спецсимвол (!@#$…)';
  if (new Set(password).size < 4) return 'Пароль должен содержать минимум 4 разных символа';
  return null;
}
