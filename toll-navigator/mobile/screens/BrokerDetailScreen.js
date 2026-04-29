import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Alert, Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { getBrokerDetail, deleteBrokerReview } from '../services/brokers';
import { COLORS, FONTS, SPACING, RADIUS, SHARED } from '../theme';

const ISSUE_TYPE_MAP = {
  late_payment:  { label: 'Late Payment', emoji: '🕐', color: '#ffb74d' },
  fraud:         { label: 'Fraud',   emoji: '⚠️', color: '#ef9a9a' },
  double_broker: { label: 'Double Broker',  emoji: '🔄', color: '#ce93d8' },
  low_rate:      { label: 'Low Rate',   emoji: '💰', color: '#80cbc4' },
  other:         { label: 'Other',           emoji: '❓', color: '#90a4ae' },
};

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString('en-US', { day: 'numeric', month: 'long', year: 'numeric' });
}

function getRatingColor(rating) {
  if (rating >= 4) return COLORS.success;
  if (rating >= 3) return COLORS.warning;
  return COLORS.error;
}

function StarRating({ rating, size = 16 }) {
  const stars = [];
  for (let i = 1; i <= 5; i++) {
    const filled = i <= Math.floor(rating);
    const half = !filled && i - 0.5 <= rating;
    stars.push(
      <Ionicons
        key={i}
        name={filled ? 'star' : half ? 'star-half' : 'star-outline'}
        size={size}
        color={filled || half ? COLORS.warning : COLORS.textMuted}
      />
    );
  }
  return <View style={styles.starsRow}>{stars}</View>;
}

function IssueBadge({ issueType }) {
  const meta = ISSUE_TYPE_MAP[issueType] || ISSUE_TYPE_MAP.other;
  return (
    <View style={[styles.issueBadge, { borderColor: meta.color + '66' }]}>
      <Text style={styles.issueBadgeText}>
        {meta.emoji} {meta.label}
      </Text>
    </View>
  );
}

function ReviewCard({ review, onDelete }) {
  const rating = parseFloat(review.rating || 0);
  const ratingColor = getRatingColor(rating);

  return (
    <View style={styles.reviewCard}>
      <View style={styles.reviewHeader}>
        <StarRating rating={rating} size={13} />
        <View style={styles.reviewHeaderRight}>
          <Text style={[styles.reviewRatingNum, { color: ratingColor }]}>
            {rating.toFixed(1)}
          </Text>
          {onDelete && (
            <TouchableOpacity onPress={onDelete} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name="trash-outline" size={15} color={COLORS.textMuted} />
            </TouchableOpacity>
          )}
        </View>
      </View>

      {review.issue_type && (
        <View style={styles.reviewBadgeRow}>
          <IssueBadge issueType={review.issue_type} />
        </View>
      )}

      {review.comment ? (
        <Text style={styles.reviewComment}>{review.comment}</Text>
      ) : null}

      <View style={styles.reviewFooter}>
        <Text style={styles.reviewDate}>{formatDate(review.created_at)}</Text>
        {review.is_anonymous ? (
          <Text style={styles.reviewAnon}>Anonymous</Text>
        ) : null}
      </View>
    </View>
  );
}

