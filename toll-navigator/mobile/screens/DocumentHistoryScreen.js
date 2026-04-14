import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  Alert, ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import * as Sharing from 'expo-sharing';
import * as FileSystem from 'expo-file-system';

import {
  getDocumentHistory,
  deleteDocumentFromHistory,
  clearDocumentHistory,
  formatDocumentDate,
} from '../services/documentHistory';

const TYPE_ICONS = { BOL: '📦', POD: '✅', RATE: '📄', OTHER: '📋' };
const TYPE_COLORS = {
  BOL: '#4fc3f7',
  POD: '#81c784',
  RATE: '#ffb74d',
  OTHER: '#ce93d8',
};

export default function DocumentHistoryScreen({ navigation }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  // Перезагружаем при каждом фокусе экрана
  useFocusEffect(
    useCallback(() => {
      loadHistory();
    }, [])
  );

  const loadHistory = async () => {
    setLoading(true);
    try {
      const items = await getDocumentHistory();
      setHistory(items);
    } catch (e) {
      console.error('loadHistory error:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleShare = async (item) => {
    try {
      // Проверяем что файл существует
      const info = await FileSystem.getInfoAsync(item.pdfUri);
      if (!info.exists) {
        Alert.alert('Файл не найден', 'PDF был удалён или недоступен.');
        return;
      }
      const canShare = await Sharing.isAvailableAsync();
      if (!canShare) {
        Alert.alert('Шаринг недоступен', 'На этом устройстве нельзя поделиться файлами.');
        return;
      }
      await Sharing.shareAsync(item.pdfUri, {
        mimeType: 'application/pdf',
        dialogTitle: `Share ${item.typeLabel || item.type}`,
        UTI: 'com.adobe.pdf',
      });
    } catch (e) {
      Alert.alert('Ошибка', e.message);
    }
  };

  const handleDelete = (item) => {
    Alert.alert(
      'Удалить документ',
      `Удалить ${item.typeLabel || item.type} из истории?`,
      [
        { text: 'Отмена', style: 'cancel' },
        {
          text: 'Удалить',
          style: 'destructive',
          onPress: async () => {
            try {
              // Удаляем PDF файл с диска
              const info = await FileSystem.getInfoAsync(item.pdfUri);
              if (info.exists) {
                await FileSystem.deleteAsync(item.pdfUri, { idempotent: true });
              }
              const updated = await deleteDocumentFromHistory(item.id);
              setHistory(updated);
            } catch (e) {
              Alert.alert('Ошибка удаления', e.message);
            }
          },
        },
      ]
    );
  };

  const handleClearAll = () => {
    if (history.length === 0) return;
    Alert.alert(
      'Очистить историю',
      'Удалить все отсканированные документы? Это действие необратимо.',
      [
        { text: 'Отмена', style: 'cancel' },
        {
          text: 'Очистить всё',
          style: 'destructive',
          onPress: async () => {
            try {
              // Удаляем все PDF файлы
              for (const item of history) {
                try {
                  await FileSystem.deleteAsync(item.pdfUri, { idempotent: true });
                } catch (_) {}
              }
              await clearDocumentHistory();
              setHistory([]);
            } catch (e) {
              Alert.alert('Ошибка', e.message);
            }
          },
        },
      ]
    );
  };

  const renderItem = ({ item }) => {
    const color = TYPE_COLORS[item.type] || '#4fc3f7';
    const icon = TYPE_ICONS[item.type] || '📋';

    return (
      <View style={styles.docCard}>
        <View style={[styles.docTypeTag, { backgroundColor: color + '22', borderColor: color }]}>
          <Text style={styles.docTypeTagIcon}>{icon}</Text>
          <Text style={[styles.docTypeTagLabel, { color }]}>{item.typeLabel || item.type}</Text>
        </View>

        <View style={styles.docInfo}>
          <Text style={styles.docDate}>{formatDocumentDate(item.date)}</Text>
          <Text style={styles.docPages}>{item.pages} page{item.pages !== 1 ? 's' : ''}</Text>
        </View>

        <View style={styles.docActions}>
          <TouchableOpacity
            style={styles.docActionBtn}
            onPress={() => handleShare(item)}
          >
            <Ionicons name="share-outline" size={20} color="#4fc3f7" />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.docActionBtn, styles.docActionBtnDelete]}
            onPress={() => handleDelete(item)}
          >
            <Ionicons name="trash-outline" size={18} color="#ef9a9a" />
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Ionicons name="arrow-back" size={22} color="#4fc3f7" />
        </TouchableOpacity>
        <Text style={styles.title}>Scan History</Text>
        {history.length > 0 && (
          <TouchableOpacity onPress={handleClearAll}>
            <Text style={styles.clearAllBtn}>Clear all</Text>
          </TouchableOpacity>
        )}
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#4fc3f7" />
        </View>
      ) : history.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyIcon}>📂</Text>
          <Text style={styles.emptyTitle}>No documents yet</Text>
          <Text style={styles.emptySubtitle}>
            Scan your first BOL or POD to see it here
          </Text>
          <TouchableOpacity
            style={styles.scanNowBtn}
            onPress={() => navigation.goBack()}
          >
            <Ionicons name="camera" size={18} color="#0d0d1a" />
            <Text style={styles.scanNowText}>Scan Document</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={history}
          keyExtractor={item => item.id}
          renderItem={renderItem}
          contentContainerStyle={styles.list}
          ItemSeparatorComponent={() => <View style={styles.separator} />}
          showsVerticalScrollIndicator={false}
        />
      )}

      {/* FAB — новое сканирование */}
      {history.length > 0 && (
        <TouchableOpacity
          style={styles.fab}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="camera" size={24} color="#0d0d1a" />
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 54,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1e1e3a',
  },
  backBtn: { padding: 4, marginRight: 12 },
  title: { flex: 1, color: '#fff', fontSize: 20, fontWeight: '800' },
  clearAllBtn: { color: '#ef9a9a', fontSize: 13, fontWeight: '700' },

  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },

  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  emptyIcon: { fontSize: 56, marginBottom: 16 },
  emptyTitle: { color: '#fff', fontSize: 20, fontWeight: '800', marginBottom: 8 },
  emptySubtitle: { color: '#666', fontSize: 14, textAlign: 'center', marginBottom: 28, lineHeight: 20 },
  scanNowBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#4fc3f7',
    borderRadius: 12,
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  scanNowText: { color: '#0d0d1a', fontSize: 15, fontWeight: '800' },

  list: { padding: 16 },
  separator: { height: 1, backgroundColor: '#1e1e3a', marginVertical: 2 },

  docCard: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    gap: 12,
  },
  docTypeTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    minWidth: 70,
  },
  docTypeTagIcon: { fontSize: 14 },
  docTypeTagLabel: { fontSize: 12, fontWeight: '800' },

  docInfo: { flex: 1 },
  docDate: { color: '#ccc', fontSize: 13, fontWeight: '600', marginBottom: 3 },
  docPages: { color: '#666', fontSize: 12 },

  docActions: { flexDirection: 'row', gap: 6 },
  docActionBtn: {
    backgroundColor: '#161629',
    borderRadius: 8,
    padding: 8,
    borderWidth: 1,
    borderColor: '#2a2a4a',
  },
  docActionBtnDelete: { borderColor: '#3a1a1a', backgroundColor: '#1a0d0d' },

  fab: {
    position: 'absolute',
    bottom: 30,
    right: 24,
    backgroundColor: '#4fc3f7',
    borderRadius: 30,
    width: 56,
    height: 56,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#4fc3f7',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 8,
  },
});
