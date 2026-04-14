const express = require('express');
const db = require('../db');
const { verifyToken } = require('../middleware/auth');

const router = express.Router();

const VALID_ISSUE_TYPES = ['late_payment', 'fraud', 'double_broker', 'low_rate', 'other'];

// GET /api/brokers — список с поиском и фильтрацией
router.get('/', verifyToken, (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = Math.min(parseInt(req.query.limit) || 20, 100);
    const offset = (page - 1) * limit;
    const search = req.query.search || null;
    const state = req.query.state || null;
    const minRating = req.query.min_rating ? parseFloat(req.query.min_rating) : null;

    const conditions = [];
    const params = [];

    if (search) {
      conditions.push('(b.name LIKE ? OR b.mc_number LIKE ? OR b.dot_number LIKE ?)');
      params.push(`%${search}%`, `%${search}%`, `%${search}%`);
    }
    if (state) {
      conditions.push('b.state = ?');
      params.push(state.toUpperCase());
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

    // Если есть фильтр по min_rating — нужна HAVING
    const havingClause = minRating !== null ? `HAVING COALESCE(AVG(br.rating), 0) >= ?` : '';

    const countSql = `
      SELECT COUNT(*) as cnt
      FROM brokers b
      ${whereClause}
    `;

    // При фильтре по рейтингу считаем с подзапросом
    let totalCount;
    if (minRating !== null) {
      const countWithRating = db.prepare(`
        SELECT COUNT(*) as cnt FROM (
          SELECT b.id
          FROM brokers b
          LEFT JOIN broker_reviews br ON br.broker_id = b.id
          ${whereClause}
          GROUP BY b.id
          HAVING COALESCE(AVG(br.rating), 0) >= ?
        )
      `).get(...params, parseFloat(minRating));
      totalCount = countWithRating.cnt;
    } else {
      totalCount = db.prepare(countSql).get(...params).cnt;
    }

    const brokers = db.prepare(`
      SELECT
        b.*,
        COALESCE(AVG(br.rating), 0) as avg_rating,
        COUNT(br.id) as review_count,
        MAX(br.created_at) as latest_review_date
      FROM brokers b
      LEFT JOIN broker_reviews br ON br.broker_id = b.id
      ${whereClause}
      GROUP BY b.id
      ${havingClause}
      ORDER BY review_count DESC, b.name ASC
      LIMIT ? OFFSET ?
    `).all(...params, ...(minRating !== null ? [parseFloat(minRating), limit, offset] : [limit, offset]));

    const result = brokers.map(b => ({
      ...b,
      avg_rating: parseFloat((b.avg_rating || 0).toFixed(2)),
      review_count: b.review_count || 0,
    }));

    res.json({
      brokers: result,
      total: totalCount,
      page,
      hasMore: offset + result.length < totalCount,
    });
  } catch (err) {
    console.error('GET /api/brokers error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// POST /api/brokers — создать брокера
router.post('/', verifyToken, (req, res) => {
  try {
    const { name, mc_number, dot_number, phone, email, city, state } = req.body;

    if (!name || !name.trim()) {
      return res.status(400).json({ error: 'name is required' });
    }

    const result = db.prepare(`
      INSERT INTO brokers (name, mc_number, dot_number, phone, email, city, state)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      name.trim(),
      mc_number || null,
      dot_number || null,
      phone || null,
      email || null,
      city || null,
      state ? state.toUpperCase() : null,
    );

    res.status(201).json({
      id: result.lastInsertRowid,
      name: name.trim(),
      message: 'Broker created',
    });
  } catch (err) {
    console.error('POST /api/brokers error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// GET /api/brokers/:id — детали + отзывы с пагинацией
router.get('/:id', verifyToken, (req, res) => {
  try {
    const brokerId = parseInt(req.params.id);
    if (isNaN(brokerId)) {
      return res.status(400).json({ error: 'Invalid broker id' });
    }

    const reviewsPage = parseInt(req.query.reviews_page) || 1;
    const reviewsLimit = 20;
    const reviewsOffset = (reviewsPage - 1) * reviewsLimit;

    const broker = db.prepare(`
      SELECT
        b.*,
        COALESCE(AVG(br.rating), 0) as avg_rating,
        COUNT(br.id) as review_count
      FROM brokers b
      LEFT JOIN broker_reviews br ON br.broker_id = b.id
      WHERE b.id = ?
      GROUP BY b.id
    `).get(brokerId);

    if (!broker) {
      return res.status(404).json({ error: 'Broker not found' });
    }

    // Распределение оценок по звёздам (1–5)
    const distRows = db.prepare(`
      SELECT rating, COUNT(*) as cnt
      FROM broker_reviews
      WHERE broker_id = ?
      GROUP BY rating
    `).all(brokerId);

    const rating_distribution = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    distRows.forEach(row => { rating_distribution[row.rating] = row.cnt; });

    // Отзывы с пагинацией и флагом can_delete
    const reviews = db.prepare(`
      SELECT
        br.id,
        br.rating,
        br.comment,
        br.issue_type,
        br.is_anonymous,
        br.created_at,
        br.user_id,
        CASE WHEN br.is_anonymous = 1 THEN NULL ELSE br.user_id END as display_user_id
      FROM broker_reviews br
      WHERE br.broker_id = ?
      ORDER BY br.created_at DESC
      LIMIT ? OFFSET ?
    `).all(brokerId, reviewsLimit, reviewsOffset);

    const reviewsWithDelete = reviews.map(r => ({
      id: r.id,
      rating: r.rating,
      comment: r.comment,
      issue_type: r.issue_type,
      is_anonymous: r.is_anonymous,
      created_at: r.created_at,
      user_id: r.display_user_id,
      can_delete: r.user_id === req.userId,
    }));

    const totalReviews = broker.review_count || 0;

    res.json({
      ...broker,
      avg_rating: parseFloat((broker.avg_rating || 0).toFixed(2)),
      review_count: totalReviews,
      rating_distribution,
      reviews: reviewsWithDelete,
      reviews_page: reviewsPage,
      reviews_has_more: reviewsOffset + reviewsWithDelete.length < totalReviews,
    });
  } catch (err) {
    console.error('GET /api/brokers/:id error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// PUT /api/brokers/:id — обновить данные брокера
router.put('/:id', verifyToken, (req, res) => {
  try {
    const brokerId = parseInt(req.params.id);
    if (isNaN(brokerId)) {
      return res.status(400).json({ error: 'Invalid broker id' });
    }

    const existing = db.prepare('SELECT id FROM brokers WHERE id = ?').get(brokerId);
    if (!existing) {
      return res.status(404).json({ error: 'Broker not found' });
    }

    const { name, mc_number, dot_number, phone, email, city, state } = req.body;

    if (name !== undefined && !name.trim()) {
      return res.status(400).json({ error: 'name cannot be empty' });
    }

    // Строим SET часть динамически — только переданные поля
    const updates = [];
    const params = [];

    if (name !== undefined) { updates.push('name = ?'); params.push(name.trim()); }
    if (mc_number !== undefined) { updates.push('mc_number = ?'); params.push(mc_number || null); }
    if (dot_number !== undefined) { updates.push('dot_number = ?'); params.push(dot_number || null); }
    if (phone !== undefined) { updates.push('phone = ?'); params.push(phone || null); }
    if (email !== undefined) { updates.push('email = ?'); params.push(email || null); }
    if (city !== undefined) { updates.push('city = ?'); params.push(city || null); }
    if (state !== undefined) { updates.push('state = ?'); params.push(state ? state.toUpperCase() : null); }

    if (updates.length === 0) {
      return res.status(400).json({ error: 'No fields to update' });
    }

    updates.push('updated_at = CURRENT_TIMESTAMP');
    params.push(brokerId);

    db.prepare(`UPDATE brokers SET ${updates.join(', ')} WHERE id = ?`).run(...params);

    res.json({ success: true, message: 'Broker updated' });
  } catch (err) {
    console.error('PUT /api/brokers/:id error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// POST /api/brokers/:id/reviews — добавить/обновить отзыв
router.post('/:id/reviews', verifyToken, (req, res) => {
  try {
    const brokerId = parseInt(req.params.id);
    if (isNaN(brokerId)) {
      return res.status(400).json({ error: 'Invalid broker id' });
    }

    const broker = db.prepare('SELECT id FROM brokers WHERE id = ?').get(brokerId);
    if (!broker) {
      return res.status(404).json({ error: 'Broker not found' });
    }

    const { rating, comment, issue_type, is_anonymous = false } = req.body;

    if (rating === undefined || rating === null) {
      return res.status(400).json({ error: 'rating is required' });
    }
    const ratingNum = parseInt(rating);
    if (isNaN(ratingNum) || ratingNum < 1 || ratingNum > 5) {
      return res.status(400).json({ error: 'rating must be between 1 and 5' });
    }
    if (comment && comment.length > 2000) {
      return res.status(400).json({ error: 'comment must be 2000 characters or less' });
    }
    if (issue_type && !VALID_ISSUE_TYPES.includes(issue_type)) {
      return res.status(400).json({ error: `issue_type must be one of: ${VALID_ISSUE_TYPES.join(', ')}` });
    }

    // Проверяем — есть ли уже отзыв от этого пользователя
    const existing = db.prepare(
      'SELECT id FROM broker_reviews WHERE broker_id = ? AND user_id = ?'
    ).get(brokerId, req.userId);

    let reviewId;
    if (existing) {
      // Обновляем существующий
      db.prepare(`
        UPDATE broker_reviews
        SET rating = ?, comment = ?, issue_type = ?, is_anonymous = ?
        WHERE id = ?
      `).run(ratingNum, comment || null, issue_type || null, is_anonymous ? 1 : 0, existing.id);
      reviewId = existing.id;

      return res.json({ id: reviewId, updated: true, message: 'Review updated' });
    } else {
      // Создаём новый
      const result = db.prepare(`
        INSERT INTO broker_reviews (broker_id, user_id, rating, comment, issue_type, is_anonymous)
        VALUES (?, ?, ?, ?, ?, ?)
      `).run(brokerId, req.userId, ratingNum, comment || null, issue_type || null, is_anonymous ? 1 : 0);
      reviewId = result.lastInsertRowid;

      return res.status(201).json({ id: reviewId, updated: false, message: 'Review added' });
    }
  } catch (err) {
    console.error('POST /api/brokers/:id/reviews error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// PUT /api/brokers/:id/reviews/:reviewId — редактировать свой отзыв
router.put('/:id/reviews/:reviewId', verifyToken, (req, res) => {
  try {
    const brokerId = parseInt(req.params.id);
    const reviewId = parseInt(req.params.reviewId);
    if (isNaN(brokerId) || isNaN(reviewId)) {
      return res.status(400).json({ error: 'Invalid id' });
    }

    const review = db.prepare(
      'SELECT id FROM broker_reviews WHERE id = ? AND broker_id = ? AND user_id = ?'
    ).get(reviewId, brokerId, req.userId);

    if (!review) {
      return res.status(404).json({ error: 'Review not found or not yours' });
    }

    const { rating, comment, issue_type, is_anonymous } = req.body;

    const updates = [];
    const params = [];

    if (rating !== undefined) {
      const ratingNum = parseInt(rating);
      if (isNaN(ratingNum) || ratingNum < 1 || ratingNum > 5) {
        return res.status(400).json({ error: 'rating must be between 1 and 5' });
      }
      updates.push('rating = ?'); params.push(ratingNum);
    }
    if (comment !== undefined) {
      if (comment && comment.length > 2000) {
        return res.status(400).json({ error: 'comment must be 2000 characters or less' });
      }
      updates.push('comment = ?'); params.push(comment || null);
    }
    if (issue_type !== undefined) {
      if (issue_type && !VALID_ISSUE_TYPES.includes(issue_type)) {
        return res.status(400).json({ error: `issue_type must be one of: ${VALID_ISSUE_TYPES.join(', ')}` });
      }
      updates.push('issue_type = ?'); params.push(issue_type || null);
    }
    if (is_anonymous !== undefined) {
      updates.push('is_anonymous = ?'); params.push(is_anonymous ? 1 : 0);
    }

    if (updates.length === 0) {
      return res.status(400).json({ error: 'No fields to update' });
    }

    params.push(reviewId);
    db.prepare(`UPDATE broker_reviews SET ${updates.join(', ')} WHERE id = ?`).run(...params);

    res.json({ success: true, message: 'Review updated' });
  } catch (err) {
    console.error('PUT /api/brokers/:id/reviews/:reviewId error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

// DELETE /api/brokers/:id/reviews/:reviewId — удалить свой отзыв
router.delete('/:id/reviews/:reviewId', verifyToken, (req, res) => {
  try {
    const brokerId = parseInt(req.params.id);
    const reviewId = parseInt(req.params.reviewId);
    if (isNaN(brokerId) || isNaN(reviewId)) {
      return res.status(400).json({ error: 'Invalid id' });
    }

    const review = db.prepare(
      'SELECT id FROM broker_reviews WHERE id = ? AND broker_id = ? AND user_id = ?'
    ).get(reviewId, brokerId, req.userId);

    if (!review) {
      return res.status(404).json({ error: 'Review not found or not yours' });
    }

    db.prepare('DELETE FROM broker_reviews WHERE id = ?').run(reviewId);

    res.json({ success: true, message: 'Review deleted' });
  } catch (err) {
    console.error('DELETE /api/brokers/:id/reviews/:reviewId error:', err);
    res.status(500).json({ error: 'Server error' });
  }
});

module.exports = router;
