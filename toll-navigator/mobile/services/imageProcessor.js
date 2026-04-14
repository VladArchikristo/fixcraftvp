import * as ImageManipulator from 'expo-image-manipulator';

// A4 пропорции: 210x297mm → соотношение 1:1.414
const A4_RATIO = 297 / 210;

/**
 * Обработка фото для документа:
 * - Ресайз под A4 пропорции (макс ширина 1240px = 210mm при 150dpi)
 * - Повышение контраста через уровень компрессии (JPEG quality)
 * Возвращает { uri, width, height }
 */
export async function processDocumentImage(uri, options = {}) {
  const {
    maxWidth = 1240,
    quality = 0.92,
    grayscale = false,
  } = options;

  const targetHeight = Math.round(maxWidth * A4_RATIO);

  const actions = [
    { resize: { width: maxWidth, height: targetHeight } },
  ];

  const result = await ImageManipulator.manipulateAsync(
    uri,
    actions,
    {
      compress: quality,
      format: ImageManipulator.SaveFormat.JPEG,
      base64: true,
    }
  );

  return result;
}

/**
 * Быстрый ресайз без обрезки (для превью)
 */
export async function makeThumbnail(uri, size = 200) {
  const result = await ImageManipulator.manipulateAsync(
    uri,
    [{ resize: { width: size } }],
    { compress: 0.7, format: ImageManipulator.SaveFormat.JPEG }
  );
  return result.uri;
}
