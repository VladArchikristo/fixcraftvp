/**
 * ImageEditScreen — CamScanner-style document editor
 * Features: 4-corner crop handles, 4 filters, rotation (L/R), rule-of-thirds grid
 */
import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Image,
  PanResponder, Dimensions, Platform, StatusBar,
  ActivityIndicator, SafeAreaView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImageManipulator from 'expo-image-manipulator';
import * as FileSystem from 'expo-file-system';
import { detectEdges } from '../services/api';
import { COLORS, FONTS, SPACING, RADIUS, SHARED } from '../theme';

const { width: SCREEN_W } = Dimensions.get('window');

// CSS filters for PDF output
export const FILTERS = [
  { id: 'color',     label: 'Color',   icon: '🎨', css: 'none' },
  { id: 'magic',     label: 'Magic',   icon: '✨', css: 'contrast(1.35) brightness(1.05) saturate(1.2)' },
  { id: 'grayscale', label: 'Gray',    icon: '🌫️', css: 'grayscale(100%) contrast(1.15)' },
  { id: 'bw',        label: 'B&W',     icon: '◾',  css: 'grayscale(100%) contrast(2.4) brightness(1.1)' },
];

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const HANDLE_SIZE = 40; // touch target

/** Returns actual render bounds of image inside resizeMode="contain" container */
function getImageRenderBounds(imgW, imgH, cW, cH) {
  if (!imgW || !imgH || !cW || !cH) {
    return { renderW: cW || SCREEN_W, renderH: cH || 500, offsetX: 0, offsetY: 0 };
  }
  const cRatio = cW / cH;
  const iRatio = imgW / imgH;
  let renderW, renderH, offsetX, offsetY;
  if (iRatio > cRatio) {
    renderW = cW;
    renderH = cW / iRatio;
    offsetX = 0;
    offsetY = (cH - renderH) / 2;
  } else {
    renderH = cH;
    renderW = cH * iRatio;
    offsetX = (cW - renderW) / 2;
    offsetY = 0;
  }
  return { renderW, renderH, offsetX, offsetY };
}

