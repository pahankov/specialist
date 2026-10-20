import { describe, expect, it } from 'vitest';
import { MAX_IMAGE_BYTES, imageUploadError, isSupportedImageFile } from '../utils/imageUpload';

function file(name: string, type: string, size = 1024) {
  return { name, type, size };
}

describe('image upload preflight', () => {
  it('accepts iPhone HEIC/HEIF photos', () => {
    expect(isSupportedImageFile(file('IMG_0001.HEIC', 'image/heic'))).toBe(true);
    expect(isSupportedImageFile(file('IMG_0002.heif', 'image/heif'))).toBe(true);
    expect(imageUploadError(file('IMG_0001.HEIC', 'image/heic'))).toBeNull();
  });

  it('uses the extension when a phone picker sends an empty MIME type', () => {
    expect(isSupportedImageFile(file('photo.HEIC', ''))).toBe(true);
    expect(isSupportedImageFile(file('photo.jpg', 'application/octet-stream'))).toBe(true);
    expect(isSupportedImageFile(file('notes.txt', ''))).toBe(false);
  });

  it('accepts regular formats and rejects unsupported files', () => {
    expect(isSupportedImageFile(file('a.jpg', 'image/jpeg'))).toBe(true);
    expect(isSupportedImageFile(file('a.png', 'image/png'))).toBe(true);
    expect(isSupportedImageFile(file('a.webp', 'image/webp'))).toBe(true);
    expect(isSupportedImageFile(file('a.svg', 'image/svg+xml'))).toBe(false);
    expect(isSupportedImageFile(file('a.pdf', 'application/pdf'))).toBe(false);
  });

  it('enforces the 15MB backend limit', () => {
    expect(imageUploadError(file('big.jpg', 'image/jpeg', MAX_IMAGE_BYTES))).toBeNull();
    expect(imageUploadError(file('big.jpg', 'image/jpeg', MAX_IMAGE_BYTES + 1))).toBe(
      'Файл больше 15 МБ',
    );
  });
});
