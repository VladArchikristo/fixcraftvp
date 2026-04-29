import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, Alert, Switch, KeyboardAvoidingView, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { addBrokerReview, createBrokerWithReview } from '../services/brokers';
import { COLORS, FONTS, SPACING, RADIUS, SHARED } from '../theme';

const ISSUE_TYPES = [
  { value: 'late_payment',  label: 'Late Payment', emoji: '🕐' },
  { value: 'fraud',         label: 'Fraud',   emoji: '⚠️' },
  { value: 'double_broker', label: 'Double Broker',  emoji: '🔄' },
  { value: 'low_rate',      label: 'Low Rate',   emoji: '💰' },
  { value: 'other',         label: 'Other',           emoji: '❓' },
];

const MAX_COMMENT = 2000;

function StarInput({ value, onChange }) {
  return (
    <View style={styles.starInputRow}>
      {[1, 2, 3, 4, 5].map(star => (
        <TouchableOpacity
          key={star}
          onPress={() => onChange(star)}
          hitSlop={{ top: 8, bottom: 8, left: 6, right: 6 }}
        >
          <Ionicons
            name={star <= value ? 'star' : 'star-outline'}
            size={38}
            color={star <= value ? COLORS.warning : COLORS.textMuted}
          />
        </TouchableOpacity>
      ))}
    </View>
  );
}

function SectionLabel({ text, required }) {
  return (
    <View style={styles.sectionLabelRow}>
      <Text style={styles.sectionLabel}>{text}</Text>
      {required && <Text style={styles.sectionRequired}> *</Text>}
    </View>
  );
}

