import type { InputHTMLAttributes } from 'react'

/** Max digits of a RU phone number: country digit + 10 (e.g. 79991234567). */
export const PHONE_MAX_DIGITS = 11

/**
 * Format-as-you-type Russian phone mask: +7 (___) ___-__-__.
 * Digit runs are capped at 11 — the field can never grow unbounded,
 * no matter what is pasted in.
 */
export function maskPhone(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, PHONE_MAX_DIGITS)
  if (digits.length === 0) return ''
  let rest = digits[0] === '8' || digits[0] === '7' ? digits.slice(1) : digits
  rest = rest.slice(0, 10)
  if (rest.length === 0) return '+7'
  if (rest.length <= 3) return `+7 (${rest}`
  let out = `+7 (${rest.slice(0, 3)}) ${rest.slice(3, 6)}`
  if (rest.length > 6) out += `-${rest.slice(6, 8)}`
  if (rest.length > 8) out += `-${rest.slice(8, 10)}`
  return out
}

/** A phone number is submittable only when all 11 digits are present. */
export function isCompletePhone(value: string): boolean {
  return value.replace(/\D/g, '').length === PHONE_MAX_DIGITS
}

interface PhoneInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value' | 'type'> {
  value: string
  onChange: (formatted: string) => void
}

/**
 * Single shared phone field for the whole app (masters, clients,
 * booking, registration). Controlled; always emits the masked value.
 */
export default function PhoneInput({ value, onChange, ...rest }: PhoneInputProps) {
  return (
    <input
      type="tel"
      inputMode="tel"
      autoComplete="tel"
      value={value}
      onChange={(e) => onChange(maskPhone(e.target.value))}
      {...rest}
    />
  )
}
