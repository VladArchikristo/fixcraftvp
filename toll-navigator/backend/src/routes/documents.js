const express = require('express');
const { spawn } = require('child_process');
const path = require('path');
const { verifyToken } = require('../middleware/auth');

const router = express.Router();

const DETECT_EDGES_SCRIPT = path.join(__dirname, '../../../scripts/detect_edges.py');

// POST /api/documents/ocr — извлечение текста из изображения документа
router.post('/ocr', verifyToken, async (req, res) => {
  try {
    const { image_base64 } = req.body;
    if (!image_base64) {
      return res.status(400).json({ error: 'image_base64 is required' });
    }

    const apiKey = process.env.GOOGLE_VISION_API_KEY;

    // Без ключа — возвращаем заглушку для разработки
    if (!apiKey) {
      console.log('[documents/ocr] No GOOGLE_VISION_API_KEY — returning mock');
      return res.json({
        text: 'BILL OF LADING\nShipper: ABC Freight Inc.\nConsignee: XYZ Logistics\nDate: 04/14/2026\nPRO#: 123456789\nWeight: 42,000 lbs\nPieces: 24\nOrigin: Dallas, TX\nDestination: New York, NY',
        word_count: 0,
        mock: true,
      });
    }

    // Google Vision API — полное текстовое распознавание документа
    const visionRes = await fetch(
      `https://vision.googleapis.com/v1/images:annotate?key=${apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requests: [{
            image: { content: image_base64 },
            features: [
              { type: 'DOCUMENT_TEXT_DETECTION', maxResults: 1 },
            ],
          }],
        }),
      }
    );

    if (!visionRes.ok) {
      const errText = await visionRes.text();
      console.error('[documents/ocr] Vision API error:', errText);
      return res.status(502).json({ error: 'Google Vision API error', details: errText });
    }

    const visionData = await visionRes.json();
    const fullText = visionData.responses?.[0]?.fullTextAnnotation?.text || '';
    const words = visionData.responses?.[0]?.fullTextAnnotation?.pages
      ?.flatMap(p => p.blocks)
      ?.flatMap(b => b.paragraphs)
      ?.flatMap(p => p.words)
      ?.length || 0;

    res.json({
      text: fullText,
      word_count: words,
      mock: false,
    });
  } catch (err) {
    console.error('POST /api/documents/ocr error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// POST /api/documents/detect-edges — авто-определение краёв документа
router.post('/detect-edges', verifyToken, async (req, res) => {
  try {
    const { image_base64 } = req.body;
    if (!image_base64) {
      return res.status(400).json({ error: 'image_base64 is required' });
    }

    const result = await runEdgeDetection(image_base64);
    res.json(result);
  } catch (err) {
    console.error('POST /api/documents/detect-edges error:', err);
    // На ошибку возвращаем дефолтные углы — приложение продолжает работать
    res.json({
      corners: defaultCorners(),
      detected: false,
      error: err.message,
    });
  }
});

// Запускаем Python скрипт для определения углов документа
function runEdgeDetection(image_base64) {
  return new Promise((resolve, reject) => {
    const python = spawn('python3', [DETECT_EDGES_SCRIPT]);

    let stdout = '';
    let stderr = '';

    python.stdout.on('data', data => { stdout += data.toString(); });
    python.stderr.on('data', data => { stderr += data.toString(); });

    python.on('close', code => {
      if (code !== 0) {
        console.error('[detect-edges] Python exit code:', code, stderr);
        return resolve({ corners: defaultCorners(), detected: false });
      }
      try {
        const result = JSON.parse(stdout.trim());
        resolve(result);
      } catch {
        console.error('[detect-edges] Invalid JSON from Python:', stdout);
        resolve({ corners: defaultCorners(), detected: false });
      }
    });

    python.on('error', err => {
      console.error('[detect-edges] Failed to start Python:', err);
      resolve({ corners: defaultCorners(), detected: false });
    });

    // Таймаут 10 секунд
    const timeout = setTimeout(() => {
      python.kill();
      resolve({ corners: defaultCorners(), detected: false, error: 'timeout' });
    }, 10000);

    python.on('close', () => clearTimeout(timeout));

    // Отправляем изображение в stdin
    python.stdin.write(JSON.stringify({ image_base64 }));
    python.stdin.end();
  });
}

function defaultCorners() {
  const m = 0.05;
  return [
    { x: m,     y: m },
    { x: 1 - m, y: m },
    { x: 1 - m, y: 1 - m },
    { x: m,     y: 1 - m },
  ];
}

module.exports = router;