export default function AddBrokerReviewScreen({ route, navigation }) {
  // mode: 'new' — adding broker+review, 'review' — review only for existing broker
  const { mode = 'new', brokerId, brokerName } = route.params || {};
  const isNewBroker = mode === 'new';

  // New broker fields
  const [brokerNameField, setBrokerNameField] = useState('');
  const [mcNumber, setMcNumber] = useState('');
  const [dotNumber, setDotNumber] = useState('');
  const [phone, setPhone] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');

  // Review fields
  const [rating, setRating] = useState(0);
  const [issueType, setIssueType] = useState('');
  const [comment, setComment] = useState('');
  const [isAnonymous, setIsAnonymous] = useState(false);

  const [submitting, setSubmitting] = useState(false);

  React.useEffect(() => {
    if (isNewBroker) {
      navigation.setOptions({ title: 'Add Broker' });
    } else {
      navigation.setOptions({ title: `Review: ${brokerName || 'Broker'}` });
    }
  }, []);

  const validate = () => {
    if (isNewBroker && !brokerNameField.trim()) {
      Alert.alert('Error', 'Enter broker name');
      return false;
    }
    if (rating === 0) {
      Alert.alert('Error', 'Rate 1–5 stars');
      return false;
    }
    return true;
  };

  const handleSubmit = async () => {
    if (!validate()) return;

    setSubmitting(true);
    try {
      const reviewData = {
        rating,
        issue_type: issueType || null,
        comment: comment.trim() || null,
        is_anonymous: isAnonymous,
      };

      if (isNewBroker) {
        const brokerData = {
          name: brokerNameField.trim(),
          mc_number: mcNumber.trim() || null,
          dot_number: dotNumber.trim() || null,
          phone: phone.trim() || null,
          city: city.trim() || null,
          state: state.trim().toUpperCase() || null,
        };
        const { broker } = await createBrokerWithReview(brokerData, reviewData);
        Alert.alert('Done!', `Broker "${broker.name}" added with your review.`, [
          {
            text: 'View',
            onPress: () => {
              navigation.replace('BrokerDetail', { brokerId: broker.id, brokerName: broker.name });
            },
          },
          {
            text: 'Back to list',
            onPress: () => navigation.navigate('BrokerList'),
          },
        ]);
      } else {
        await addBrokerReview(brokerId, reviewData);
        Alert.alert('Done!', 'Your review has been published.', [
          { text: 'OK', onPress: () => navigation.goBack() },
        ]);
      }
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to save review';
      Alert.alert('Error', msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: COLORS.bg }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={88}
    >
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
      >
        {/* New broker section */}
        {isNewBroker && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Broker Information</Text>

            <SectionLabel text="Name / Company" required />
            <TextInput
              style={styles.input}
              placeholder="e.g. Best Freight LLC"
              placeholderTextColor={COLORS.textMuted}
              value={brokerNameField}
              onChangeText={setBrokerNameField}
              autoCapitalize="words"
            />

            <View style={styles.row2}>
              <View style={styles.col2}>
                <SectionLabel text="MC#" />
                <TextInput
                  style={styles.input}
                  placeholder="123456"
                  placeholderTextColor={COLORS.textMuted}
                  value={mcNumber}
                  onChangeText={setMcNumber}
                  keyboardType="numeric"
                />
              </View>
              <View style={styles.col2}>
                <SectionLabel text="DOT#" />
                <TextInput
                  style={styles.input}
                  placeholder="654321"
                  placeholderTextColor={COLORS.textMuted}
                  value={dotNumber}
                  onChangeText={setDotNumber}
                  keyboardType="numeric"
                />
              </View>
            </View>

            <SectionLabel text="Phone" />
            <TextInput
              style={styles.input}
              placeholder="+1 (555) 000-0000"
              placeholderTextColor={COLORS.textMuted}
              value={phone}
              onChangeText={setPhone}
              keyboardType="phone-pad"
            />

            <View style={styles.row2}>
              <View style={styles.col2flex}>
                <SectionLabel text="City" />
                <TextInput
                  style={styles.input}
                  placeholder="Chicago"
                  placeholderTextColor={COLORS.textMuted}
                  value={city}
                  onChangeText={setCity}
                  autoCapitalize="words"
                />
              </View>
              <View style={styles.colState}>
                <SectionLabel text="State" />
                <TextInput
                  style={styles.input}
                  placeholder="IL"
                  placeholderTextColor={COLORS.textMuted}
                  value={state}
                  onChangeText={(t) => setState(t.toUpperCase().slice(0, 2))}
                  autoCapitalize="characters"
                  maxLength={2}
                />
              </View>
            </View>
          </View>
        )}

        {/* If editing existing — show name */}
        {!isNewBroker && brokerName && (
          <View style={styles.brokerNameBadge}>
            <Ionicons name="business-outline" size={16} color={COLORS.primary} />
            <Text style={styles.brokerNameBadgeText}>{brokerName}</Text>
          </View>
        )}

        {/* Review section */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Your Review</Text>

          <SectionLabel text="Rating" required />
          <StarInput value={rating} onChange={setRating} />
          {rating > 0 && (
            <Text style={styles.ratingLabel}>
              {['', 'Terrible', 'Poor', 'Average', 'Good', 'Excellent'][rating]}
            </Text>
          )}

          <View style={styles.divider} />

          <SectionLabel text="Issue Type" />
          <View style={styles.issueGrid}>
            {ISSUE_TYPES.map(item => (
              <TouchableOpacity
                key={item.value}
                style={[
                  styles.issueBtn,
                  issueType === item.value && styles.issueBtnActive,
                ]}
                onPress={() => setIssueType(issueType === item.value ? '' : item.value)}
              >
                <Text style={styles.issueBtnEmoji}>{item.emoji}</Text>
                <Text style={[
                  styles.issueBtnText,
                  issueType === item.value && styles.issueBtnTextActive,
                ]}>
                  {item.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <View style={styles.divider} />

          <SectionLabel text="Comment" />
          <TextInput
            style={styles.textArea}
            placeholder="Describe the situation in detail..."
            placeholderTextColor={COLORS.textMuted}
            value={comment}
            onChangeText={(t) => setComment(t.slice(0, MAX_COMMENT))}
            multiline
            numberOfLines={5}
            textAlignVertical="top"
          />
          <Text style={[
            styles.charCount,
            comment.length > MAX_COMMENT * 0.9 && styles.charCountWarn,
          ]}>
            {comment.length} / {MAX_COMMENT}
          </Text>

          <View style={styles.divider} />

          {/* Anonymous */}
          <View style={styles.toggleRow}>
            <View style={styles.toggleLeft}>
              <Ionicons name="eye-off-outline" size={18} color={COLORS.textMuted} />
              <View>
                <Text style={styles.toggleLabel}>Anonymous</Text>
                <Text style={styles.toggleSub}>Your name will not be shown</Text>
              </View>
            </View>
            <Switch
              value={isAnonymous}
              onValueChange={setIsAnonymous}
              trackColor={{ false: COLORS.bgCardAlt, true: COLORS.accent }}
              thumbColor={isAnonymous ? COLORS.primary : COLORS.textMuted}
            />
          </View>
        </View>

        {/* Publish button */}
        <TouchableOpacity
          style={[styles.submitBtn, submitting && styles.submitBtnDisabled]}
          onPress={handleSubmit}
          disabled={submitting}
        >
          {submitting ? (
            <ActivityIndicator size="small" color={COLORS.textInverse} />
          ) : (
            <Ionicons name="send-outline" size={18} color={COLORS.textInverse} />
          )}
          <Text style={styles.submitBtnText}>
            {submitting ? 'Publishing...' : 'Publish Review'}
          </Text>
        </TouchableOpacity>

        <View style={{ height: 40 }} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  scroll: { padding: SPACING.md, paddingBottom: 40 },

  card: {
    backgroundColor: COLORS.bgCard,
    borderRadius: 14,
    padding: SPACING.md,
    marginBottom: SPACING.md,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
  },
  cardTitle: {
    color: COLORS.textSecondary,
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: SPACING.md,
  },

  brokerNameBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
    backgroundColor: COLORS.primaryLight,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    marginBottom: SPACING.md,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  brokerNameBadgeText: { color: COLORS.primary, fontSize: 15, fontWeight: '700' },

  sectionLabelRow: { flexDirection: 'row', marginBottom: SPACING.sm, marginTop: SPACING.xs },
  sectionLabel: { color: COLORS.textMuted, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.3 },
  sectionRequired: { color: COLORS.error, fontSize: 12, fontWeight: '700' },

  input: {
    backgroundColor: COLORS.bg,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
    color: COLORS.textPrimary,
    fontSize: 15,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 12,
  },

  row2: { flexDirection: 'row', gap: 10 },
  col2: { flex: 1 },
  col2flex: { flex: 1 },
  colState: { width: 70 },

  divider: {
    height: 1,
    backgroundColor: COLORS.bgCardAlt,
    marginVertical: 14,
  },

  starInputRow: {
    flexDirection: 'row',
    gap: SPACING.sm,
    marginBottom: SPACING.sm,
    paddingVertical: SPACING.xs,
  },
  ratingLabel: {
    color: COLORS.warning,
    fontSize: 13,
    fontWeight: '700',
    marginBottom: SPACING.xs,
  },

  issueGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: SPACING.sm,
    marginBottom: SPACING.xs,
  },
  issueBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: SPACING.sm,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
    backgroundColor: COLORS.bg,
  },
  issueBtnActive: {
    borderColor: COLORS.primary,
    backgroundColor: COLORS.primaryLight,
  },
  issueBtnEmoji: { fontSize: 14 },
  issueBtnText: { color: COLORS.textMuted, fontSize: 12, fontWeight: '600' },
  issueBtnTextActive: { color: COLORS.primary },

  textArea: {
    backgroundColor: COLORS.bg,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: COLORS.bgCardAlt,
    color: COLORS.textPrimary,
    fontSize: 15,
    paddingHorizontal: 14,
    paddingVertical: 12,
    minHeight: 110,
    marginBottom: 6,
  },
  charCount: { color: COLORS.textMuted, fontSize: 11, textAlign: 'right' },
  charCountWarn: { color: COLORS.error },

  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  toggleLeft: { flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 },
  toggleLabel: { color: COLORS.textSecondary, fontSize: 14, fontWeight: '600' },
  toggleSub: { color: COLORS.textMuted, fontSize: 11, marginTop: 2 },

  submitBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: COLORS.accent,
    paddingVertical: 18,
    borderRadius: 14,
    marginTop: SPACING.xs,
  },
  submitBtnDisabled: { backgroundColor: COLORS.bgCardAlt, opacity: 0.7 },
  submitBtnText: { color: COLORS.textInverse, fontSize: 16, fontWeight: '800' },
});
