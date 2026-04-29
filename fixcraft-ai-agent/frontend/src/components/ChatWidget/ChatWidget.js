import React, { useState, useEffect, useCallback, useRef } from 'react';
import ChatButton from './ChatButton';
import ChatPanel from './ChatPanel';
import { injectKeyframes } from './styles';

const API_URL = process.env.REACT_APP_CHAT_API_URL || 'https://api.fixcraftvp.com/api/chat';

const welcomeMessages = [
  {
    role: 'assistant',
    content: "Hey there! \ud83d\udc4b I'm Alex, Vlad's AI assistant at FixCraft VP.",
  },
  {
    role: 'assistant',
    content:
      'I can help you with furniture assembly, TV mounting, plumbing, electrical \u2014 pretty much anything around the house in Charlotte.',
  },
  {
    role: 'assistant',
    content: 'What can I help you with today?',
  },
];

// Mock API for dev/testing
const mockApiCall = async (message) => {
  await new Promise((r) => setTimeout(r, 1000));
  return {
    reply: `You said: "${message}". I'm Alex from FixCraft VP. I'd love to help! Can you tell me more about what you need?`,
    handoff: false,
  };
};

function getSessionId() {
  let id = localStorage.getItem('fcw_session_id');
  if (!id) {
    id = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem('fcw_session_id', id);
  }
  return id;
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [welcomeDone, setWelcomeDone] = useState(false);
  const sessionIdRef = useRef(getSessionId());

  // Inject CSS keyframes on mount
  useEffect(() => {
    injectKeyframes();
  }, []);

  // Load history from API or show welcome
  const initChat = useCallback(async () => {
    if (welcomeDone) return;

    try {
      const res = await fetch(`${API_URL}/history/${sessionIdRef.current}`);
      if (res.ok) {
        const data = await res.json();
        if (data.messages && data.messages.length > 0) {
          setMessages(data.messages);
          setWelcomeDone(true);
          return;
        }
      }
    } catch {
      // API not available, use welcome flow
    }

    // Drip-feed welcome messages with delays
    setWelcomeDone(true);
    for (let i = 0; i < welcomeMessages.length; i++) {
      if (i > 0) {
        setIsTyping(true);
        await new Promise((r) => setTimeout(r, 800));
        setIsTyping(false);
      }
      setMessages((prev) => [...prev, welcomeMessages[i]]);
    }
  }, [welcomeDone]);

  const handleOpen = () => {
    setIsOpen(true);
    setIsClosing(false);
    if (!welcomeDone) initChat();
  };

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(() => {
      setIsOpen(false);
      setIsClosing(false);
    }, 250);
  };

  const sendMessage = useCallback(
    async (text) => {
      const userMsg = { role: 'user', content: text };
      setMessages((prev) => [...prev, userMsg]);
      setIsTyping(true);

      try {
        const res = await fetch(`${API_URL}/message`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sessionId: sessionIdRef.current, message: text }),
        });

        if (res.ok) {
          const data = await res.json();
          setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
        } else {
          throw new Error('API error');
        }
      } catch {
        // Fallback to mock
        const mock = await mockApiCall(text);
        setMessages((prev) => [...prev, { role: 'assistant', content: mock.reply }]);
      } finally {
        setIsTyping(false);
      }
    },
    [],
  );

  const handleQuickAction = (msg) => sendMessage(msg);

  // Show quick actions only after welcome and no user messages yet
  const hasUserMessage = messages.some((m) => m.role === 'user');

  return (
    <>
      {!isOpen && !isClosing && <ChatButton onClick={handleOpen} />}
      <ChatPanel
        messages={messages}
        isTyping={isTyping}
        isOpen={isOpen}
        isClosing={isClosing}
        onClose={handleClose}
        onSend={sendMessage}
        onQuickAction={handleQuickAction}
        showQuickActions={!hasUserMessage && welcomeDone}
        disabled={isTyping}
      />
    </>
  );
}
