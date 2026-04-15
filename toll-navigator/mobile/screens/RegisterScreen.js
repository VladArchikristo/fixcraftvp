import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, Alert, KeyboardAvoidingView, Platform, ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { register } from '../services/api';
import { saveToken, saveUser } from '../services/auth';

export default function RegisterScreen({ navigation, onLogin }) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPass, setShowPass] = useState(false);

  const handleRegister = async () => {
    if (!name.trim() || !email.trim() || !password.trim()) {
      Alert.alert('Error', 'Fill in all fields');
      return;
    }
    if (password !== password2) {
      Alert.alert('Error', 'Passwords do not match');
      return;
    }
    if (password.length < 6) {
      Alert.alert('Error', 'Password must be at least 6 characters');
      return;
    }

    setLoading(true);
    try {
      const res = await register({
        name: name.trim(),
        email: email.trim().toLowerCase(),
        password,
      });
      await saveToken(res.data.token);
      await saveUser(res.data.user);
      onLogin();
    } catch (err) {
      const msg = err.response?.data?.error || 'Registration error';
      Alert.alert('Error', msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.logo}>🛣️</Text>
          <Text style={styles.title}>Create Account</Text>
          <Text style={styles.subtitle}>HaulWallet for truckers</Text>
        </View>

        {/* Form */}
        <View style={styles.card}>
          {/* Name */}
          <Text style={styles.label}>Name</Text>
          <View style={styles.inputRow}>
            <Ionicons name="person-outline" size={20} color="#4fc3f7" style={styles.icon} />
            <TextInput
              style={styles.input}
              placeholder="John Driver"
              placeholderTextColor="#555"
              value={name}
              onChangeText={setName}
            />
          </View>

          {/* Email */}
          <Text style={[styles.label, { marginTop: 16 }]}>Email</Text>
          <View style={styles.inputRow}>
            <Ionicons name="mail-outline" size={20} color="#4fc3f7" style={styles.icon} />
            <TextInput
              style={styles.input}
              placeholder="driver@company.com"
              placeholderTextColor="#555"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              keyboardType="email-address"
            />
          </View>

          {/* Password */}
          <Text style={[styles.label, { marginTop: 16 }]}>Password</Text>
          <View style={styles.inputRow}>
            <Ionicons name="lock-closed-outline" size={20} color="#4fc3f7" style={styles.icon} />
            <TextInput
              style={styles.input}
              placeholder="At least 6 characters"
              placeholderTextColor="#555"
              value={password}
              onChangeText={setPassword}
              secureTextEntry={!showPass}
            />
            <TouchableOpacity onPress={() => setShowPass(!showPass)}>
              <Ionicons name={showPass ? 'eye-outline' : 'eye-off-outline'} size={20} color="#555" />
            </TouchableOpacity>
          </View>

          {/* Confirm Password */}
          <Text style={[styles.label, { marginTop: 16 }]}>Confirm password</Text>
          <View style={[
            styles.inputRow,
            password2.length > 0 && password !== password2 && styles.inputError
          ]}>
            <Ionicons name="shield-checkmark-outline" size={20} color="#4fc3f7" style={styles.icon} />
            <TextInput
              style={styles.input}
              placeholder="Repeat password"
              placeholderTextColor="#555"
              value={password2}
              onChangeText={setPassword2}
              secureTextEntry={!showPass}
            />
          </View>
          {password2.length > 0 && password !== password2 && (
            <Text style={styles.errorText}>Passwords do not match</Text>
          )}
        </View>

        {/* Register Button */}
        <TouchableOpacity
          style={[styles.btn, loading && styles.btnDisabled]}
          onPress={handleRegister}
          disabled={loading}
        >
          {loading
            ? <ActivityIndicator color="#000" />
            : <Text style={styles.btnText}>Sign Up</Text>
          }
        </TouchableOpacity>

        {/* Back to Login */}
        <TouchableOpacity
          style={styles.link}
          onPress={() => navigation.goBack()}
        >
          <Text style={styles.linkText}>
            Already have an account? <Text style={styles.linkAccent}>Sign In</Text>
          </Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: 20 },

  header: { alignItems: 'center', marginBottom: 32 },
  logo: { fontSize: 48 },
  title: { fontSize: 26, fontWeight: '800', color: '#fff', marginTop: 8 },
  subtitle: { fontSize: 14, color: '#888', marginTop: 4 },

  card: {
    backgroundColor: '#12122a',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#1e1e3a',
    marginBottom: 20,
  },
  label: { color: '#aaa', fontSize: 13, fontWeight: '600', marginBottom: 8 },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0a0a1a',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#1e1e3a',
    paddingHorizontal: 12,
    height: 48,
  },
  inputError: { borderColor: '#f44336' },
  icon: { marginRight: 8 },
  input: { flex: 1, color: '#fff', fontSize: 15 },
  errorText: { color: '#f44336', fontSize: 12, marginTop: 4 },

  btn: {
    backgroundColor: '#4fc3f7',
    borderRadius: 12,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  btnDisabled: { opacity: 0.6 },
  btnText: { color: '#000', fontSize: 16, fontWeight: '800' },

  link: { alignItems: 'center', paddingVertical: 8 },
  linkText: { color: '#666', fontSize: 14 },
  linkAccent: { color: '#4fc3f7', fontWeight: '700' },
});
