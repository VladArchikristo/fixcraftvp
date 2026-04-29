import React from 'react';
import { colors, radius } from './styles';

const avatarStyle = (isUser) => ({
  width: 32,
  height: 32,
  borderRadius: '50%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: 16,
  flexShrink: 0,
  background: isUser ? colors.userBubble : colors.botBubble,
  border: `1px solid ${isUser ? 'rgba(255,255,255,0.1)' : colors.cardBorder}`,
});

const bubbleStyle = (isUser) => ({
  maxWidth: '78%',
  padding: '10px 14px',
  borderRadius: isUser
    ? `${radius.md}px ${radius.md}px 4px ${radius.md}px`
    : `${radius.md}px ${radius.md}px ${radius.md}px 4px`,
  background: isUser ? colors.userBubble : colors.botBubble,
  color: colors.textPrimary,
  fontSize: 14,
  lineHeight: 1.5,
  wordBreak: 'break-word',
  border: `1px solid ${isUser ? 'rgba(255,255,255,0.06)' : colors.cardBorder}`,
});

export default function MessageBubble({ role, content }) {
  const isUser = role === 'user';

  const rowStyle = {
    display: 'flex',
    flexDirection: isUser ? 'row-reverse' : 'row',
    alignItems: 'flex-end',
    gap: 8,
    animation: 'fcw-fadeIn 0.3s ease',
  };

  return (
    <div style={rowStyle}>
      <div style={avatarStyle(isUser)}>
        {isUser ? '👤' : '🔧'}
      </div>
      <div style={bubbleStyle(isUser)}>{content}</div>
    </div>
  );
}
