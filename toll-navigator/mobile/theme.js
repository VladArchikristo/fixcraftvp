/**
 * HaulWallet v13 — Unified Design System
 *
 * Color palette: white background, dark navy primary, orange trucking accents
 * Typography: system fonts (Roboto/SF) with consistent sizing 14-18px
 * Spacing: 16px base grid
 */

export const COLORS = {
  // Backgrounds
  bg:           '#FFFFFF',
  bgCard:       '#F5F7FA',
  bgCardAlt:    '#EDF0F5',
  bgInput:      '#F0F3F8',

  // Primary / accent
  primary:      '#1B3A5C',   // dark navy — brand, headers, icons
  primaryLight: '#E8EFF5',   // primary tint — active states, hover
  accent:       '#FF8C00',   // trucking orange — CTAs, buttons
  accentDark:   '#E07800',
  accentLight:  '#FFF3E0',   // orange tint

  // Text
  textPrimary:  '#1B2838',
  textSecondary:'#5A6B7E',
  textMuted:    '#9AA8B8',
  textInverse:  '#FFFFFF',

  // Semantic
  success:      '#2E7D32',
  successLight: '#E8F5E9',
  error:        '#D32F2F',
  errorLight:   '#FFEBEE',
  warning:      '#F57C00',
  info:         '#1565C0',

  // Borders
  border:       '#DEE3EA',
  borderLight:  '#E8ECF1',

  // Tab bar
  tabActive:    '#1B3A5C',
  tabInactive:  '#B0B8C4',
};

export const FONTS = {
  h1:    { fontSize: 28, fontWeight: '800', color: COLORS.textPrimary },
  h2:    { fontSize: 22, fontWeight: '700', color: COLORS.textPrimary },
  h3:    { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  body:  { fontSize: 16, fontWeight: '400', color: COLORS.textPrimary },
  small: { fontSize: 14, fontWeight: '400', color: COLORS.textSecondary },
  tiny:  { fontSize: 12, fontWeight: '400', color: COLORS.textMuted },
  label: { fontSize: 14, fontWeight: '600', color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: 1 },
};

export const SPACING = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const RADIUS = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  full: 999,
};

// Shadows
export const SHADOW = {
  sm: {
    shadowColor: '#1B2838',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 3,
    elevation: 2,
  },
  md: {
    shadowColor: '#1B2838',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 4,
  },
  lg: {
    shadowColor: '#1B2838',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 16,
    elevation: 8,
  },
  accent: {
    shadowColor: '#FF8C00',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 6,
  },
};

// Reusable component styles
export const SHARED = {
  container: {
    flex: 1,
    backgroundColor: COLORS.bg,
  },
  card: {
    backgroundColor: COLORS.bgCard,
    borderRadius: RADIUS.md,
    padding: SPACING.md,
    marginBottom: SPACING.md,
    borderWidth: 1,
    borderColor: COLORS.borderLight,
    shadowColor: '#1B2838',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 3,
    elevation: 2,
  },
  cardAlt: {
    backgroundColor: COLORS.bgCardAlt,
    borderRadius: RADIUS.md,
    padding: SPACING.md,
    marginBottom: SPACING.md,
  },
  input: {
    backgroundColor: COLORS.bgInput,
    borderRadius: RADIUS.sm,
    padding: SPACING.md,
    color: COLORS.textPrimary,
    fontSize: 16,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  inputFocused: {
    borderColor: COLORS.primary,
  },
  button: {
    backgroundColor: COLORS.accent,
    borderRadius: RADIUS.sm,
    paddingVertical: SPACING.md,
    paddingHorizontal: SPACING.lg,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#FF8C00',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 6,
  },
  buttonText: {
    color: COLORS.textInverse,
    fontSize: 16,
    fontWeight: '700',
  },
  buttonOutline: {
    borderWidth: 1.5,
    borderColor: COLORS.primary,
    borderRadius: RADIUS.sm,
    paddingVertical: SPACING.md - 2,
    paddingHorizontal: SPACING.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonOutlineText: {
    color: COLORS.primary,
    fontSize: 16,
    fontWeight: '600',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  divider: {
    height: 1,
    backgroundColor: COLORS.border,
    marginVertical: SPACING.md,
  },
  safeArea: {
    flex: 1,
    backgroundColor: COLORS.bg,
    paddingTop: 50,  // SafeAreaView fallback
  },
  scrollContent: {
    padding: SPACING.md,
    paddingBottom: SPACING.xxl,
  },
};
