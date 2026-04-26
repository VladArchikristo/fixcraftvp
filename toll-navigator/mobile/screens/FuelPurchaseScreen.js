import React, { useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput,
  ScrollView, Image, Alert, ActivityIndicator, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import api from '../services/api';

const US_STATES = [
  'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
  'ID','IL','IN','IA','KS','KY','LA','ME','MD','MA',
  'MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM',
  'NY','NC','ND','OH','OK','OR','PA','RI','SC','SD',
  'TN','TX','UT','VT','VA','WA','WV','WI','WY',
];

export default function FuelPurchaseScreen({ navigation }) {
  const [photoUri, setPhotoUri] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [saving, setSaving] = useState(false);

  const [state, setState] = useState('');
  const [gallons, setGallons] = useState('');
  const [pricePerGallon, setPricePerGallon] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [stationName, setStationName] = useState('');

  // Request permission and pick photo
  const pickImage = async (useCamera) => {
    try {
      let permResult;
      if (useCamera) {
        permResult = await ImagePicker.requestCameraPermissionsAsync();
      } else {
        permResult = await ImagePicker.requestMediaLibraryPermissionsAsync();
      }

      if (permResult.status !== 'granted') {
        Alert.alert('No Access', useCamera ? 'Allow camera access in Settings' : 'Allow photo library access in Settings');
        return;
      }

      const result = useCamera
        ? await ImagePicker.launchCameraAsync({
            mediaTypes: ImagePicker.MediaTypeOptions.Images,
            quality: 0.8,
            base64: true,
          })
        : await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ImagePicker.MediaTypeOptions.Images,
            quality: 0.8,
            base64: true,
          });

      if (!result.canceled && result.assets?.[0]) {
        const asset = result.assets[0];
        setPhotoUri(asset.uri);
        await scanReceipt(asset.base64);
      }
    } catch (err) {
      Alert.alert('Error', 'Failed to open ' + (useCamera ? 'camera' : 'gallery'));
      console.error('[FuelPurchase] pickImage error:', err);
    }
  };

  const scanReceipt = async (base64) => {
    if (!base64) return;
    setScanning(true);
    try {
      const { data } = await api.post('/api/trips/scan-receipt', { image_base64: base64 });

      // Autofill from OCR
      if (data.state && US_STATES.includes(data.state)) setState(data.state);
      if (data.gallons) setGallons(String(data.gallons));
      if (data.price_per_gallon) setPricePerGallon(String(data.price_per_gallon));
      if (data.date) setDate(data.date);
      if (data.station_name) setStationName(data.station_name);

      if (data.mock) {
        Alert.alert('Development Mode', 'OCR key not configured — mock data filled. Enter real values.');
      }
    } catch (err) {
      Alert.alert('OCR Error', 'Failed to scan receipt. Enter data manually.');
      console.error('[FuelPurchase] scanReceipt error:', err?.response?.data || err.message);
    } finally {
      setScanning(false);
    }
  };

  const handleSave = async () => {
    if (!state || !gallons) {
      Alert.alert('Fill in fields', 'State and gallons are required');
      return;
    }
    if (!US_STATES.includes(state.toUpperCase())) {
      Alert.alert('Invalid state', 'Enter a US state abbreviation, e.g. TX, CA, FL');
      return;
    }

    setSaving(true);
    try {
      await api.post('/api/trips/fuel-purchases', {
        state: state.toUpperCase(),
        gallons: parseFloat(gallons),
        price_per_gallon: parseFloat(pricePerGallon) || 0,
        station_name: stationName || null,
        purchase_date: date || null,
      });

      Alert.alert('Saved', `Fuel purchase ${gallons} gal in ${state.toUpperCase()} added`, [
        { text: 'OK', onPress: () => navigation.goBack() },
      ]);
    } catch (err) {
      Alert.alert('Error', err.response?.data?.error || 'Failed to save');
      console.error('[FuelPurchase] save error:', err?.response?.data || err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
      <Text style={styles.title}>Add Fuel Purchase</Text>

      <View style={styles.photoRow}>
        <TouchableOpacity style={styles.photoBtn} onPress={() => pickImage(true)} disabled={scanning}>
          <Ionicons name="camera" size={22} color="#4fc3f7" />
          <Text style={styles.photoBtnText}>Camera</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.photoBtn} onPress={() => pickImage(false)} disabled={scanning}>
          <Ionicons name="images" size={22} color="#4fc3f7" />
          <Text style={styles.photoBtnText}>Gallery</Text>
        </TouchableOpacity>
      </View>

      {/* Photo preview */}
      {photoUri && (
        <View style={styles.previewContainer}>
          <Image source={{ uri: photoUri }} style={styles.previewImage} resizeMode="contain" />
        </View>
      )}

      {/* Spinner OCR */}
      {scanning && (
        <View style={styles.scanningRow}>
          <ActivityIndicator size="small" color="#4fc3f7" />
          <Text style={styles.scanningText}>Scanning receipt...</Text>
        </View>
      )}

      {/* Form */}
      <View style={styles.form}>
        <Text style={styles.label}>State *</Text>
        <TextInput
          style={styles.input}
          placeholder="TX"
          placeholderTextColor="#444"
          value={state}
          onChangeText={(v) => setState(v.toUpperCase().slice(0, 2))}
          maxLength={2}
          autoCapitalize="characters"
        />

        <Text style={styles.label}>Gallons *</Text>
        <TextInput
          style={styles.input}
          placeholder="85.4"
          placeholderTextColor="#444"
          value={gallons}
          onChangeText={setGallons}
          keyboardType="decimal-pad"
        />

        <Text style={styles.label}>Price / gallon ($)</Text>
        <TextInput
          style={styles.input}
          placeholder="3.89"
          placeholderTextColor="#444"
          value={pricePerGallon}
          onChangeText={setPricePerGallon}
          keyboardType="decimal-pad"
        />

        <Text style={styles.label}>Date (YYYY-MM-DD)</Text>
        <TextInput
          style={styles.input}
          placeholder="2026-04-14"
          placeholderTextColor="#444"
          value={date}
          onChangeText={setDate}
        />

        <Text style={styles.label}>Station</Text>
        <TextInput
          style={styles.input}
          placeholder="Pilot Travel Center"
          placeholderTextColor="#444"
          value={stationName}
          onChangeText={setStationName}
        />
      </View>

      {/* Save button */}
      <TouchableOpacity
        style={[styles.saveBtn, (saving || scanning) && styles.saveBtnDisabled]}
        onPress={handleSave}
        disabled={saving || scanning}
      >
        {saving
          ? <ActivityIndicator size="small" color="#fff" />
          : <Ionicons name="checkmark-circle" size={20} color="#fff" />
        }
        <Text style={styles.saveBtnText}>{saving ? 'Saving...' : 'Save Fuel Purchase'}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  scroll: { padding: 20, paddingBottom: 40 },

  title: {
    color: '#fff',
    fontSize: 22,
    fontWeight: '800',
    marginBottom: 20,
  },

  photoRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  photoBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#4fc3f7',
    backgroundColor: '#0a1f2e',
  },
  photoBtnText: { color: '#4fc3f7', fontSize: 14, fontWeight: '700' },

  previewContainer: {
    borderRadius: 12,
    overflow: 'hidden',
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#1e1e3a',
    backgroundColor: '#161629',
  },
  previewImage: { width: '100%', height: 200 },

  scanningRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 14,
    padding: 12,
    backgroundColor: '#0a1520',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1e3a50',
  },
  scanningText: { color: '#4fc3f7', fontSize: 13, fontWeight: '600' },

  form: { gap: 4, marginBottom: 20 },

  label: {
    color: '#888',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    marginTop: 12,
    marginBottom: 6,
  },
  input: {
    backgroundColor: '#161629',
    borderWidth: 1,
    borderColor: '#1e1e3a',
    borderRadius: 10,
    color: '#fff',
    fontSize: 15,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },

  saveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: '#4fc3f7',
    paddingVertical: 16,
    borderRadius: 14,
  },
  saveBtnDisabled: { backgroundColor: '#2a5a70', opacity: 0.7 },
  saveBtnText: { color: '#fff', fontSize: 15, fontWeight: '800' },
});
