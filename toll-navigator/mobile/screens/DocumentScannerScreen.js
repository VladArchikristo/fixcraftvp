/**
 * DocumentScannerScreen — main scanner hub
 * After capture → opens ImageEditScreen (CamScanner-style crop/filter/rotate)
 * Then generates PDF with per-page CSS filters applied
 */
import React, { useState, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  Alert, ActivityIndicator, Image, Modal, Platform, Share,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as Print from 'expo-print';
import * as Sharing from 'expo-sharing';
import * as FileSystem from 'expo-file-system';

import {
  saveDocumentToHistory,
  generateDocumentId,
} from '../services/documentHistory';
import { extractTextFromBase64, isMlKitAvailable, OCR_SOURCE } from '../services/ocrService';

const DOC_TYPES = [
  { value: 'BOL',   label: 'BOL',      icon: '📦', desc: 'Bill of Lading' },
  { value: 'POD',   label: 'POD',      icon: '✅', desc: 'Proof of Delivery' },
  { value: 'RATE',  label: 'Rate Con', icon: '📄', desc: 'Rate Confirmation' },
  { value: 'OTHER', label: 'Other',    icon: '📋', desc: 'Other Document' },
];

export default function DocumentScannerScreen({ navigation }) {
  const [pages, setPages]         = useState([]); // [{id, uri, base64, cssFilter, filter}]
  const [docType, setDocType]     = useState('BOL');
  const [generating, setGenerating] = useState(false);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewIndex, setPreviewIndex]     = useState(0);
  const [pdfUri, setPdfUri]       = useState(null);

  // OCR state
  const [ocrLoading, setOcrLoading]   = useState(false);
  const [ocrText, setOcrText]         = useState('');
  const [ocrMock, setOcrMock]         = useState(false);
  const [ocrSource, setOcrSource]     = useState(null); // 'mlkit' | 'api' | 'fallback'
  const [ocrModalVisible, setOcrModalVisible] = useState(false);
  const [ocrPageIndex, setOcrPageIndex] = useState(0);

  // --- Open CamScanner-style editor ---
  const openEditor = useCallback((asset) => {
    navigation.navigate('ImageEdit', {
      imageUri:    asset.uri,
      imageWidth:  asset.width  || 0,
      imageHeight: asset.height || 0,
      onConfirm: (edited) => {
        setPdfUri(null);
        setPages(prev => [...prev, {
          id:        `page_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
          originalUri: asset.uri,
          uri:       edited.uri,
          base64:    edited.base64,
          width:     edited.width,
          height:    edited.height,
          filter:    edited.filter    || 'color',
          cssFilter: edited.cssFilter || 'none',
        }]);
      },
    });
  }, [navigation]);

  // --- Camera ---
  const handleCamera = useCallback(async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('No camera access', 'Allow camera access in phone Settings.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.95,
      allowsEditing: false,
    });
    if (!result.canceled && result.assets?.[0]) {
      openEditor(result.assets[0]);
    }
  }, [openEditor]);

  // --- Gallery ---
  const handleGallery = useCallback(async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.95,
      allowsMultipleSelection: true,
      selectionLimit: 10,
    });
    if (!result.canceled && result.assets?.length > 0) {
      for (const asset of result.assets) {
        openEditor(asset);
      }
    }
  }, [openEditor]);

  // --- Remove page ---
  const removePage = (id) => {
    setPages(prev => prev.filter(p => p.id !== id));
    setPdfUri(null);
  };

  // --- Generate PDF (with per-page CSS filters!) ---
  const handleCreatePdf = async () => {
    if (pages.length === 0) {
      Alert.alert('No pages', 'Add at least one scanned document page.');
      return;
    }
    setGenerating(true);
    try {
      const pageHtml = pages.map((p, i) => {
        const filterStyle = p.cssFilter && p.cssFilter !== 'none'
          ? `filter: ${p.cssFilter};`
          : '';
        return `
          <div class="page" ${i > 0 ? 'style="page-break-before: always;"' : ''}>
            <img src="data:image/jpeg;base64,${p.base64}"
                 style="width:100%; height:auto; display:block; ${filterStyle}" />
          </div>
        `;
      }).join('');

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
            .header p  { font-size: 11px; color: #666; margin-top: 4px; }
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
        'PDF created ✅',
        `Document ready (${pages.length} page${pages.length !== 1 ? 's' : ''}). Tap Share to send.`,
        [{ text: 'OK' }]
      );
    } catch (e) {
      Alert.alert('PDF generation error', e.message || 'Try again.');
      console.error('handleCreatePdf error:', e);
    } finally {
      setGenerating(false);
    }
  };

  // --- Share PDF ---
  const handleShare = async () => {
    if (!pdfUri) {
      Alert.alert('Create PDF first', 'Tap "Create PDF" button first.');
      return;
    }
    try {
      const canShare = await Sharing.isAvailableAsync();
      if (!canShare) {
        Alert.alert('Sharing unavailable', 'File sharing not supported on this device.');
        return;
      }

      const docId = generateDocumentId();
      const selectedType = DOC_TYPES.find(t => t.value === docType);
      const permanentPath = `${FileSystem.documentDirectory}documents/${docId}.pdf`;
      await FileSystem.makeDirectoryAsync(
        `${FileSystem.documentDirectory}documents/`,
        { intermediates: true }
      );
      await FileSystem.copyAsync({ from: pdfUri, to: permanentPath });

      await saveDocumentToHistory({
        id:        docId,
        type:      docType,
        typeLabel: selectedType?.label || docType,
        date:      new Date().toISOString(),
        pdfUri:    permanentPath,
        pages:     pages.length,
      });

      await Sharing.shareAsync(permanentPath, {
        mimeType:    'application/pdf',
        dialogTitle: `Send document — ${selectedType?.label || docType}`,
        UTI:         'com.adobe.pdf',
      });
    } catch (e) {
      Alert.alert('Error', e.message || 'Could not share PDF.');
      console.error('handleShare error:', e);
    }
  };

  // --- OCR: extract text from a page (offline-first via ML Kit) ---
  const handleOCR = useCallback(async (pageIndex = 0) => {
    const page = pages[pageIndex];
    if (!page?.base64) {
      Alert.alert('No page', 'Scan a document first.');
      return;
    }
    setOcrPageIndex(pageIndex);
    setOcrLoading(true);
    try {
      const result = await extractTextFromBase64(page.base64);
      setOcrText(result.text || '(no text detected)');
      setOcrMock(result.mock || false);
      setOcrSource(result.source || null);
      setOcrModalVisible(true);
    } catch (e) {
      Alert.alert('OCR Error', 'Could not extract text.');
      console.error('handleOCR error:', e);
    } finally {
      setOcrLoading(false);
    }
  }, [pages]);

  const handleShareOcrText = async () => {
    try {
      await Share.share({ message: ocrText, title: 'Extracted Text' });
    } catch (e) {
      console.error('share OCR text error:', e);
    }
  };

  // --- Reset ---
  const handleReset = () => {
    Alert.alert(
      'Clear all',
      'Remove all scanned pages?',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Clear', style: 'destructive', onPress: () => { setPages([]); setPdfUri(null); } },
      ]
    );
  };

  const selectedTypeInfo = DOC_TYPES.find(t => t.value === docType);

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">

        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>📷 Document Scanner</Text>
          <Text style={styles.subtitle}>Crop · Filter · PDF · Share</Text>
        </View>

        {/* Document type selector */}
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

        {/* Capture buttons */}
        <View style={styles.captureRow}>
          <TouchableOpacity
            style={[styles.captureBtn, styles.captureBtnCamera]}
            onPress={handleCamera}
          >
            <Ionicons name="camera" size={24} color="#0d0d1a" />
            <Text style={styles.captureBtnText}>Camera</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.captureBtn, styles.captureBtnGallery]}
            onPress={handleGallery}
          >
            <Ionicons name="images" size={24} color="#4fc3f7" />
            <Text style={[styles.captureBtnText, { color: '#4fc3f7' }]}>Gallery</Text>
          </TouchableOpacity>
        </View>

        {/* CamScanner hint */}
        <View style={styles.featureHint}>
          <Text style={styles.featureHintText}>
            ✂️ Crop  ·  🎨 Filters  ·  🔄 Rotate  ·  📐 Rule of thirds
          </Text>
        </View>

        {/* Page thumbnails */}
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
                    {/* Filter badge */}
                    {page.filter && page.filter !== 'color' && (
                      <View style={styles.filterBadge}>
                        <Text style={styles.filterBadgeText}>
                          {page.filter === 'magic' ? '✨' : page.filter === 'grayscale' ? '🌫️' : '◾'}
                        </Text>
                      </View>
                    )}
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.thumbDelete} onPress={() => removePage(page.id)}>
                    <Ionicons name="close-circle" size={20} color="#ef9a9a" />
                  </TouchableOpacity>
                </View>
              ))}

              {/* Add more */}
              <TouchableOpacity style={styles.addMoreBtn} onPress={handleCamera}>
                <Ionicons name="add-circle-outline" size={32} color="#4fc3f7" />
                <Text style={styles.addMoreText}>Add</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        )}

        {/* PDF ready */}
        {pdfUri && (
          <View style={styles.pdfReadyBanner}>
            <Ionicons name="checkmark-circle" size={20} color="#81c784" />
            <Text style={styles.pdfReadyText}>
              PDF ready — {pages.length} page{pages.length !== 1 ? 's' : ''}
            </Text>
          </View>
        )}

        {/* Actions */}
        <TouchableOpacity
          style={[styles.actionBtn, styles.actionBtnPrimary,
            (generating || pages.length === 0) && styles.actionBtnDisabled]}
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

        {/* OCR Button */}
        <TouchableOpacity
          style={[styles.actionBtn, styles.actionBtnOcr,
            (ocrLoading || pages.length === 0) && styles.actionBtnDisabled]}
          onPress={() => {
            if (pages.length === 1) {
              handleOCR(0);
            } else {
              // Show page selection via alert
              const opts = pages.map((_, i) => ({
                text: `Page ${i + 1}`,
                onPress: () => handleOCR(i),
              }));
              opts.push({ text: 'Cancel', style: 'cancel' });
              Alert.alert('Extract Text — Select Page', 'Which page to scan?', opts);
            }
          }}
          disabled={ocrLoading || pages.length === 0}
        >
          {ocrLoading
            ? <ActivityIndicator color="#a5d6a7" />
            : <>
                <Ionicons name="text-outline" size={20} color={pages.length > 0 ? '#a5d6a7' : '#555'} />
                <Text style={[styles.actionBtnText,
                  { color: pages.length > 0 ? '#a5d6a7' : '#555' }]}>
                  Extract Text {isMlKitAvailable() ? '(Offline OCR)' : '(OCR)'}
                </Text>
              </>
          }
        </TouchableOpacity>

        {/* History link */}
        <TouchableOpacity
          style={styles.historyLink}
          onPress={() => navigation.navigate('DocumentHistory')}
        >
          <Ionicons name="time-outline" size={16} color="#888" />
          <Text style={styles.historyLinkText}>View scan history</Text>
        </TouchableOpacity>

        <Text style={styles.hint}>
          {selectedTypeInfo?.icon} {selectedTypeInfo?.label}: {selectedTypeInfo?.desc}
          {'\n'}Tap thumbnail to preview · Share via AirDrop, Email, WhatsApp and more
        </Text>
      </ScrollView>

      {/* OCR Modal */}
      <Modal visible={ocrModalVisible} animationType="slide" statusBarTranslucent>
        <View style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <View style={{ flex: 1 }}>
              <Text style={styles.modalTitle}>
                📝 Extracted Text — Page {ocrPageIndex + 1}
              </Text>
              <View style={styles.ocrBadgeRow}>
                {ocrSource === OCR_SOURCE.ML_KIT && (
                  <View style={[styles.ocrSourceBadge, styles.ocrSourceBadgeOffline]}>
                    <Ionicons name="phone-portrait-outline" size={10} color="#81c784" />
                    <Text style={[styles.ocrSourceText, { color: '#81c784' }]}>On-device · Offline</Text>
                  </View>
                )}
                {ocrSource === OCR_SOURCE.API && (
                  <View style={[styles.ocrSourceBadge, styles.ocrSourceBadgeApi]}>
                    <Ionicons name="cloud-outline" size={10} color="#4fc3f7" />
                    <Text style={[styles.ocrSourceText, { color: '#4fc3f7' }]}>Cloud API</Text>
                  </View>
                )}
                {ocrMock && (
                  <View style={[styles.ocrSourceBadge, { borderColor: '#ffb74d' }]}>
                    <Text style={[styles.ocrSourceText, { color: '#ffb74d' }]}>⚠️ Demo</Text>
                  </View>
                )}
              </View>
            </View>
            <TouchableOpacity onPress={() => setOcrModalVisible(false)}>
              <Ionicons name="close" size={28} color="#fff" />
            </TouchableOpacity>
          </View>
          <ScrollView style={styles.ocrScroll} contentContainerStyle={styles.ocrScrollContent}>
            <Text style={styles.ocrText} selectable>{ocrText}</Text>
          </ScrollView>
          <View style={styles.ocrActions}>
            <TouchableOpacity style={styles.ocrShareBtn} onPress={handleShareOcrText}>
              <Ionicons name="share-outline" size={18} color="#0d0d1a" />
              <Text style={styles.ocrShareBtnText}>Share Text</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Preview modal */}
      <Modal visible={previewVisible} animationType="slide" statusBarTranslucent>
        <View style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>
              Page {previewIndex + 1} of {pages.length}
              {pages[previewIndex]?.filter && pages[previewIndex].filter !== 'color'
                ? `  ·  ${pages[previewIndex].filter}` : ''}
            </Text>
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
  title:    { fontSize: 24, fontWeight: '800', color: '#fff' },
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
    color: '#666', fontSize: 11, fontWeight: '700',
    textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12,
  },

  docTypeRow: { flexDirection: 'row', gap: 8 },
  docTypeBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 10,
    borderRadius: 10, backgroundColor: '#0d0d1a',
    borderWidth: 1, borderColor: '#2a2a4a',
  },
  docTypeBtnActive: { borderColor: '#4fc3f7', backgroundColor: '#0d1f2d' },
  docTypeIcon:  { fontSize: 18, marginBottom: 3 },
  docTypeLabel: { color: '#666', fontSize: 11, fontWeight: '700' },
  docTypeLabelActive: { color: '#4fc3f7' },

  captureRow: { flexDirection: 'row', gap: 12, marginBottom: 10 },
  captureBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center',
    justifyContent: 'center', gap: 8, paddingVertical: 14, borderRadius: 14,
  },
  captureBtnCamera:  { backgroundColor: '#4fc3f7' },
  captureBtnGallery: { backgroundColor: '#161629', borderWidth: 1, borderColor: '#4fc3f7' },
  captureBtnText:    { fontSize: 16, fontWeight: '700', color: '#0d0d1a' },

  featureHint: {
    backgroundColor: '#0d1a2a',
    borderRadius: 10,
    padding: 10,
    marginBottom: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#1a3a5a',
  },
  featureHintText: { color: '#4fc3f7', fontSize: 12, fontWeight: '600' },

  pagesHeader: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 12,
  },
  clearAllText: { color: '#ef9a9a', fontSize: 12, fontWeight: '700' },
  pagesScroll:  { flexDirection: 'row' },

  pageThumb: { marginRight: 10, position: 'relative' },
  thumbImage: { width: 80, height: 110, borderRadius: 8, backgroundColor: '#2a2a4a' },
  thumbOverlay: {
    position: 'absolute', bottom: 4, left: 4,
    backgroundColor: 'rgba(0,0,0,0.6)', borderRadius: 4,
    paddingHorizontal: 5, paddingVertical: 2,
  },
  thumbNum: { color: '#fff', fontSize: 11, fontWeight: '700' },
  filterBadge: {
    position: 'absolute', top: 4, right: 4,
    backgroundColor: 'rgba(0,0,0,0.65)', borderRadius: 4,
    paddingHorizontal: 3, paddingVertical: 1,
  },
  filterBadgeText: { fontSize: 10 },
  thumbDelete: { position: 'absolute', top: -6, right: -6 },

  addMoreBtn: {
    width: 80, height: 110, borderRadius: 8,
    borderWidth: 2, borderColor: '#2a2a4a', borderStyle: 'dashed',
    alignItems: 'center', justifyContent: 'center',
  },
  addMoreText: { color: '#4fc3f7', fontSize: 11, marginTop: 4 },

  pdfReadyBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: '#0d1f18', borderRadius: 10, padding: 12,
    marginBottom: 14, borderWidth: 1, borderColor: '#81c784',
  },
  pdfReadyText: { color: '#81c784', fontSize: 14, fontWeight: '600' },

  actionBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, paddingVertical: 14, borderRadius: 14, marginBottom: 12,
  },
  actionBtnPrimary: { backgroundColor: '#4fc3f7' },
  actionBtnShare:   { backgroundColor: '#161629', borderWidth: 1, borderColor: '#4fc3f7' },
  actionBtnOcr:     { backgroundColor: '#161629', borderWidth: 1, borderColor: '#a5d6a7' },
  actionBtnDisabled: { opacity: 0.4 },
  actionBtnText:     { color: '#4fc3f7', fontSize: 16, fontWeight: '700' },
  actionBtnTextDark: { color: '#0d0d1a', fontSize: 16, fontWeight: '700' },

  ocrMockBadge: { color: '#ffb74d', fontSize: 11, marginTop: 2 },
  ocrBadgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 },
  ocrSourceBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    borderWidth: 1, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2,
  },
  ocrSourceBadgeOffline: { borderColor: '#81c784', backgroundColor: 'rgba(129,199,132,0.1)' },
  ocrSourceBadgeApi:     { borderColor: '#4fc3f7', backgroundColor: 'rgba(79,195,247,0.1)' },
  ocrSourceText: { fontSize: 10, fontWeight: '600' },
  ocrScroll:    { flex: 1 },
  ocrScrollContent: { padding: 20 },
  ocrText: {
    color: '#e0e0e0', fontSize: 14, lineHeight: 22,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  ocrActions: {
    padding: 16,
    paddingBottom: Platform.OS === 'ios' ? 34 : 16,
    borderTopWidth: 1, borderTopColor: '#222',
  },
  ocrShareBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, backgroundColor: '#a5d6a7', borderRadius: 12, paddingVertical: 14,
  },
  ocrShareBtnText: { color: '#0d0d1a', fontSize: 16, fontWeight: '700' },

  historyLink: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingVertical: 10, marginBottom: 10,
  },
  historyLinkText: { color: '#888', fontSize: 13 },
  hint: { textAlign: 'center', color: '#444', fontSize: 12, lineHeight: 18 },

  modalContainer: { flex: 1, backgroundColor: '#000' },
  modalHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 16, paddingTop: Platform.OS === 'ios' ? 50 : 20,
  },
  modalTitle: { color: '#fff', fontSize: 16, fontWeight: '700' },
  modalImage: { flex: 1, width: '100%' },
  modalNav: {
    flexDirection: 'row', justifyContent: 'space-between',
    padding: 16, paddingBottom: Platform.OS === 'ios' ? 34 : 16,
  },
  navBtn: {
    backgroundColor: '#1a1a2e', borderRadius: 30, padding: 12,
    borderWidth: 1, borderColor: '#2a2a4a',
  },
  navBtnDisabled: { borderColor: '#1a1a2e' },
});