export default function BrokerDetailScreen({ route, navigation }) {
  const { brokerId, brokerName } = route.params;
  const [broker, setBroker] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [reviewsPage, setReviewsPage] = useState(1);
  const [loadingMoreReviews, setLoadingMoreReviews] = useState(false);
  const [hasMoreReviews, setHasMoreReviews] = useState(false);

  useEffect(() => {
    navigation.setOptions({ title: brokerName || 'Broker' });
    loadBroker(1);
  }, [brokerId]);

  const loadBroker = async (page = 1) => {
    if (page === 1) {
      setLoading(true);
      setError(null);
    } else {
      setLoadingMoreReviews(true);
    }
    try {
      const data = await getBrokerDetail(brokerId, page);
      if (page === 1) {
        setBroker(data);
      } else {
        setBroker(prev => ({
          ...prev,
          reviews: [...(prev.reviews || []), ...(data.reviews || [])],
        }));
      }
      setReviewsPage(page);
      setHasMoreReviews(data.reviews_has_more || false);
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to load broker data';
      if (page === 1) setError(msg);
    } finally {
      if (page === 1) setLoading(false);
      else setLoadingMoreReviews(false);
    }
  };

  const handleLoadMoreReviews = () => {
    if (!loadingMoreReviews && hasMoreReviews) {
      loadBroker(reviewsPage + 1);
    }
  };

  const handleAddReview = () => {
    navigation.navigate('AddBrokerReview', { mode: 'review', brokerId, brokerName: broker?.name });
  };

  const handleRefresh = () => loadBroker(1);

  const handleDeleteReview = (review) => {
    Alert.alert(
      'Delete review?',
      'This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => confirmDeleteReview(review.id),
        },
      ]
    );
  };

  const confirmDeleteReview = async (reviewId) => {
    setDeletingId(reviewId);
    try {
      await deleteBrokerReview(brokerId, reviewId);
      setBroker(prev => ({
        ...prev,
        reviews: prev.reviews.filter(r => r.id !== reviewId),
        review_count: (prev.review_count || 1) - 1,
      }));
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to delete review';
      Alert.alert('Error', msg);
    } finally {
      setDeletingId(null);
    }
  };

  const handlePhone = (phone) => {
    if (!phone) return;
    Linking.openURL(`tel:${phone.replace(/\D/g, '')}`);
  };

  const handleEmail = (email) => {
    if (!email) return;
    Linking.openURL(`mailto:${email}`);
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>Loading broker...</Text>
      </View>
    );
  }

  if (error || !broker) {
    return (
      <View style={styles.center}>
        <Ionicons name="alert-circle-outline" size={48} color={COLORS.error} />
        <Text style={styles.errorText}>{error || 'Broker not found'}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={loadBroker}>
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const avgRating = parseFloat(broker.avg_rating || 0);
  const ratingColor = getRatingColor(avgRating);
  const reviews = broker.reviews || [];

  return (
    <View style={{ flex: 1, backgroundColor: COLORS.bg }}>
      <ScrollView style={styles.container} contentContainerStyle={styles.scroll}>

        {/* Broker header */}
        <View style={styles.brokerCard}>
          <Text style={styles.brokerName}>{broker.name}</Text>

          <View style={styles.infoGrid}>
            {broker.mc_number ? (
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>MC#</Text>
                <Text style={styles.infoValue}>{broker.mc_number}</Text>
              </View>
            ) : null}
            {broker.dot_number ? (
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>DOT#</Text>
                <Text style={styles.infoValue}>{broker.dot_number}</Text>
              </View>
            ) : null}
            {(broker.city || broker.state) ? (
              <View style={styles.infoRow}>
                <Ionicons name="location-outline" size={14} color={COLORS.textMuted} />
                <Text style={styles.infoValue}>
                  {[broker.city, broker.state].filter(Boolean).join(', ')}
                </Text>
              </View>
            ) : null}
          </View>

          <View style={styles.contactRow}>
            {broker.phone ? (
              <TouchableOpacity style={styles.contactBtn} onPress={() => handlePhone(broker.phone)}>
                <Ionicons name="call-outline" size={15} color={COLORS.primary} />
                <Text style={styles.contactBtnText}>{broker.phone}</Text>
              </TouchableOpacity>
            ) : null}
            {broker.email ? (
              <TouchableOpacity style={styles.contactBtn} onPress={() => handleEmail(broker.email)}>
                <Ionicons name="mail-outline" size={15} color={COLORS.primary} />
                <Text style={styles.contactBtnText}>{broker.email}</Text>
              </TouchableOpacity>
            ) : null}
          </View>
        </View>

        {/* Rating block */}
        <View style={styles.ratingCard}>
          <View style={styles.ratingMain}>
            <Text style={[styles.ratingBig, { color: ratingColor }]}>
              {avgRating > 0 ? avgRating.toFixed(1) : '—'}
            </Text>
            <View style={styles.ratingRight}>
              <StarRating rating={avgRating} size={18} />
              <Text style={styles.ratingReviewCount}>
                {broker.review_count || 0} review{getReviewWord(broker.review_count || 0)}
              </Text>
            </View>
          </View>

          {/* Star distribution */}
          {broker.rating_distribution && (
            <View style={styles.ratingDistribution}>
              {[5, 4, 3, 2, 1].map(star => {
                const count = broker.rating_distribution[star] || 0;
                const total = broker.review_count || 1;
                const pct = Math.round((count / total) * 100);
                return (
                  <View key={star} style={styles.distRow}>
                    <Text style={styles.distLabel}>{star} ⭐</Text>
                    <View style={styles.distBarWrap}>
                      <View style={[styles.distBar, { width: `${pct}%`, backgroundColor: getRatingColor(star) }]} />
                    </View>
                    <Text style={styles.distCount}>{count}</Text>
                  </View>
                );
              })}
            </View>
          )}
        </View>

        {/* Reviews */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Reviews</Text>
          <Text style={styles.sectionCount}>{reviews.length}</Text>
        </View>

        {reviews.length === 0 ? (
          <View style={styles.noReviews}>
            <Text style={styles.noReviewsText}>No reviews yet</Text>
            <Text style={styles.noReviewsSub}>Be the first to write a review</Text>
          </View>
        ) : (
          reviews.map(review => (
            <ReviewCard
              key={review.id}
              review={review}
              onDelete={review.can_delete ? () => handleDeleteReview(review) : null}
            />
          ))
        )}

        {hasMoreReviews && (
          <TouchableOpacity
            style={styles.loadMoreBtn}
            onPress={handleLoadMoreReviews}
            disabled={loadingMoreReviews}
          >
            {loadingMoreReviews ? (
              <ActivityIndicator size="small" color={COLORS.primary} />
            ) : (
              <Text style={styles.loadMoreBtnText}>Load more reviews</Text>
            )}
          </TouchableOpacity>
        )}

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* Write Review button */}
      <View style={styles.bottomBar}>
        <TouchableOpacity style={styles.reviewBtn} onPress={handleAddReview}>
          <Ionicons name="create-outline" size={18} color={COLORS.textInverse} />
          <Text style={styles.reviewBtnText}>Write Review</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

function getReviewWord(count) {
  return count === 1 ? '' : 's';
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  scroll: { padding: 16, paddingBottom: 40 },

  center: {
    flex: 1,
    backgroundColor: COLORS.bg,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  loadingText: { color: COLORS.textMuted, fontSize: 14, marginTop: 12 },
  errorText: { color: COLORS.error, fontSize: 14, textAlign: 'center', marginTop: 12 },
  retryBtn: {
    marginTop: 20,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: COLORS.primary,
  },
  retryText: { color: COLORS.primary, fontSize: 14, fontWeight: '700' },

  // Broker card
  brokerCard: {
    backgroundColor: COLORS.bgCard,
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
  },
  brokerName: { color: COLORS.textPrimary, fontSize: 22, fontWeight: '800', marginBottom: 14 },
  infoGrid: { gap: 8, marginBottom: 14 },
  infoRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  infoLabel: { color: COLORS.textMuted, fontSize: 12, fontWeight: '700', width: 40 },
  infoValue: { color: COLORS.textSecondary, fontSize: 14 },
  contactRow: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  contactBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: COLORS.primaryLight,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  contactBtnText: { color: COLORS.primary, fontSize: 13 },

  // Rating card
  ratingCard: {
    backgroundColor: COLORS.bgCard,
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
  },
  ratingMain: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    marginBottom: 16,
  },
  ratingBig: { fontSize: 52, fontWeight: '900', lineHeight: 60 },
  ratingRight: { flex: 1 },
  starsRow: { flexDirection: 'row', gap: 3, marginBottom: 6 },
  ratingReviewCount: { color: COLORS.textMuted, fontSize: 13 },

  ratingDistribution: { gap: 6 },
  distRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  distLabel: { color: COLORS.textMuted, fontSize: 12, width: 32 },
  distBarWrap: {
    flex: 1,
    height: 6,
    backgroundColor: COLORS.bgCardAlt,
    borderRadius: 3,
    overflow: 'hidden',
  },
  distBar: { height: '100%', borderRadius: 3 },
  distCount: { color: COLORS.textMuted, fontSize: 12, width: 20, textAlign: 'right' },

  // Section
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
    marginTop: 4,
  },
  sectionTitle: {
    color: COLORS.textSecondary,
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sectionCount: {
    color: COLORS.primary,
    fontSize: 11,
    fontWeight: '700',
    backgroundColor: COLORS.primaryLight,
    borderRadius: 10,
    paddingHorizontal: 7,
    paddingVertical: 2,
    overflow: 'hidden',
  },

  noReviews: {
    alignItems: 'center',
    paddingVertical: 32,
    backgroundColor: COLORS.bgCard,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
  },
  noReviewsText: { color: COLORS.textMuted, fontSize: 16, fontWeight: '700', marginBottom: 6 },
  noReviewsSub: { color: COLORS.textMuted, fontSize: 13 },

  // Review cards
  reviewCard: {
    backgroundColor: COLORS.bgCard,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
  },
  reviewHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  reviewHeaderRight: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  reviewRatingNum: { fontSize: 14, fontWeight: '800' },

  reviewBadgeRow: { marginBottom: 8 },
  issueBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
    borderWidth: 1,
  },
  issueBadgeText: { color: COLORS.textSecondary, fontSize: 12, fontWeight: '600' },

  reviewComment: {
    color: COLORS.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 10,
  },
  reviewFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  reviewDate: { color: COLORS.textMuted, fontSize: 11 },
  reviewAnon: { color: COLORS.textMuted, fontSize: 11, fontStyle: 'italic' },

  loadMoreBtn: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    marginBottom: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.primaryLight,
  },
  loadMoreBtnText: { color: COLORS.primary, fontSize: 14, fontWeight: '600' },

  // Bottom bar
  bottomBar: {
    padding: 16,
    paddingBottom: 24,
    backgroundColor: COLORS.bg,
    borderTopWidth: 1,
    borderTopColor: COLORS.borderLight,
  },
  reviewBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: COLORS.accent,
    paddingVertical: 16,
    borderRadius: 14,
  },
  reviewBtnText: { color: COLORS.textInverse, fontSize: 16, fontWeight: '800' },
});
