// FixCraft Chat Widget — Design Tokens & Shared Styles

export const colors = {
  bg: '#0d0d1a',
  card: '#161629',
  cardBorder: 'rgba(79, 195, 247, 0.15)',
  cyan: '#4fc3f7',
  cyanDark: '#0288d1',
  cyanGlow: 'rgba(79, 195, 247, 0.25)',
  white: '#ffffff',
  textPrimary: '#e8e8f0',
  textSecondary: '#8888aa',
  userBubble: 'rgba(255, 255, 255, 0.08)',
  botBubble: 'rgba(79, 195, 247, 0.12)',
  inputBg: 'rgba(255, 255, 255, 0.06)',
  overlay: 'rgba(13, 13, 26, 0.6)',
};

export const radius = {
  sm: 8,
  md: 14,
  lg: 20,
  pill: 50,
};

// Keyframe animations injected once into <head>
const keyframes = `
@keyframes fcw-slideUp {
  from { opacity: 0; transform: translateY(20px) scale(0.95); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes fcw-slideDown {
  from { opacity: 1; transform: translateY(0) scale(1); }
  to   { opacity: 0; transform: translateY(20px) scale(0.95); }
}
@keyframes fcw-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(79,195,247,0.5); }
  50%      { box-shadow: 0 0 0 12px rgba(79,195,247,0); }
}
@keyframes fcw-bounce {
  0%, 80%, 100% { transform: translateY(0); }
  40%           { transform: translateY(-6px); }
}
@keyframes fcw-fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
`;

let injected = false;
export function injectKeyframes() {
  if (injected) return;
  injected = true;
  const style = document.createElement('style');
  style.textContent = keyframes;
  document.head.appendChild(style);
}

// Shared inline style helpers
export const glassEffect = {
  background: 'rgba(22, 22, 41, 0.85)',
  backdropFilter: 'blur(16px)',
  WebkitBackdropFilter: 'blur(16px)',
  border: `1px solid ${colors.cardBorder}`,
};

export const shadow = {
  panel: '0 8px 32px rgba(0,0,0,0.5), 0 0 60px rgba(79,195,247,0.08)',
  button: '0 4px 20px rgba(79,195,247,0.35)',
};
