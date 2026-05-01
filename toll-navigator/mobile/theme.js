/**
 * HaulWallet v13 — Unified Design System
 *
 * Color palette: white background, dark navy primary, orange trucking accents
 * Typography: system fonts (Roboto/SF) with consistent sizing 14-18px
 * Spacing: 16px base grid
 */

/**
 * HaulWallet v14 — Unified Design System
 * Professional dark theme for truckers
 */

export const COLORS = {
  // Backgrounds — deep navy for professional trucking aesthetic
  bg:           '#0B1220',
  bgCard:       '#111B2E',
  bgCardAlt:    '#0E1626',
  bgInput:      '#1A2744',

  // Primary / accent — amber/gold trucking
  primary:      '#3B82F6',   // blue — trust, navigation, links
  primaryLight: '#1E3A5F',   // active states bg
  accent:       '#F59E0B',   // amber — CTAs, buttons
  accentDark:   '#D97706',
  accentLight:  '#FEF3C7',  // amber tint
  accentGlow:   '#FBBF24',

  // Text
  textPrimary:  '#F1F5F9',
  textSecondary:'#94A3B8',
  textMuted:    '#64748B',
  textInverse:  '#0B1220',

  // Semantic
  success:      '#22C55E',
  successLight: '#064E3B',
  error:        '#EF4444',
  errorLight:   '#7F1D1D',
  warning:      '#F59E0B',
  info:         '#3B82F6',

  // Borders
  border:       '#1E293B',
  borderLight:  '#334155',

  // Tab bar
  tabActive:    '#F59E0B',
  tabInactive:  '#475569',
};

export const FONTS = {
  h1:    { fontSize: 32, fontWeight: '800', color: COLORS.textPrimary },
  h2:    { fontSize: 24, fontWeight: '700', color: COLORS.textPrimary },
  h3:    { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  body:  { fontSize: 16, fontWeight: '400', color: COLORS.textPrimary },
  small: { fontSize: 14, fontWeight: '400', color: COLORS.textSecondary },
  tiny:  { fontSize: 12, fontWeight: '400', color: COLORS.textMuted },
  label: { fontSize: 12, fontWeight: '700', color: COLORS.accent, textTransform: 'uppercase', letterSpacing: 1 },
};

export const SPACING = {
  xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48,
};

export const RADIUS = {
  sm: 8, md: 12, lg: 16, xl: 24, full: 999,
};

export const SHADOW = {
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 4,
    elevation: 3,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 6,
  },
  lg: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.25,
    shadowRadius: 24,
    elevation: 12,
  },
  accent: {
    shadowColor: '#F59E0B',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.4,
    shadowRadius: 16,
    elevation: 8,
  },
};

export const SHARED = {
  container: { flex: 1, backgroundColor: COLORS.bg },
  card: {
    backgroundColor: COLORS.bgCard,
    borderRadius: RADIUS.md,
    padding: SPACING.md,
    marginBottom: SPACING.md,
    borderWidth: 1,
    borderColor: COLORS.border,
    ...SHADOW.sm,
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
  inputFocused: { borderColor: COLORS.primary },
  button: {
    backgroundColor: COLORS.accent,
    borderRadius: RADIUS.md,
    paddingVertical: SPACING.md,
    paddingHorizontal: SPACING.lg,
    alignItems: 'center',
    justifyContent: 'center',
    ...SHADOW.accent,
  },
  buttonText: {
    color: COLORS.textInverse,
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  buttonOutline: {
    borderWidth: 1.5,
    borderColor: COLORS.primary,
    borderRadius: RADIUS.md,
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
  row: { flexDirection: 'row', alignItems: 'center' },
  divider: { height: 1, backgroundColor: COLORS.border, marginVertical: SPACING.md },
  safeArea: { flex: 1, backgroundColor: COLORS.bg, paddingTop: 50 },
  scrollContent: { padding: SPACING.md, paddingBottom: SPACING.xxl },
};
