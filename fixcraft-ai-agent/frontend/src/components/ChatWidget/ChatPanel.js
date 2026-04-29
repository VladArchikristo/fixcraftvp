import React from 'react';
import MessageList from './MessageList';
import QuickActions from './QuickActions';
import ChatInput from './ChatInput';
import { colors, radius, glassEffect, shadow } from './styles';

export default function ChatPanel({
  messages,
  isTyping,
  isOpen,
  isClosing,
  onClose,
  onSend,
  onQuickAction,
  showQuickActions,
  disabled,
}) {
  if (!isOpen && !isClosing) return null;

  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 480;

  const panelStyle = {
    position: 'fixed',
    bottom: isMobile ? 0 : 88,
    right: isMobile ? 0 : 24,
    width: isMobile ? '100%' : 400,
    height: isMobile ? '100%' : 600,
    maxHeight: isMobile ? '100vh' : 'calc(100vh - 120px)',
    borderRadius: isMobile ? 0 : radius.lg,
    ...glassEffect,
    boxShadow: shadow.panel,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    zIndex: 9999,
    animation: isClosing ? 'fcw-slideDown 0.25s ease forwards' : 'fcw-slideUp 0.3s ease',
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  };

  const headerStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '14px 16px',
    borderBottom: `1px solid ${colors.cardBorder}`,
    flexShrink: 0,
  };

  const closeBtnStyle = {
    width: 32,
    height: 32,
    borderRadius: '50%',
    border: 'none',
    background: 'rgba(255,255,255,0.06)',
    color: colors.textSecondary,
    fontSize: 18,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'background 0.2s',
    fontFamily: 'inherit',
  };

  return (
    <div style={panelStyle}>
      {/* Header */}
      <div style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: '50%',
              background: `linear-gradient(135deg, ${colors.cyan}, ${colors.cyanDark})`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 18,
            }}
          >
            🔧
          </div>
          <div>
            <div
              style={{
                color: colors.textPrimary,
                fontWeight: 600,
                fontSize: 15,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              Chat with Alex
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: '#4caf50',
                  display: 'inline-block',
                }}
              />
            </div>
            <div style={{ color: colors.textSecondary, fontSize: 12 }}>
              Online &bull; typically responds in 1 min
            </div>
          </div>
        </div>
        <button style={closeBtnStyle} onClick={onClose} aria-label="Close chat">
          ✕
        </button>
      </div>

      {/* Messages */}
      <MessageList messages={messages} isTyping={isTyping} />

      {/* Quick Actions */}
      <QuickActions onSelect={onQuickAction} visible={showQuickActions} />

      {/* Input */}
      <ChatInput onSend={onSend} disabled={disabled} />
    </div>
  );
}
