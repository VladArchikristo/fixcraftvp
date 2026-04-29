import React, { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';
import { colors, radius } from './styles';

function TypingIndicator() {
  const dotStyle = (i) => ({
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: colors.cyan,
    animation: `fcw-bounce 1.2s infinite ${i * 0.15}s`,
  });

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 16,
          background: 'rgba(79,195,247,0.12)',
          border: `1px solid rgba(79,195,247,0.15)`,
          flexShrink: 0,
        }}
      >
        🔧
      </div>
      <div
        style={{
          display: 'flex',
          gap: 4,
          padding: '12px 16px',
          borderRadius: `${radius.md}px ${radius.md}px ${radius.md}px 4px`,
          background: 'rgba(79,195,247,0.12)',
          border: `1px solid rgba(79,195,247,0.15)`,
        }}
      >
        <span style={dotStyle(0)} />
        <span style={dotStyle(1)} />
        <span style={dotStyle(2)} />
      </div>
    </div>
  );
}

export default function MessageList({ messages, isTyping }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  return (
    <div
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      {messages.map((msg, i) => (
        <MessageBubble key={i} role={msg.role} content={msg.content} />
      ))}
      {isTyping && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}