export default function ImageEditScreen({ route, navigation }) {
  const { imageUri: initUri, imageWidth: initW, imageHeight: initH, onConfirm } = route.params;

  const [uri, setUri] = useState(initUri);
  const [imgSize, setImgSize] = useState({ w: initW || 0, h: initH || 0 });
  const [filter, setFilter] = useState('color');
  const [rotating, setRotating] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [container, setContainer] = useState({ width: SCREEN_W, height: 500 });
  const [autoDetecting, setAutoDetecting] = useState(false);
  const [edgeDetected, setEdgeDetected] = useState(false);

  // Get image size if not provided
  useEffect(() => {
    if (!initW || !initH) {
      Image.getSize(initUri, (w, h) => setImgSize({ w, h }), () => {});
    }
  }, [initUri, initW, initH]);

  // Auto edge detection on image load
  useEffect(() => {
    let cancelled = false;
    const runDetection = async () => {
      setAutoDetecting(true);
      try {
        const b64 = await FileSystem.readAsStringAsync(initUri, {
          encoding: FileSystem.EncodingType.Base64,
        });
        const res = await detectEdges(b64);
        if (cancelled) return;
        const corners = res.data?.corners;
        if (Array.isArray(corners) && corners.length === 4) {
          // corners: [tl, tr, br, bl] each {x, y} in [0..1]
          const [tl, tr, br, bl] = corners;
          const x  = Math.min(tl.x, bl.x);
          const y  = Math.min(tl.y, tr.y);
          const x2 = Math.max(tr.x, br.x);
          const y2 = Math.max(bl.y, br.y);
          const w  = Math.max(0.1, x2 - x);
          const h  = Math.max(0.1, y2 - y);
          setCropBox({ x, y, w, h });
          if (res.data.detected) setEdgeDetected(true);
        }
      } catch (e) {
        // Silently fall back to default crop — user can adjust manually
        console.log('[EdgeDetection] failed:', e.message);
      } finally {
        if (!cancelled) setAutoDetecting(false);
      }
    };
    runDetection();
    return () => { cancelled = true; };
  }, [initUri]); // eslint-disable-line react-hooks/exhaustive-deps

  // Crop box as fractions [0..1] of image render bounds
  const [cropBox, setCropBoxState] = useState({ x: 0.04, y: 0.04, w: 0.92, h: 0.92 });
  const cropRef = useRef({ x: 0.04, y: 0.04, w: 0.92, h: 0.92 });
  const setCropBox = useCallback((cb) => {
    cropRef.current = cb;
    setCropBoxState(cb);
  }, []);

  const boundsRef = useRef({ renderW: 1, renderH: 1, offsetX: 0, offsetY: 0 });
  const imgSizeRef = useRef(imgSize);
  imgSizeRef.current = imgSize;

  const bounds = getImageRenderBounds(imgSize.w, imgSize.h, container.width, container.height);
  boundsRef.current = bounds;

  // Corner drag state
  const cornerStarts = useRef({});

  const makePan = useCallback((corner) => PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: () => {
      cornerStarts.current[corner] = { ...cropRef.current };
    },
    onPanResponderMove: (_, gs) => {
      const start = cornerStarts.current[corner];
      if (!start) return;
      const b = boundsRef.current;
      const dxF = gs.dx / b.renderW;
      const dyF = gs.dy / b.renderH;
      const { x, y, w, h } = start;
      let nx = x, ny = y, nw = w, nh = h;
      if (corner === 'tl') {
        nx = clamp(x + dxF, 0, x + w - 0.1);
        ny = clamp(y + dyF, 0, y + h - 0.1);
        nw = w - (nx - x);
        nh = h - (ny - y);
      } else if (corner === 'tr') {
        ny = clamp(y + dyF, 0, y + h - 0.1);
        nw = clamp(w + dxF, 0.1, 1 - x);
        nh = h - (ny - y);
      } else if (corner === 'bl') {
        nx = clamp(x + dxF, 0, x + w - 0.1);
        nw = w - (nx - x);
        nh = clamp(h + dyF, 0.1, 1 - y);
      } else if (corner === 'br') {
        nw = clamp(w + dxF, 0.1, 1 - x);
        nh = clamp(h + dyF, 0.1, 1 - y);
      }
      setCropBox({ x: nx, y: ny, w: nw, h: nh });
    },
  }), [setCropBox]);

  const panTL = useRef(makePan('tl')).current;
  const panTR = useRef(makePan('tr')).current;
  const panBL = useRef(makePan('bl')).current;
  const panBR = useRef(makePan('br')).current;

  // Rotate: apply to image immediately so crop coords stay simple
  const rotate = useCallback(async (dir) => {
    setRotating(true);
    try {
      const deg = dir === 'left' ? -90 : 90;
      const result = await ImageManipulator.manipulateAsync(
        uri,
        [{ rotate: deg }],
        { compress: 0.95, format: ImageManipulator.SaveFormat.JPEG }
      );
      setUri(result.uri);
      setImgSize({ w: result.width, h: result.height });
      setCropBox({ x: 0.04, y: 0.04, w: 0.92, h: 0.92 }); // reset crop after rotation
    } catch (e) {
      console.error('rotate error:', e);
    } finally {
      setRotating(false);
    }
  }, [uri, setCropBox]);

  // Confirm: apply crop → resize → return
  const handleConfirm = useCallback(async () => {
    setProcessing(true);
    try {
      const cb = cropRef.current;
      const { w: iW, h: iH } = imgSizeRef.current;
      const actions = [];

      // Apply crop if not trivially full image
      if (cb.x > 0.02 || cb.y > 0.02 || cb.w < 0.98 || cb.h < 0.98) {
        const originX = Math.round(cb.x * iW);
        const originY = Math.round(cb.y * iH);
        const cropW = Math.round(cb.w * iW);
        const cropH = Math.round(cb.h * iH);
        actions.push({
          crop: {
            originX: clamp(originX, 0, iW - 10),
            originY: clamp(originY, 0, iH - 10),
            width:  clamp(cropW, 10, iW - clamp(originX, 0, iW - 10)),
            height: clamp(cropH, 10, iH - clamp(originY, 0, iH - 10)),
          },
        });
      }

      // Resize to A4 proportions (210x297mm @ 150dpi)
      const maxW = 1240;
      const A4_RATIO = 297 / 210;
      actions.push({ resize: { width: maxW, height: Math.round(maxW * A4_RATIO) } });

      const result = await ImageManipulator.manipulateAsync(
        uri, actions,
        { compress: 0.92, format: ImageManipulator.SaveFormat.JPEG, base64: true }
      );

      const sel = FILTERS.find(f => f.id === filter);
      onConfirm({
        uri: result.uri,
        base64: result.base64,
        width: result.width,
        height: result.height,
        filter,
        cssFilter: sel?.css || 'none',
      });
      navigation.goBack();
    } catch (e) {
      console.error('ImageEditScreen confirm error:', e);
    } finally {
      setProcessing(false);
    }
  }, [uri, filter, onConfirm, navigation]);

  // Pixel positions for crop overlay
  const { renderW, renderH, offsetX, offsetY } = bounds;
  const cb = cropBox;
  const bL = offsetX + cb.x * renderW;
  const bT = offsetY + cb.y * renderH;
  const bW = cb.w * renderW;
  const bH = cb.h * renderH;

  const selFilter = FILTERS.find(f => f.id === filter);

  return (
    <View style={styles.container}>
      {/* Top bar */}
      <SafeAreaView style={styles.topSafe}>
        <View style={styles.topBar}>
          <TouchableOpacity style={styles.topBtnCancel} onPress={() => navigation.goBack()}>
            <Ionicons name="close" size={22} color={COLORS.textInverse} />
            <Text style={styles.topBtnCancelText}>Cancel</Text>
          </TouchableOpacity>
          <View style={styles.topTitleArea}>
            <Text style={styles.topTitle}>Edit Document</Text>
            {autoDetecting && (
              <View style={styles.autoDetectBadge}>
                <ActivityIndicator size={10} color={COLORS.primary} style={{ marginRight: 4 }} />
                <Text style={styles.autoDetectText}>Auto-detecting…</Text>
              </View>
            )}
            {!autoDetecting && edgeDetected && (
              <View style={styles.autoDetectBadge}>
                <Text style={styles.autoDetectText}>✨ Auto</Text>
              </View>
            )}
          </View>
          <TouchableOpacity
            style={styles.topBtnUse}
            onPress={handleConfirm}
            disabled={processing || autoDetecting}
          >
            {processing
              ? <ActivityIndicator size="small" color={COLORS.textInverse} />
              : <>
                  <Ionicons name="checkmark" size={20} color={COLORS.textInverse} />
                  <Text style={styles.topBtnUseText}>Use</Text>
                </>
            }
          </TouchableOpacity>
        </View>
      </SafeAreaView>

      {/* Image + crop overlay */}
      <View
        style={styles.imageArea}
        onLayout={e => {
          const { width, height } = e.nativeEvent.layout;
          setContainer({ width, height });
        }}
      >
        <Image source={{ uri }} style={StyleSheet.absoluteFill} resizeMode="contain" />

        {/* Overlay: dark masks + crop border + handles */}
        <View style={StyleSheet.absoluteFill} pointerEvents="box-none">
          {/* Dark mask — 4 edges around crop box */}
          <View style={[styles.mask, { top: 0, left: 0, right: 0, height: bT }]} />
          <View style={[styles.mask, { top: bT + bH, left: 0, right: 0, bottom: 0 }]} />
          <View style={[styles.mask, { top: bT, left: 0, width: bL, height: bH }]} />
          <View style={[styles.mask, { top: bT, left: bL + bW, right: 0, height: bH }]} />

          {/* Crop border */}
          <View style={[styles.cropBorder, { left: bL, top: bT, width: bW, height: bH }]} />

          {/* Rule-of-thirds grid */}
          <View style={[styles.gridV, { left: bL + bW / 3, top: bT, height: bH }]} />
          <View style={[styles.gridV, { left: bL + bW * 2 / 3, top: bT, height: bH }]} />
          <View style={[styles.gridH, { top: bT + bH / 3, left: bL, width: bW }]} />
          <View style={[styles.gridH, { top: bT + bH * 2 / 3, left: bL, width: bW }]} />

          {/* 4 Corner handles */}
          {[
            { id: 'tl', pan: panTL, left: bL - HANDLE_SIZE / 2, top: bT - HANDLE_SIZE / 2,
              corner: [styles.cornerVis, styles.cornerTL] },
            { id: 'tr', pan: panTR, left: bL + bW - HANDLE_SIZE / 2, top: bT - HANDLE_SIZE / 2,
              corner: [styles.cornerVis, styles.cornerTR] },
            { id: 'bl', pan: panBL, left: bL - HANDLE_SIZE / 2, top: bT + bH - HANDLE_SIZE / 2,
              corner: [styles.cornerVis, styles.cornerBL] },
            { id: 'br', pan: panBR, left: bL + bW - HANDLE_SIZE / 2, top: bT + bH - HANDLE_SIZE / 2,
              corner: [styles.cornerVis, styles.cornerBR] },
          ].map(({ id, pan, left, top, corner }) => (
            <View
              key={id}
              style={[styles.handle, { left, top }]}
              {...pan.panHandlers}
            >
              <View style={corner} />
            </View>
          ))}
        </View>

        {/* Rotating spinner */}
        {rotating && (
          <View style={styles.spinOverlay}>
            <ActivityIndicator size="large" color={COLORS.primary} />
          </View>
        )}
      </View>

      {/* Filter selector */}
      <View style={styles.filterBar}>
        {FILTERS.map(f => (
          <TouchableOpacity
            key={f.id}
            style={[styles.filterBtn, filter === f.id && styles.filterBtnActive]}
            onPress={() => setFilter(f.id)}
          >
            <Text style={styles.filterIcon}>{f.icon}</Text>
            <Text style={[styles.filterLabel, filter === f.id && styles.filterLabelActive]}>
              {f.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Bottom toolbar */}
      <SafeAreaView style={styles.bottomSafe}>
        <View style={styles.bottomBar}>
          <TouchableOpacity style={styles.rotBtn} onPress={() => rotate('left')} disabled={rotating}>
            <Ionicons name="refresh" size={22} color={COLORS.primary} style={{ transform: [{ scaleX: -1 }] }} />
            <Text style={styles.rotBtnText}>Rotate ←</Text>
          </TouchableOpacity>

          <View style={styles.filterLabel2}>
            <Text style={styles.filterLabel2Text}>{selFilter?.icon} {selFilter?.label}</Text>
            <Text style={styles.filterLabel2Sub}>Tap filter to change</Text>
          </View>

          <TouchableOpacity style={styles.rotBtn} onPress={() => rotate('right')} disabled={rotating}>
            <Ionicons name="refresh" size={22} color={COLORS.primary} />
            <Text style={styles.rotBtnText}>Rotate →</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    </View>
  );
}

const CORNER_W = 3;
const CORNER_L = 22;

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },

  topSafe: { backgroundColor: COLORS.bgCard },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: SPACING.md,
    paddingVertical: 10,
    backgroundColor: COLORS.bgCard,
  },
  topBtnCancel: { flexDirection: 'row', alignItems: 'center', gap: SPACING.xs, padding: 6 },
  topBtnCancelText: { color: COLORS.textSecondary, fontSize: 14 },
  topTitleArea: { alignItems: 'center' },
  topTitle: { color: COLORS.textPrimary, fontSize: 16, fontWeight: '700' },
  autoDetectBadge: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: COLORS.primaryLight, borderRadius: RADIUS.sm,
    paddingHorizontal: 6, paddingVertical: 2, marginTop: 3,
    borderWidth: 1, borderColor: COLORS.border,
  },
  autoDetectText: { color: COLORS.primary, fontSize: 10, fontWeight: '600' },
  topBtnUse: {
    flexDirection: 'row', alignItems: 'center', gap: SPACING.xs,
    backgroundColor: COLORS.accent, borderRadius: RADIUS.sm,
    paddingHorizontal: 14, paddingVertical: 7,
  },
  topBtnUseText: { color: COLORS.textInverse, fontSize: 14, fontWeight: '700' },

  imageArea: { flex: 1, backgroundColor: COLORS.bgCardAlt },

  mask: { position: 'absolute', backgroundColor: 'rgba(0,0,0,0.56)' },

  cropBorder: {
    position: 'absolute',
    borderWidth: 1.5,
    borderColor: 'rgba(255,255,255,0.9)',
  },
  gridV: {
    position: 'absolute',
    width: 1,
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  gridH: {
    position: 'absolute',
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.2)',
  },

  handle: {
    position: 'absolute',
    width: HANDLE_SIZE,
    height: HANDLE_SIZE,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 20,
  },
  cornerVis: { position: 'absolute', width: CORNER_L, height: CORNER_L },
  cornerTL: { top: 0, left: 0,
    borderTopWidth: CORNER_W, borderLeftWidth: CORNER_W, borderColor: COLORS.primary, borderRadius: 2 },
  cornerTR: { top: 0, right: 0,
    borderTopWidth: CORNER_W, borderRightWidth: CORNER_W, borderColor: COLORS.primary, borderRadius: 2 },
  cornerBL: { bottom: 0, left: 0,
    borderBottomWidth: CORNER_W, borderLeftWidth: CORNER_W, borderColor: COLORS.primary, borderRadius: 2 },
  cornerBR: { bottom: 0, right: 0,
    borderBottomWidth: CORNER_W, borderRightWidth: CORNER_W, borderColor: COLORS.primary, borderRadius: 2 },

  spinOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.3)',
    alignItems: 'center',
    justifyContent: 'center',
  },

  filterBar: {
    flexDirection: 'row',
    backgroundColor: COLORS.bgCard,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  filterBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 6,
    borderBottomWidth: 2.5, borderBottomColor: 'transparent',
  },
  filterBtnActive: { borderBottomColor: COLORS.primary },
  filterIcon: { fontSize: 20, marginBottom: 3 },
  filterLabel: { color: COLORS.textMuted, fontSize: 11, fontWeight: '600' },
  filterLabelActive: { color: COLORS.primary },

  bottomSafe: { backgroundColor: COLORS.bgCard },
  bottomBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: SPACING.lg,
    paddingVertical: 12,
    backgroundColor: COLORS.bgCard,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  rotBtn: { alignItems: 'center', gap: SPACING.xs, minWidth: 70 },
  rotBtnText: { color: COLORS.primary, fontSize: 11 },
  filterLabel2: { alignItems: 'center', flex: 1 },
  filterLabel2Text: { color: COLORS.textPrimary, fontSize: 14, fontWeight: '700' },
  filterLabel2Sub: { color: COLORS.textMuted, fontSize: 10, marginTop: 2 },
});
