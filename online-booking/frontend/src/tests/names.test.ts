import { describe, it, expect } from 'vitest';
import { capitalizeWords, splitFullName } from '../utils/names';

describe('names', () => {
  describe('capitalizeWords', () => {
    it('capitalizes the first letter', () => {
      expect(capitalizeWords('иван')).toBe('Иван');
    });

    it('capitalizes every word and hyphenated parts', () => {
      expect(capitalizeWords('анна-мария петрова')).toBe('Анна-Мария Петрова');
    });

    it('keeps already-capitalized text and latin', () => {
      expect(capitalizeWords('John doe')).toBe('John Doe');
    });

    it('leaves empty string alone', () => {
      expect(capitalizeWords('')).toBe('');
    });
  });

  describe('splitFullName', () => {
    it('splits first token from the rest', () => {
      expect(splitFullName('Иван Петров Сидоров')).toEqual(['Иван', 'Петров Сидоров']);
    });

    it('single word has no rest', () => {
      expect(splitFullName('Иван')).toEqual(['Иван', '']);
    });
  });
});
