import React, { useState, useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { ActivityIndicator, View, Text, StyleSheet } from 'react-native';

import HomeScreen from '../screens/HomeScreen';
import ResultScreen from '../screens/ResultScreen';
import MapScreen from '../screens/MapScreen';
import HistoryScreen from '../screens/HistoryScreen';
import TripHistoryScreen from '../screens/TripHistoryScreen';
import TripDetailScreen from '../screens/TripDetailScreen';
import FuelPurchaseScreen from '../screens/FuelPurchaseScreen';
import IFTADashboardScreen from '../screens/IFTADashboardScreen';
import ProfileScreen from '../screens/ProfileScreen';
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
      <Stack.Screen name="HistoryList" component={TripHistoryScreen} options={{ title: 'История поездок' }} />
      <Stack.Screen name="TripDetail" component={TripDetailScreen} options={{ title: 'Детали поездки' }} />
    </Stack.Navigator>
  );
}

// Fuel stack
function FuelStack() {
  return (
    <Stack.Navigator screenOptions={stackScreenOptions}>
      <Stack.Screen name="FuelPurchase" component={FuelPurchaseScreen} options={{ title: 'Заправки' }} />
    </Stack.Navigator>
  );
}

// IFTA stack
function IFTAStack() {
  return (
    <Stack.Navigator screenOptions={stackScreenOptions}>
      <Stack.Screen name="IFTADashboard" component={IFTADashboardScreen} options={{ title: 'IFTA' }} />
    </Stack.Navigator>
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
            Fuel: focused ? 'flame' : 'flame-outline',
            History: focused ? 'time' : 'time-outline',
            IFTA: focused ? 'bar-chart' : 'bar-chart-outline',
            Profile: focused ? 'person' : 'person-outline',
          };
          return <Ionicons name={icons[route.name] || 'ellipse'} size={size} color={color} />;
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
      })}
    >
      <Tab.Screen name="Calc" component={CalcStack} options={{ tabBarLabel: 'Маршрут' }} />
      <Tab.Screen name="Fuel" component={FuelStack} options={{ tabBarLabel: 'Заправки' }} />
      <Tab.Screen name="History" component={HistoryStack} options={{ tabBarLabel: 'История' }} />
      <Tab.Screen name="IFTA" component={IFTAStack} options={{ tabBarLabel: 'IFTA' }} />
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
});
