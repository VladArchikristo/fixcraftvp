import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, Alert, Switch, KeyboardAvoidingView, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { addBrokerReview, createBrokerWithReview } from '../services/brokers';

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
            color={star <= value ? '#ffb74d' : '#333'}
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
        Alert.alert('Done!', `Broker "${broker.name}" added with reviewом.`, [
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
      style={{ flex: 1, backgroundColor: '#0d0d1a' }}
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
              placeholderTextColor="#444"
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
                  placeholderTextColor="#444"
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
                  placeholderTextColor="#444"
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
              placeholderTextColor="#444"
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
                  placeholderTextColor="#444"
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
                  placeholderTextColor="#444"
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
            <Ionicons name="business-outline" size={16} color="#4fc3f7" />
            <Text style={styles.brokerNameBadgeText}>{brokerName}</Text>
          </View>
        )}

        {/* Review section */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Ваш review</Text>

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
            placeholderTextColor="#444"
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
              <Ionicons name="eye-off-outline" size={18} color="#555" />
              <View>
                <Text style={styles.toggleLabel}>Anonymous</Text>
                <Text style={styles.toggleSub}>Your name will not be shown</Text>
              </View>
            </View>
            <Switch
              value={isAnonymous}
              onValueChange={setIsAnonymous}
              trackColor={{ false: '#1e1e3a', true: '#1565c0' }}
              thumbColor={isAnonymous ? '#4fc3f7' : '#555'}
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
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Ionicons name="send-outline" size={18} color="#fff" />
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
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  scroll: { padding: 16, paddingBottom: 40 },

  card: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  cardTitle: {
    color: '#888',
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 16,
  },

  brokerNameBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#0a1520',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#1e3a50',
  },
  brokerNameBadgeText: { color: '#4fc3f7', fontSize: 15, fontWeight: '700' },

  sectionLabelRow: { flexDirection: 'row', marginBottom: 8, marginTop: 4 },
  sectionLabel: { color: '#777', fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.3 },
  sectionRequired: { color: '#ef9a9a', fontSize: 12, fontWeight: '700' },

  input: {
    backgroundColor: '#0d0d1a',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1e1e3a',
    color: '#fff',
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
    backgroundColor: '#1e1e3a',
    marginVertical: 14,
  },

  starInputRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 8,
    paddingVertical: 4,
  },
  ratingLabel: {
    color: '#ffb74d',
    fontSize: 13,
    fontWeight: '700',
    marginBottom: 4,
  },

  issueGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 4,
  },
  issueBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#1e1e3a',
    backgroundColor: '#0d0d1a',
  },
  issueBtnActive: {
    borderColor: '#4fc3f7',
    backgroundColor: '#0a1520',
  },
  issueBtnEmoji: { fontSize: 14 },
  issueBtnText: { color: '#555', fontSize: 12, fontWeight: '600' },
  issueBtnTextActive: { color: '#4fc3f7' },

  textArea: {
    backgroundColor: '#0d0d1a',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1e1e3a',
    color: '#fff',
    fontSize: 15,
    paddingHorizontal: 14,
    paddingVertical: 12,
    minHeight: 110,
    marginBottom: 6,
  },
  charCount: { color: '#444', fontSize: 11, textAlign: 'right' },
  charCountWarn: { color: '#ef9a9a' },

  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  toggleLeft: { flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 },
  toggleLabel: { color: '#bbb', fontSize: 14, fontWeight: '600' },
  toggleSub: { color: '#444', fontSize: 11, marginTop: 2 },

  submitBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: '#1565c0',
    paddingVertical: 18,
    borderRadius: 14,
    marginTop: 4,
  },
  submitBtnDisabled: { backgroundColor: '#0d2a50', opacity: 0.7 },
  submitBtnText: { color: '#fff', fontSize: 16, fontWeight: '800' },
});
