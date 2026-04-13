import React, { useState, useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { ActivityIndicator, View, TouchableOpacity, Text, StyleSheet } from 'react-native';

import HomeScreen from '../screens/HomeScreen';
import ResultScreen from '../screens/ResultScreen';
import MapScreen from '../screens/MapScreen';
import HistoryScreen from '../screens/HistoryScreen';
import LoginScreen from '../screens/LoginScreen';
import RegisterScreen from '../screens/RegisterScreen';
import { getToken, logout } from '../services/auth';

const Stack = createStackNavigator();
const Tab = createBottomTabNavigator();

const stackScreenOptions = {
  headerStyle: { backgroundColor: '#0d0d1a', elevation: 0, shadowOpacity: 0 },
  headerTintColor: '#4fc3f7',
  headerTitleStyle: { color: '#fff', fontWeight: '700' },
  cardStyle: { backgroundColor: '#0d0d1a' },
};

// Auth stack
function AuthStack({ onLogin }) {
  return (
    <Stack.Navigator screenOptions={{ ...stackScreenOptions, headerShown: false }}>
      <Stack.Screen name="Login">
        {(props) => <LoginScreen {...props} onLogin={onLogin} />}
      </Stack.Screen>
      <Stack.Screen name="Register">
        {(props) => <RegisterScreen {...props} onLogin={onLogin} />}
      </Stack.Screen>
    </Stack.Navigator>
  );
}

// Calc stack
function CalcStack() {
  return (
    <Stack.Navigator screenOptions={stackScreenOptions}>
      <Stack.Screen name="Home" component={HomeScreen} options={{ headerShown: false }} />
      <Stack.Screen name="Result" component={ResultScreen} options={{ title: 'Маршрут и сборы' }} />
      <Stack.Screen name="Map" component={MapScreen} options={{ title: 'Карта маршрута', headerShown: false }} />
    </Stack.Navigator>
  );
}

// History stack
function HistoryStack() {
  return (
    <Stack.Navigator screenOptions={stackScreenOptions}>
      <Stack.Screen name="HistoryList" component={HistoryScreen} options={{ title: 'История маршрутов' }} />
    </Stack.Navigator>
  );
}

// Profile screen (simple)
function ProfileScreen({ onLogout }) {
  return (
    <View style={styles.profileContainer}>
      <Ionicons name="person-circle-outline" size={90} color="#4fc3f7" />
      <Text style={styles.profileTitle}>Мой профиль</Text>
      <Text style={styles.profileSub}>Toll Navigator Driver</Text>
      <TouchableOpacity style={styles.logoutBtn} onPress={onLogout}>
        <Ionicons name="log-out-outline" size={20} color="#f44336" />
        <Text style={styles.logoutText}>Выйти из аккаунта</Text>
      </TouchableOpacity>
    </View>
  );
}

// Main tab navigator
function MainTabs({ onLogout }) {
  const handleLogout = async () => {
    await logout();
    onLogout();
  };

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarStyle: {
          backgroundColor: '#0d0d1a',
          borderTopColor: '#1e1e3a',
          borderTopWidth: 1,
          height: 60,
          paddingBottom: 8,
        },
        tabBarActiveTintColor: '#4fc3f7',
        tabBarInactiveTintColor: '#444',
        tabBarIcon: ({ focused, color, size }) => {
          const icons = {
            Calc: focused ? 'calculator' : 'calculator-outline',
            History: focused ? 'time' : 'time-outline',
            Profile: focused ? 'person' : 'person-outline',
          };
          return <Ionicons name={icons[route.name] || 'ellipse'} size={size} color={color} />;
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
      })}
    >
      <Tab.Screen name="Calc" component={CalcStack} options={{ tabBarLabel: 'Калькулятор' }} />
      <Tab.Screen name="History" component={HistoryStack} options={{ tabBarLabel: 'История' }} />
      <Tab.Screen name="Profile" options={{ tabBarLabel: 'Профиль' }}>
        {() => <ProfileScreen onLogout={handleLogout} />}
      </Tab.Screen>
    </Tab.Navigator>
  );
}

// Root navigator — проверяем токен при старте
export default function AppNavigator() {
  const [isLoggedIn, setIsLoggedIn] = useState(null);

  useEffect(() => {
    getToken().then((token) => setIsLoggedIn(!!token));
  }, []);

  if (isLoggedIn === null) {
    return (
      <View style={styles.splash}>
        <Text style={styles.splashLogo}>🛣️</Text>
        <ActivityIndicator size="large" color="#4fc3f7" style={{ marginTop: 24 }} />
      </View>
    );
  }

  return (
    <NavigationContainer>
      {isLoggedIn
        ? <MainTabs onLogout={() => setIsLoggedIn(false)} />
        : <AuthStack onLogin={() => setIsLoggedIn(true)} />
      }
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  splash: {
    flex: 1,
    backgroundColor: '#0d0d1a',
    justifyContent: 'center',
    alignItems: 'center',
  },
  splashLogo: { fontSize: 72 },

  profileContainer: {
    flex: 1,
    backgroundColor: '#0d0d1a',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  profileTitle: { fontSize: 22, fontWeight: '800', color: '#fff', marginTop: 16 },
  profileSub: { fontSize: 14, color: '#888', marginTop: 4, marginBottom: 40 },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1a0a0a',
    borderRadius: 12,
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: '#3a1111',
    gap: 10,
  },
  logoutText: { color: '#f44336', fontSize: 15, fontWeight: '700' },
});
