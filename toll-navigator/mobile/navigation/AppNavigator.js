import React, { useState, useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { ActivityIndicator, View, Text, StyleSheet } from 'react-native';

import HomeScreen from '../screens/HomeScreen';
import ResultScreen from '../screens/ResultScreen';
import MapScreen from '../screens/MapScreen';
import TripHistoryScreen from '../screens/TripHistoryScreen';
import TripDetailScreen from '../screens/TripDetailScreen';
import FuelPurchaseScreen from '../screens/FuelPurchaseScreen';
import IFTADashboardScreen from '../screens/IFTADashboardScreen';
import BrokerListScreen from '../screens/BrokerListScreen';
import BrokerDetailScreen from '../screens/BrokerDetailScreen';
import AddBrokerReviewScreen from '../screens/AddBrokerReviewScreen';
import ProfileScreen from '../screens/ProfileScreen';
import LoginScreen from '../screens/LoginScreen';
import RegisterScreen from '../screens/RegisterScreen';
import DocumentScannerScreen from '../screens/DocumentScannerScreen';
import DocumentHistoryScreen from '../screens/DocumentHistoryScreen';
import ImageEditScreen from '../screens/ImageEditScreen';
import LoadTrackingScreen from '../screens/LoadTrackingScreen';
import ExpenseDashboardScreen from '../screens/ExpenseDashboardScreen';
import AddExpenseScreen from '../screens/AddExpenseScreen';
import AddLoadScreen from '../screens/AddLoadScreen';
import { getToken, logout } from '../services/auth';
import { COLORS } from '../theme';

const Stack = createStackNavigator();
const Tab = createBottomTabNavigator();

const stackScreenOptions = {
  headerStyle: { backgroundColor: COLORS.bg, elevation: 0, shadowOpacity: 0, borderBottomWidth: 1, borderBottomColor: COLORS.borderLight },
  headerTintColor: COLORS.primary,
  headerTitleStyle: { color: COLORS.textPrimary, fontWeight: '700' },
  cardStyle: { backgroundColor: COLORS.bg },
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
      <Stack.Screen name="Result" component={ResultScreen} options={{ title: 'Route & Tolls' }} />
      <Stack.Screen name="Map" component={MapScreen} options={{ title: 'Route Map', headerShown: false }} />
    </Stack.Navigator>
  );
}

// History stack
function HistoryStack() {
  return (
    <Stack.Navigator screenOptions={stackScreenOptions}>
      <Stack.Screen name="HistoryList" component={TripHistoryScreen} options={{ title: 'Trip History' }} />
      <Stack.Screen name="TripDetail" component={TripDetailScreen} options={{ title: 'Trip Details' }} />
    </Stack.Navigator>
  );
}

