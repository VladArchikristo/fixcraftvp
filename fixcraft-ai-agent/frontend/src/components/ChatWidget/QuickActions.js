import React from 'react';
import { colors, radius } from './styles';

const quickButtons = [
  { label: '\ud83d\udcfa TV Mounting', message: 'I need a TV mounted' },
  { label: '\ud83e\ude91 Furniture Assembly', message: 'I need furniture assembled' },
  { label: '\ud83d\udebf Plumbing', message: 'I have a plumbing issue' },
  { label: '\u26a1 Electrical', message: 'I need electrical work' },
  { label: '\ud83d\udd27 Other', message: 'I have another project' },
];

const btnStyle = (hovered) => ({
  padding: '6px 12px',
  borderRadius: radius.pill,
  border: `1px solid ${colors.cardBorder}`,
  background: hovered ? colors.cyanGlow : 'transparent',
  color: colors.textPrimary,
  fontSize: 13,
  cursor: 'pointer',
  transition: 'background 0.2s, border-color 0.2s',
  whiteSpace: 'nowrap',
  fontFamily: 'inherit',
});

export default function QuickActions({ onSelect, visible }) {
  const [hoveredIdx, setHoveredIdx] = React.useState(-1);

  if (!visible) return null;

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 8,
        padding: '8px 16px 4px',
      }}
    >
      {quickButtons.map((btn, i) => (
        <button
          key={i}
          style={btnStyle(hoveredIdx === i)}
          onMouseEnter={() => setHoveredIdx(i)}
          onMouseLeave={() => setHoveredIdx(-1)}
          onClick={() => onSelect(btn.message)}
        >
          {btn.label}
        </button>
      ))}
    </div>
  );
}
