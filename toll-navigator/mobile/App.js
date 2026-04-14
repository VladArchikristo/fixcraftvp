import React, { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import AppNavigator from './navigation/AppNavigator';
import { initExpenseDb } from './services/expenseService';

export default function App() {
  useEffect(() => {
    // Init SQLite expense/load tables at app start
    initExpenseDb().catch((err) =>
      console.warn('[ExpenseDB] Init failed:', err?.message)
    );
  }, []);

  return (
    <>
      <StatusBar style="light" />
      <AppNavigator />
    </>
  );
}
