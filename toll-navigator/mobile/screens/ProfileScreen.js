import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, ActivityIndicator, Alert, KeyboardAvoidingView, Platform
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../services/api';

const TRUCK_TYPES = ['Semi-Truck', 'Box Truck', 'Flatbed', 'Tanker', 'Other'];

export default function ProfileScreen({ onLogout }) {
  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [truckType, setTruckType] = useState('Semi-Truck');
  const [usdot, setUsdot] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showTruckPicker, setShowTruckPicker] = useState(false);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/users/profile');
      const d = res.data;
      setName(d.name || '');
      setCompany(d.company || '');
      setTruckType(d.truck_type || 'Semi-Truck');
      setUsdot(d.usdot || '');
    } catch (err) {
      // Silent error on first login — profile may not exist yet
      console.log('[ProfileScreen] loadProfile error:', err?.message);
    } finally {
      setLoading(false);
    }
  };

  const saveProfile = async () => {
    if (!name.trim()) {
      Alert.alert('Error', 'Enter your name');
      return;
    }
    setSaving(true);
    try {
      await api.put('/api/users/profile', {
        name: name.trim(),
        company: company.trim(),
        truck_type: truckType,
        usdot: usdot.trim(),
      });
      Alert.alert('Profile Updated', 'Data saved successfully');
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to save profile';
      Alert.alert('Error', msg);
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    Alert.alert(
      'Sign Out',
      'Are you sure?',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Sign Out', style: 'destructive', onPress: onLogout },
      ]
    );
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#4fc3f7" />
        <Text style={styles.loadingText}>Loading profile...</Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
        onScrollBeginDrag={() => setShowTruckPicker(false)}
      >
        {/* Header */}
        <View style={styles.header}>
          <Ionicons name="person-circle-outline" size={72} color="#4fc3f7" />
          <Text style={styles.headerTitle}>My Profile</Text>
          <Text style={styles.headerSub}>Driver and company details</Text>
        </View>

        {/* Form */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>PERSONAL INFO</Text>

          {/* Name */}
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Driver Name</Text>
            <View style={styles.inputRow}>
              <Ionicons name="person-outline" size={18} color="#4fc3f7" style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="John Smith"
                placeholderTextColor="#555"
                value={name}
                onChangeText={setName}
                autoCapitalize="words"
              />
            </View>
          </View>

          {/* Company */}
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Company</Text>
            <View style={styles.inputRow}>
              <Ionicons name="business-outline" size={18} color="#4fc3f7" style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="ABC Trucking LLC"
                placeholderTextColor="#555"
                value={company}
                onChangeText={setCompany}
                autoCapitalize="words"
              />
            </View>
          </View>

          {/* USDOT */}
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>USDOT Number</Text>
            <View style={styles.inputRow}>
              <Ionicons name="shield-outline" size={18} color="#4fc3f7" style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="1234567"
                placeholderTextColor="#555"
                value={usdot}
                onChangeText={setUsdot}
                keyboardType="number-pad"
              />
            </View>
          </View>
        </View>

        {/* Truck Type */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>VEHICLE TYPE</Text>
          <View style={styles.fieldGroup}>
            <Text style={styles.label}>Truck Type</Text>
            <TouchableOpacity
              style={styles.pickerBtn}
              onPress={() => setShowTruckPicker(!showTruckPicker)}
            >
              <Ionicons name="truck-outline" size={18} color="#4fc3f7" style={styles.inputIcon} />
              <Text style={styles.pickerBtnText}>{truckType}</Text>
              <Ionicons
                name={showTruckPicker ? 'chevron-up' : 'chevron-down'}
                size={18}
                color="#888"
              />
            </TouchableOpacity>

            {showTruckPicker && (
              <View style={styles.dropdownContainer}>
                {TRUCK_TYPES.map((type) => (
                  <TouchableOpacity
                    key={type}
                    style={[
                      styles.dropdownOption,
                      truckType === type && styles.dropdownOptionActive,
                    ]}
                    onPress={() => {
                      setTruckType(type);
                      setShowTruckPicker(false);
                    }}
                  >
                    <Text
                      style={[
                        styles.dropdownOptionText,
                        truckType === type && styles.dropdownOptionTextActive,
                      ]}
                    >
                      {type}
                    </Text>
                    {truckType === type && (
                      <Ionicons name="checkmark" size={16} color="#4fc3f7" />
                    )}
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </View>
        </View>

        {/* Save button */}
        <TouchableOpacity
          style={[styles.saveBtn, saving && styles.saveBtnDisabled]}
          onPress={saveProfile}
          disabled={saving}
        >
          {saving ? (
            <ActivityIndicator color="#0d0d1a" size="small" />
          ) : (
            <>
              <Ionicons name="checkmark-circle-outline" size={20} color="#0d0d1a" />
              <Text style={styles.saveBtnText}>Save Profile</Text>
            </>
          )}
        </TouchableOpacity>

        {/* Logout */}
        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
          <Ionicons name="log-out-outline" size={20} color="#f44336" />
          <Text style={styles.logoutText}>Sign Out</Text>
        </TouchableOpacity>

        <Text style={styles.hint}>HaulWallet • IFTA 2026 • Data encrypted</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  scroll: { padding: 20, paddingBottom: 40 },

  loadingContainer: {
    flex: 1,
    backgroundColor: '#0d0d1a',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 16,
  },
  loadingText: { color: '#888', fontSize: 14 },

  header: {
    alignItems: 'center',
    marginBottom: 28,
    marginTop: 10,
  },
  headerTitle: { fontSize: 22, fontWeight: '800', color: '#fff', marginTop: 12 },
  headerSub: { fontSize: 13, color: '#666', marginTop: 4 },

  card: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  cardTitle: {
    color: '#444',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    marginBottom: 16,
  },

  fieldGroup: { marginBottom: 16 },
  label: {
    color: '#888',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0d0d1a',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: '#2a2a4a',
  },
  inputIcon: { marginRight: 10 },
  input: {
    flex: 1,
    color: '#fff',
    fontSize: 15,
    fontWeight: '500',
  },

  // Picker
  pickerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0d0d1a',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: '#2a2a4a',
  },
  pickerBtnText: {
    flex: 1,
    color: '#fff',
    fontSize: 15,
    fontWeight: '500',
  },
  dropdownContainer: {
    marginTop: 4,
    backgroundColor: '#1a1a2e',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#2a2a4a',
    overflow: 'hidden',
  },
  dropdownOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1e1e3a',
  },
  dropdownOptionActive: { backgroundColor: '#0d1f2d' },
  dropdownOptionText: { color: '#aaa', fontSize: 14 },
  dropdownOptionTextActive: { color: '#4fc3f7', fontWeight: '700' },

  // Buttons
  saveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: '#4fc3f7',
    borderRadius: 14,
    paddingVertical: 16,
    marginBottom: 12,
  },
  saveBtnDisabled: { opacity: 0.6 },
  saveBtnText: { color: '#0d0d1a', fontSize: 16, fontWeight: '800' },

  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: '#1a0a0a',
    borderRadius: 14,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: '#3a1111',
    marginBottom: 20,
  },
  logoutText: { color: '#f44336', fontSize: 15, fontWeight: '700' },

  hint: { textAlign: 'center', color: '#333', fontSize: 12 },
});
