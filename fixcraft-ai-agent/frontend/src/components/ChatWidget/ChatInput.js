import React, { useState } from 'react';
import { colors, radius } from './styles';

export default function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('');

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '10px 12px',
        borderTop: `1px solid ${colors.cardBorder}`,
      }}
    >
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type your message..."
        disabled={disabled}
        style={{
          flex: 1,
          padding: '10px 14px',
          borderRadius: radius.md,
          border: `1px solid ${colors.cardBorder}`,
          background: colors.inputBg,
          color: colors.textPrimary,
          fontSize: 14,
          outline: 'none',
          fontFamily: 'inherit',
          transition: 'border-color 0.2s',
        }}
        onFocus={(e) => (e.target.style.borderColor = colors.cyan)}
        onBlur={(e) => (e.target.style.borderColor = colors.cardBorder)}
      />
      {/* Mic icon placeholder for future voice */}
      <button
        style={{
          width: 38,
          height: 38,
          borderRadius: '50%',
          border: `1px solid ${colors.cardBorder}`,
          background: 'transparent',
          color: colors.textSecondary,
          fontSize: 18,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          fontFamily: 'inherit',
        }}
        aria-label="Voice input (coming soon)"
        title="Voice input (coming soon)"
        onClick={() => {}}
      >
        🎤
      </button>
      <button
        onClick={handleSend}
        disabled={disabled || !text.trim()}
        style={{
          width: 38,
          height: 38,
          borderRadius: '50%',
          border: 'none',
          background:
            text.trim() && !disabled
              ? `linear-gradient(135deg, ${colors.cyan}, ${colors.cyanDark})`
              : colors.inputBg,
          color: colors.white,
          fontSize: 18,
          cursor: text.trim() && !disabled ? 'pointer' : 'default',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          transition: 'background 0.2s, transform 0.1s',
          fontFamily: 'inherit',
        }}
        aria-label="Send message"
      >
        ➤
      </button>
    </div>
  );
}
