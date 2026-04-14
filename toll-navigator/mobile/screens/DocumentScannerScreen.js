import React, { useState, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  Alert, ActivityIndicator, Image, FlatList, Modal, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as Print from 'expo-print';
import * as Sharing from 'expo-sharing';
import * as FileSystem from 'expo-file-system';

import { processDocumentImage } from '../services/imageProcessor';
import {
  saveDocumentToHistory,
  generateDocumentId,
} from '../services/documentHistory';

const DOC_TYPES = [
  { value: 'BOL', label: 'BOL', icon: '📦', desc: 'Bill of Lading' },
  { value: 'POD', label: 'POD', icon: '✅', desc: 'Proof of Delivery' },
  { value: 'RATE', label: 'Rate Con', icon: '📄', desc: 'Rate Confirmation' },
  { value: 'OTHER', label: 'Other', icon: '📋', desc: 'Other Document' },
];

export default function DocumentScannerScreen({ navigation }) {
  const [pages, setPages] = useState([]); // [{uri, base64, processed}]
  const [docType, setDocType] = useState('BOL');
  const [processing, setProcessing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewIndex, setPreviewIndex] = useState(0);
  const [pdfUri, setPdfUri] = useState(null);

  // --- Камера ---
  const handleCamera = useCallback(async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Нет доступа к камере', 'Разреши доступ в настройках телефона.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.95,
      allowsEditing: false,
    });
    if (!result.canceled && result.assets?.[0]) {
      await addPage(result.assets[0].uri);
    }
  }, [pages]);

  // --- Галерея ---
  const handleGallery = useCallback(async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.95,
      allowsMultipleSelection: true,
      selectionLimit: 10,
    });
    if (!result.canceled && result.assets?.length > 0) {
      for (const asset of result.assets) {
        await addPage(asset.uri);
      }
    }
  }, [pages]);

  // --- Обработка и добавление страницы ---
  const addPage = async (uri) => {
    setProcessing(true);
    setPdfUri(null); // сбрасываем старый PDF при добавлении новой страницы
    try {
      const processed = await processDocumentImage(uri);
      setPages(prev => [...prev, {
        id: `page_${Date.now()}_${Math.random().toString(36).substr(2,5)}`,
        originalUri: uri,
        uri: processed.uri,
        base64: processed.base64,
        width: processed.width,
        height: processed.height,
      }]);
    } catch (e) {
      Alert.alert('Ошибка обработки', 'Не удалось обработать изображение. Попробуй ещё раз.');
      console.error('addPage error:', e);
    } finally {
      setProcessing(false);
    }
  };

  // --- Удалить страницу ---
  const removePage = (id) => {
    setPages(prev => prev.filter(p => p.id !== id));
    setPdfUri(null);
  };

  // --- Генерация PDF через expo-print ---
  const handleCreatePdf = async () => {
    if (pages.length === 0) {
      Alert.alert('Нет страниц', 'Добавь хотя бы одно фото документа.');
      return;
    }
    setGenerating(true);
    try {
      // Строим HTML с img тегами (base64)
      const pageHtml = pages.map((p, i) => `
        <div class="page" ${i > 0 ? 'style="page-break-before: always;"' : ''}>
          <img src="data:image/jpeg;base64,${p.base64}" style="width:100%; height:auto; display:block;" />
        </div>
      `).join('');

      const selectedType = DOC_TYPES.find(t => t.value === docType);
      const html = `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="UTF-8" />
          <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial, sans-serif; background: #fff; }
            .header {
              text-align: center;
              padding: 12px;
              border-bottom: 2px solid #333;
              margin-bottom: 16px;
            }
            .header h1 { font-size: 18px; color: #222; }
            .header p { font-size: 11px; color: #666; margin-top: 4px; }
            .page { width: 100%; padding: 0; }
            img { max-width: 100%; }
          </style>
        </head>
        <body>
          <div class="header">
            <h1>${selectedType?.icon} ${selectedType?.label} — ${selectedType?.desc}</h1>
            <p>Generated: ${new Date().toLocaleString('en-US')} | Pages: ${pages.length}</p>
          </div>
          ${pageHtml}
        </body>
        </html>
      `;

      const { uri } = await Print.printToFileAsync({ html, base64: false });
      setPdfUri(uri);
      Alert.alert(
        'PDF создан',
        `Документ готов (${pages.length} стр.). Нажми "Поделиться" чтобы отправить.`,
        [{ text: 'OK' }]
      );
    } catch (e) {
      Alert.alert('Ошибка генерации PDF', e.message || 'Попробуй ещё раз.');
      console.error('handleCreatePdf error:', e);
    } finally {
      setGenerating(false);
    }
  };

  // --- Поделиться PDF ---
  const handleShare = async () => {
    if (!pdfUri) {
      Alert.alert('Сначала создай PDF', 'Нажми кнопку "Создать PDF".');
      return;
    }
    try {
      const canShare = await Sharing.isAvailableAsync();
      if (!canShare) {
        Alert.alert('Шаринг недоступен', 'На этом устройстве нельзя поделиться файлами.');
        return;
      }

      // Сохраняем в историю перед шарингом
      const docId = generateDocumentId();
      const selectedType = DOC_TYPES.find(t => t.value === docType);

      // Копируем PDF в постоянное хранилище приложения
      const permanentPath = `${FileSystem.documentDirectory}documents/${docId}.pdf`;
      await FileSystem.makeDirectoryAsync(
        `${FileSystem.documentDirectory}documents/`,
        { intermediates: true }
      );
      await FileSystem.copyAsync({ from: pdfUri, to: permanentPath });

      await saveDocumentToHistory({
        id: docId,
        type: docType,
        typeLabel: selectedType?.label || docType,
        date: new Date().toISOString(),
        pdfUri: permanentPath,
        pages: pages.length,
      });

      await Sharing.shareAsync(permanentPath, {
        mimeType: 'application/pdf',
        dialogTitle: `Share ${selectedType?.label || docType}`,
        UTI: 'com.adobe.pdf',
      });
    } catch (e) {
      Alert.alert('Ошибка', e.message || 'Не удалось поделиться PDF.');
      console.error('handleShare error:', e);
    }
  };

  // --- Сброс ---
  const handleReset = () => {
    Alert.alert(
      'Очистить всё',
      'Удалить все добавленные страницы?',
      [
        { text: 'Отмена', style: 'cancel' },
        {
          text: 'Очистить',
          style: 'destructive',
          onPress: () => {
            setPages([]);
            setPdfUri(null);
          },
        },
      ]
    );
  };

  const selectedTypeInfo = DOC_TYPES.find(t => t.value === docType);

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">

        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>📄 Document Scanner</Text>
          <Text style={styles.subtitle}>BOL / POD / Rate Con — scan & share</Text>
        </View>

        {/* Тип документа */}
        <View style={styles.card}>
          <Text style={styles.sectionLabel}>DOCUMENT TYPE</Text>
          <View style={styles.docTypeRow}>
            {DOC_TYPES.map(t => (
              <TouchableOpacity
                key={t.value}
                style={[styles.docTypeBtn, docType === t.value && styles.docTypeBtnActive]}
                onPress={() => setDocType(t.value)}
              >
                <Text style={styles.docTypeIcon}>{t.icon}</Text>
                <Text style={[styles.docTypeLabel, docType === t.value && styles.docTypeLabelActive]}>
                  {t.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Кнопки съёмки */}
        <View style={styles.captureRow}>
          <TouchableOpacity
            style={[styles.captureBtn, styles.captureBtnCamera]}
            onPress={handleCamera}
            disabled={processing}
          >
            <Ionicons name="camera" size={24} color="#0d0d1a" />
            <Text style={styles.captureBtnText}>Camera</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.captureBtn, styles.captureBtnGallery]}
            onPress={handleGallery}
            disabled={processing}
          >
            <Ionicons name="images" size={24} color="#4fc3f7" />
            <Text style={[styles.captureBtnText, { color: '#4fc3f7' }]}>Gallery</Text>
          </TouchableOpacity>
        </View>

        {/* Индикатор обработки */}
        {processing && (
          <View style={styles.processingBanner}>
            <ActivityIndicator color="#4fc3f7" size="small" />
            <Text style={styles.processingText}>Processing image...</Text>
          </View>
        )}

        {/* Список страниц */}
        {pages.length > 0 && (
          <View style={styles.card}>
            <View style={styles.pagesHeader}>
              <Text style={styles.sectionLabel}>PAGES ({pages.length})</Text>
              <TouchableOpacity onPress={handleReset}>
                <Text style={styles.clearAllText}>Clear all</Text>
              </TouchableOpacity>
            </View>

            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.pagesScroll}>
              {pages.map((page, index) => (
                <View key={page.id} style={styles.pageThumb}>
                  <TouchableOpacity
                    onPress={() => { setPreviewIndex(index); setPreviewVisible(true); }}
                  >
                    <Image source={{ uri: page.uri }} style={styles.thumbImage} resizeMode="cover" />
                    <View style={styles.thumbOverlay}>
                      <Text style={styles.thumbNum}>{index + 1}</Text>
                    </View>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.thumbDelete}
                    onPress={() => removePage(page.id)}
                  >
                    <Ionicons name="close-circle" size={20} color="#ef9a9a" />
                  </TouchableOpacity>
                </View>
              ))}

              {/* Кнопка добавить ещё */}
              <TouchableOpacity style={styles.addMoreBtn} onPress={handleCamera} disabled={processing}>
                <Ionicons name="add-circle-outline" size={32} color="#4fc3f7" />
                <Text style={styles.addMoreText}>Add</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        )}

        {/* PDF статус */}
        {pdfUri && (
          <View style={styles.pdfReadyBanner}>
            <Ionicons name="checkmark-circle" size={20} color="#81c784" />
            <Text style={styles.pdfReadyText}>PDF ready — {pages.length} page{pages.length !== 1 ? 's' : ''}</Text>
          </View>
        )}

        {/* Действия */}
        <TouchableOpacity
          style={[styles.actionBtn, styles.actionBtnPrimary, (generating || pages.length === 0) && styles.actionBtnDisabled]}
          onPress={handleCreatePdf}
          disabled={generating || pages.length === 0}
        >
          {generating
            ? <ActivityIndicator color="#0d0d1a" />
            : <>
                <Ionicons name="document-text" size={20} color="#0d0d1a" />
                <Text style={styles.actionBtnTextDark}>Create PDF</Text>
              </>
          }
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionBtn, styles.actionBtnShare, !pdfUri && styles.actionBtnDisabled]}
          onPress={handleShare}
          disabled={!pdfUri}
        >
          <Ionicons name="share-outline" size={20} color={pdfUri ? '#4fc3f7' : '#555'} />
          <Text style={[styles.actionBtnText, !pdfUri && { color: '#555' }]}>
            Share PDF
          </Text>
        </TouchableOpacity>

        {/* История */}
        <TouchableOpacity
          style={styles.historyLink}
          onPress={() => navigation.navigate('DocumentHistory')}
        >
          <Ionicons name="time-outline" size={16} color="#888" />
          <Text style={styles.historyLinkText}>View scan history</Text>
        </TouchableOpacity>

        <Text style={styles.hint}>
          {selectedTypeInfo?.icon} {selectedTypeInfo?.label}: {selectedTypeInfo?.desc}
          {'\n'}Tap a thumbnail to preview • Share via Email, WhatsApp, Telegram, iMessage
        </Text>

      </ScrollView>

      {/* Превью модал */}
      <Modal visible={previewVisible} animationType="slide" statusBarTranslucent>
        <View style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Page {previewIndex + 1} of {pages.length}</Text>
            <TouchableOpacity onPress={() => setPreviewVisible(false)}>
              <Ionicons name="close" size={28} color="#fff" />
            </TouchableOpacity>
          </View>
          {pages[previewIndex] && (
            <Image
              source={{ uri: pages[previewIndex].uri }}
              style={styles.modalImage}
              resizeMode="contain"
            />
          )}
          <View style={styles.modalNav}>
            <TouchableOpacity
              style={[styles.navBtn, previewIndex === 0 && styles.navBtnDisabled]}
              onPress={() => setPreviewIndex(i => Math.max(0, i - 1))}
              disabled={previewIndex === 0}
            >
              <Ionicons name="chevron-back" size={24} color={previewIndex === 0 ? '#444' : '#4fc3f7'} />
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.navBtn, previewIndex === pages.length - 1 && styles.navBtnDisabled]}
              onPress={() => setPreviewIndex(i => Math.min(pages.length - 1, i + 1))}
              disabled={previewIndex === pages.length - 1}
            >
              <Ionicons name="chevron-forward" size={24} color={previewIndex === pages.length - 1 ? '#444' : '#4fc3f7'} />
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0d0d1a' },
  scroll: { padding: 20, paddingBottom: 40 },

  header: { alignItems: 'center', marginBottom: 24, marginTop: 10 },
  title: { fontSize: 24, fontWeight: '800', color: '#fff' },
  subtitle: { fontSize: 13, color: '#666', marginTop: 4 },

  card: {
    backgroundColor: '#161629',
    borderRadius: 14,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#1e1e3a',
  },
  sectionLabel: {
    color: '#666',
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 12,
  },

  // Тип документа
  docTypeRow: { flexDirection: 'row', gap: 8 },
  docTypeBtn: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: '#0d0d1a',
    borderWidth: 1,
    borderColor: '#2a2a4a',
  },
  docTypeBtnActive: { borderColor: '#4fc3f7', backgroundColor: '#0d1f2d' },
  docTypeIcon: { fontSize: 18, marginBottom: 3 },
  docTypeLabel: { color: '#666', fontSize: 11, fontWeight: '700' },
  docTypeLabelActive: { color: '#4fc3f7' },

  // Кнопки съёмки
  captureRow: { flexDirection: 'row', gap: 12, marginBottom: 14 },
  captureBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 14,
  },
  captureBtnCamera: { backgroundColor: '#4fc3f7' },
  captureBtnGallery: {
    backgroundColor: '#161629',
    borderWidth: 1,
    borderColor: '#4fc3f7',
  },
  captureBtnText: { fontSize: 16, fontWeight: '700', color: '#0d0d1a' },

  // Обработка
  processingBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#0d1f2d',
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#4fc3f7',
  },
  processingText: { color: '#4fc3f7', fontSize: 14, fontWeight: '600' },

  // Страницы
  pagesHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  clearAllText: { color: '#ef9a9a', fontSize: 12, fontWeight: '700' },
  pagesScroll: { flexDirection: 'row' },
  pageThumb: { marginRight: 10, position: 'relative' },
  thumbImage: { width: 80, height: 110, borderRadius: 8, backgroundColor: '#2a2a4a' },
  thumbOverlay: {
    position: 'absolute',
    bottom: 4,
    left: 4,
    backgroundColor: 'rgba(0,0,0,0.6)',
    borderRadius: 4,
    paddingHorizontal: 5,
    paddingVertical: 2,
  },
  thumbNum: { color: '#fff', fontSize: 11, fontWeight: '700' },
  thumbDelete: { position: 'absolute', top: -6, right: -6 },
  addMoreBtn: {
    width: 80,
    height: 110,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: '#2a2a4a',
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
  },
  addMoreText: { color: '#4fc3f7', fontSize: 11, marginTop: 4 },

  // PDF готов
  pdfReadyBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#0d1f18',
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#81c784',
  },
  pdfReadyText: { color: '#81c784', fontSize: 14, fontWeight: '600' },

  // Кнопки действий
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 14,
    marginBottom: 12,
  },
  actionBtnPrimary: { backgroundColor: '#4fc3f7' },
  actionBtnShare: {
    backgroundColor: '#161629',
    borderWidth: 1,
    borderColor: '#4fc3f7',
  },
  actionBtnDisabled: { opacity: 0.4 },
  actionBtnText: { color: '#4fc3f7', fontSize: 16, fontWeight: '700' },
  actionBtnTextDark: { color: '#0d0d1a', fontSize: 16, fontWeight: '700' },

  // История ссылка
  historyLink: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    marginBottom: 10,
  },
  historyLinkText: { color: '#888', fontSize: 13 },

  hint: { textAlign: 'center', color: '#444', fontSize: 12, lineHeight: 18 },

  // Модал превью
  modalContainer: { flex: 1, backgroundColor: '#000' },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    paddingTop: Platform.OS === 'ios' ? 50 : 20,
  },
  modalTitle: { color: '#fff', fontSize: 16, fontWeight: '700' },
  modalImage: { flex: 1, width: '100%' },
  modalNav: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 16,
    paddingBottom: Platform.OS === 'ios' ? 34 : 16,
  },
  navBtn: {
    backgroundColor: '#1a1a2e',
    borderRadius: 30,
    padding: 12,
    borderWidth: 1,
    borderColor: '#2a2a4a',
  },
  navBtnDisabled: { borderColor: '#1a1a2e' },
});