// Fuel stack
function FuelStack() {
  return (
    <Stack.Navigator screenOptions={stackScreenOptions}>
      <Stack.Screen name="FuelPurchase" component={FuelPurchaseScreen} options={{ title: 'Fuel Purchases' }} />
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

// Brokers stack
function BrokersStack() {
  return (
    <Stack.Navigator screenOptions={stackScreenOptions}>
      <Stack.Screen name="BrokerList" component={BrokerListScreen} options={{ title: 'Brokers' }} />
      <Stack.Screen name="BrokerDetail" component={BrokerDetailScreen} options={{ title: 'Broker' }} />
      <Stack.Screen name="AddBrokerReview" component={AddBrokerReviewScreen} options={{ title: 'Add Review' }} />
    </Stack.Navigator>
  );
}

// Documents stack
function DocumentsStack() {
  return (
    <Stack.Navigator screenOptions={stackScreenOptions}>
      <Stack.Screen name="DocumentScanner" component={DocumentScannerScreen} options={{ headerShown: false }} />
      <Stack.Screen name="DocumentHistory" component={DocumentHistoryScreen} options={{ headerShown: false }} />
      <Stack.Screen
        name="ImageEdit"
        component={ImageEditScreen}
        options={{ headerShown: false, presentation: 'modal' }}
      />
    </Stack.Navigator>
  );
}

// Expenses stack
function ExpensesStack() {
  return (
    <Stack.Navigator screenOptions={stackScreenOptions}>
      <Stack.Screen
        name="ExpenseDashboard"
        component={ExpenseDashboardScreen}
        options={{ title: 'Expenses', headerShown: false }}
      />
      <Stack.Screen
        name="AddExpense"
        component={AddExpenseScreen}
        options={{ title: 'Add Expense', headerShown: false }}
      />
      <Stack.Screen
        name="AddLoad"
        component={AddLoadScreen}
        options={{ title: 'Add Load', headerShown: false }}
      />
    </Stack.Navigator>
  );
}

// Load Tracking stack
function TrackingStack() {
  return (
    <Stack.Navigator screenOptions={stackScreenOptions}>
      <Stack.Screen
        name="LoadTracking"
        component={LoadTrackingScreen}
        options={{ title: 'Load Tracking', headerShown: false }}
      />
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
          backgroundColor: COLORS.bg,
          borderTopColor: COLORS.borderLight,
          borderTopWidth: 1,
          height: 60,
          paddingBottom: 8,
        },
        tabBarActiveTintColor: COLORS.primary,
        tabBarInactiveTintColor: COLORS.tabInactive,
        tabBarIcon: ({ focused, color, size }) => {
          const icons = {
            Calc:      focused ? 'calculator'     : 'calculator-outline',
            Fuel:      focused ? 'flame'           : 'flame-outline',
            History:   focused ? 'time'            : 'time-outline',
            IFTA:      focused ? 'bar-chart'       : 'bar-chart-outline',
            Brokers:   focused ? 'shield'          : 'shield-outline',
            Documents: focused ? 'document-text'  : 'document-text-outline',
            Tracking:  focused ? 'location'        : 'location-outline',
            Expenses:  focused ? 'wallet'          : 'wallet-outline',
            Profile:   focused ? 'person'          : 'person-outline',
          };
          return <Ionicons name={icons[route.name] || 'ellipse'} size={size} color={color} />;
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
      })}
    >
      <Tab.Screen name="Calc"      component={CalcStack}      options={{ tabBarLabel: 'Route' }} />
      <Tab.Screen name="Fuel"      component={FuelStack}      options={{ tabBarLabel: 'Fuel' }} />
      <Tab.Screen name="History"   component={HistoryStack}   options={{ tabBarLabel: 'History' }} />
      <Tab.Screen name="IFTA"      component={IFTAStack}      options={{ tabBarLabel: 'IFTA' }} />
      <Tab.Screen name="Brokers"   component={BrokersStack}   options={{ tabBarLabel: 'Brokers' }} />
      <Tab.Screen name="Documents" component={DocumentsStack} options={{ tabBarLabel: 'Docs' }} />
      <Tab.Screen name="Tracking"  component={TrackingStack}  options={{ tabBarLabel: 'Tracking' }} />
      <Tab.Screen name="Expenses"  component={ExpensesStack}  options={{ tabBarLabel: 'Expenses' }} />
      <Tab.Screen name="Profile"   options={{ tabBarLabel: 'Profile' }}>
        {() => <ProfileScreen onLogout={handleLogout} />}
      </Tab.Screen>
    </Tab.Navigator>
  );
}

// Root navigator
export default function AppNavigator() {
  const [isLoggedIn, setIsLoggedIn] = useState(null);

  useEffect(() => {
    getToken().then((token) => setIsLoggedIn(!!token));
  }, []);

  if (isLoggedIn === null) {
    return (
      <View style={styles.splash}>
        <Text style={styles.splashLogo}>🛣️</Text>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 24 }} />
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
    backgroundColor: COLORS.bg,
    justifyContent: 'center',
    alignItems: 'center',
  },
  splashLogo: { fontSize: 72 },
});
