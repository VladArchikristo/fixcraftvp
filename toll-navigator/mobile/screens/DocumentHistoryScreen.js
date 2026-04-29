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
import { COLORS, FONTS, SPACING, RADIUS, SHARED } from '../theme';

const TYPE_ICONS = { BOL: '📦', POD: '✅', RATE: '📄', OTHER: '📋' };
const TYPE_COLORS = {
  BOL: COLORS.primary,
  POD: COLORS.success,
  RATE: COLORS.warning,
  OTHER: '#9C27B0',
};

export default function DocumentHistoryScreen({ navigation }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  // Reload on every screen focus
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
      // Check if file exists
      const info = await FileSystem.getInfoAsync(item.pdfUri);
      if (!info.exists) {
        Alert.alert('File Not Found', 'PDF was deleted or unavailable.');
        return;
      }
      const canShare = await Sharing.isAvailableAsync();
      if (!canShare) {
        Alert.alert('Sharing Unavailable', 'File sharing is not available on this device.');
        return;
      }
      await Sharing.shareAsync(item.pdfUri, {
        mimeType: 'application/pdf',
        dialogTitle: `Share ${item.typeLabel || item.type}`,
        UTI: 'com.adobe.pdf',
      });
    } catch (e) {
      Alert.alert('Error', e.message);
    }
  };

  const handleDelete = (item) => {
    Alert.alert(
      'Delete Document',
      `Delete ${item.typeLabel || item.type} from history?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              // Delete PDF file from disk
              const info = await FileSystem.getInfoAsync(item.pdfUri);
              if (info.exists) {
                await FileSystem.deleteAsync(item.pdfUri, { idempotent: true });
              }
              const updated = await deleteDocumentFromHistory(item.id);
              setHistory(updated);
            } catch (e) {
              Alert.alert('Delete Error', e.message);
            }
          },
        },
      ]
    );
  };

  const handleClearAll = () => {
    if (history.length === 0) return;
    Alert.alert(
      'Clear History',
      'Delete all scanned documents? This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear All',
          style: 'destructive',
          onPress: async () => {
            try {
              // Delete all PDF files
              for (const item of history) {
                try {
                  await FileSystem.deleteAsync(item.pdfUri, { idempotent: true });
                } catch (_) {}
              }
              await clearDocumentHistory();
              setHistory([]);
            } catch (e) {
              Alert.alert('Error', e.message);
            }
          },
        },
      ]
    );
  };

  const renderItem = ({ item }) => {
    const color = TYPE_COLORS[item.type] || COLORS.primary;
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
            <Ionicons name="share-outline" size={20} color={COLORS.primary} />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.docActionBtn, styles.docActionBtnDelete]}
            onPress={() => handleDelete(item)}
          >
            <Ionicons name="trash-outline" size={18} color={COLORS.error} />
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
          <Ionicons name="arrow-back" size={22} color={COLORS.primary} />
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
          <ActivityIndicator size="large" color={COLORS.primary} />
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
            <Ionicons name="camera" size={18} color={COLORS.textInverse} />
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

      {/* FAB — new scan */}
      {history.length > 0 && (
        <TouchableOpacity
          style={styles.fab}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="camera" size={24} color={COLORS.textInverse} />
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: SPACING.md,
    paddingTop: 54,
    paddingBottom: SPACING.md,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.bgCardAlt,
  },
  backBtn: { padding: SPACING.xs, marginRight: 12 },
  title: { flex: 1, color: COLORS.textPrimary, fontSize: 20, fontWeight: '800' },
  clearAllBtn: { color: COLORS.error, fontSize: 13, fontWeight: '700' },

  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },

  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  emptyIcon: { fontSize: 56, marginBottom: SPACING.md },
  emptyTitle: { color: COLORS.textPrimary, fontSize: 20, fontWeight: '800', marginBottom: SPACING.sm },
  emptySubtitle: { color: COLORS.textMuted, fontSize: 14, textAlign: 'center', marginBottom: 28, lineHeight: 20 },
  scanNowBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
    backgroundColor: COLORS.accent,
    borderRadius: RADIUS.md,
    paddingHorizontal: SPACING.lg,
    paddingVertical: 12,
  },
  scanNowText: { color: COLORS.textInverse, fontSize: 15, fontWeight: '800' },

  list: { padding: SPACING.md },
  separator: { height: 1, backgroundColor: COLORS.bgCardAlt, marginVertical: 2 },

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
    borderRadius: RADIUS.sm,
    borderWidth: 1,
    minWidth: 70,
  },
  docTypeTagIcon: { fontSize: 14 },
  docTypeTagLabel: { fontSize: 12, fontWeight: '800' },

  docInfo: { flex: 1 },
  docDate: { color: COLORS.textSecondary, fontSize: 13, fontWeight: '600', marginBottom: 3 },
  docPages: { color: COLORS.textMuted, fontSize: 12 },

  docActions: { flexDirection: 'row', gap: 6 },
  docActionBtn: {
    backgroundColor: COLORS.bgCard,
    borderRadius: RADIUS.sm,
    padding: SPACING.sm,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  docActionBtnDelete: { borderColor: COLORS.error, backgroundColor: COLORS.errorLight },

  fab: {
    position: 'absolute',
    bottom: 30,
    right: 24,
    backgroundColor: COLORS.accent,
    borderRadius: RADIUS.full,
    width: 56,
    height: 56,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: COLORS.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 8,
  },
});
