import * as ImageManipulator from 'expo-image-manipulator';

// A4 proportions: 210x297mm -> ratio 1:1.414
const A4_RATIO = 297 / 210;

/**
 * Process photo for document:
 * - Resize to A4 proportions (max width 1240px = 210mm at 150dpi)
 * - Enhance contrast via compression level (JPEG quality)
 * Returns { uri, width, height }
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
 * Quick resize without cropping (for thumbnails)
 */
export async function makeThumbnail(uri, size = 200) {
  const result = await ImageManipulator.manipulateAsync(
    uri,
    [{ resize: { width: size } }],
    { compress: 0.7, format: ImageManipulator.SaveFormat.JPEG }
  );
  return result.uri;
}
