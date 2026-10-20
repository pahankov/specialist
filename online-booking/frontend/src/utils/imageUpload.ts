/** Client-side preflight for avatar/certificate uploads.
 *
 *  iPhone Safari often reports HEIC/HEIF (or an empty MIME type) for a photo
 *  picked from the library. The backend decodes the actual bytes, so the
 *  browser check only needs to filter obvious non-images and the 15MB cap.
 */

export const MAX_IMAGE_BYTES = 15 * 1024 * 1024;

const IMAGE_TYPES = new Set([
  'image/jpeg',
  'image/jpg',
  'image/pjpeg',
  'image/png',
  'image/x-png',
  'image/webp',
  'image/heic',
  'image/heif',
  'image/heic-sequence',
  'image/heif-sequence',
]);

const IMAGE_EXTENSION = /\.(jpe?g|png|webp|hei[cf])$/i;

export function isSupportedImageFile(file: Pick<File, 'type' | 'name'>): boolean {
  const type = (file.type || '').trim().toLowerCase();
  if (type && type !== 'application/octet-stream' && type !== 'binary/octet-stream') {
    return IMAGE_TYPES.has(type);
  }
  // Some Android/iOS pickers send an empty or generic content type; trust
  // the extension in that case. The server still decodes and re-encodes it.
  return IMAGE_EXTENSION.test(file.name || '');
}

export function imageUploadError(file: Pick<File, 'type' | 'name' | 'size'>): string | null {
  if (!isSupportedImageFile(file)) {
    return 'Выберите фото в формате JPEG, PNG, WebP или HEIC';
  }
  if (file.size > MAX_IMAGE_BYTES) {
    return 'Файл больше 15 МБ';
  }
  return null;
}
