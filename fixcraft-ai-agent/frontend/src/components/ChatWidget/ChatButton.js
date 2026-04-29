import React, { useState } from 'react';
import { colors, radius, shadow } from './styles';

export default function ChatButton({ onClick }) {
  const [hovered, setHovered] = useState(false);

  const style = {
    position: 'fixed',
    bottom: 24,
    right: 24,
    zIndex: 9998,
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '14px 18px',
    background: `linear-gradient(135deg, ${colors.cyan}, ${colors.cyanDark})`,
    color: colors.white,
    border: 'none',
    borderRadius: radius.pill,
    cursor: 'pointer',
    fontSize: 16,
    fontWeight: 600,
    boxShadow: shadow.button,
    animation: 'fcw-pulse 2.5s infinite',
    transition: 'transform 0.2s, box-shadow 0.2s',
    transform: hovered ? 'scale(1.05)' : 'scale(1)',
    fontFamily: 'inherit',
  };

  const labelStyle = {
    maxWidth: hovered ? 160 : 0,
    overflow: 'hidden',
    whiteSpace: 'nowrap',
    transition: 'max-width 0.3s ease, opacity 0.3s ease',
    opacity: hovered ? 1 : 0,
    fontSize: 14,
  };

  return (
    <button
      style={style}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-label="Open chat"
    >
      <span style={{ fontSize: 22 }}>💬</span>
      <span style={labelStyle}>Chat with us</span>
    </button>
  );
}
