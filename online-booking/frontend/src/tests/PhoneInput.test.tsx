import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PhoneInput, { maskPhone, isCompletePhone } from '../components/common/PhoneInput';

describe('maskPhone', () => {
  it('formats progressively as +7 (___) ___-__-__', () => {
    expect(maskPhone('9')).toBe('+7 (9');
    expect(maskPhone('999')).toBe('+7 (999');
    expect(maskPhone('9991234')).toBe('+7 (999) 123-4');
    expect(maskPhone('9991234567')).toBe('+7 (999) 123-45-67');
  });

  it('normalizes leading 8 to +7', () => {
    expect(maskPhone('89991234567')).toBe('+7 (999) 123-45-67');
  });

  it('caps digit runs at 11 — pasted garbage cannot grow the field', () => {
    expect(maskPhone('8'.padEnd(30, '8'))).toBe('+7 (888) 888-88-88');
    expect(maskPhone('+7 (999) 123-45-67').replace(/\D/g, '').length).toBe(11);
  });

  it('empty stays empty', () => {
    expect(maskPhone('')).toBe('');
    expect(maskPhone('abc')).toBe('');
  });
});

describe('isCompletePhone', () => {
  it('requires all 11 digits', () => {
    expect(isCompletePhone('+7 (999) 123-45-67')).toBe(true);
    expect(isCompletePhone('+7 (999) 123-45-6')).toBe(false);
    expect(isCompletePhone('')).toBe(false);
  });
});

describe('PhoneInput', () => {
  it('masks on change and caps length', () => {
    const onChange = vi.fn();
    render(<PhoneInput value="" onChange={onChange} aria-label="phone" />);
    fireEvent.change(screen.getByLabelText('phone'), {
      target: { value: '8999123456789999' },
    });
    expect(onChange).toHaveBeenCalledWith('+7 (999) 123-45-67');
  });
});
