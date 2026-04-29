# Claude Prompt — FixCraft Chat Widget

## GOAL
Build a React chat widget embeddable on fixcraftvp.com — floating button that opens a chat panel.

## DESIGN (CRITICAL — match Vlad's taste)
- Dark theme ONLY (#0d0d1a background, #161629卡片)
- Semi-transparent backdrop blur effect (like glass)
- Rounded corners (14px radius)
- Cyan accent (#4fc3f7)
- Smooth animations (fade in/out, slide up)
- Messages with subtle left/right alignment + avatar
- Typing indicator (3 bouncing dots)
- Mobile-first responsive

## STRUCTURE
```
[Floating Button] 💬 — bottom-right, fixed, pulse animation on hover
  ↓
[Chat Panel] — slide from bottom-right, 400px wide, 600px tall (desktop), full screen (mobile)
  ├── Header: "Chat with Alex" + close X + online status dot
  ├── Messages: scrollable list
  ├── Input: text field + send button + mic icon (for future voice)
  └── Quick buttons: "TV Mounting", "Furniture Assembly", "Plumbing", "Other"
```

## FEATURES
1. **Floating button** — bottom-right, "Chat with us" on hover, pulse animation
2. **Chat panel** — opens with smooth animation (slide + fade)
3. **Messages** — user (right, white), bot (left, cyan #4fc3f7), avatar icons
4. **Typing indicator** — 3 bouncing dots when waiting for AI
5. **Quick action buttons** — common services, clickable, auto-fill message
6. **Persistent session** — generate sessionId (uuid), store in localStorage, restore on reload
7. **Auto-scroll** — scroll to bottom on new message
8. **Mobile** — full screen on mobile, draggable/minimizable
9. **Status bar** — "Alex is online • typically responds in 1 min"

## API INTEGRATION
```javascript
// Backend API base URL
const API_URL = 'https://api.fixcraftvp.com/api/chat'; // or localhost:3002 for dev

// Send message
POST /api/chat/message
Body: { sessionId: string, message: string }
Response: { reply: string, handoff: boolean }

// Get history
GET /api/chat/history/:sessionId
Response: { messages: [{ role, content }] }
```

## INITIAL MESSAGES
```javascript
const welcomeMessages = [
  {
    role: 'assistant',
    content: 'Hey there! 👋 I\'m Alex, Vlad\'s AI assistant at FixCraft VP.',
    delay: 0,
  },
  {
    role: 'assistant',
    content: 'I can help you with furniture assembly, TV mounting, plumbing, electrical — pretty much anything around the house in Charlotte.',
    delay: 800,
  },
  {
    role: 'assistant',
    content: 'What can I help you with today?',
    delay: 1600,
  },
];
```

## QUICK ACTION BUTTONS
```javascript
const quickButtons = [
  { label: '📺 TV Mounting', message: 'I need a TV mounted' },
  { label: '🪑 Furniture Assembly', message: 'I need furniture assembled' },
  { label: '🚿 Plumbing', message: 'I have a plumbing issue' },
  { label: '⚡ Electrical', message: 'I need electrical work' },
  { label: '🔧 Other', message: 'I have another project' },
];
```

## FILE STRUCTURE
Create in `/Users/vladimirprihodko/Папка тест/fixcraftvp/fixcraft-ai-agent/frontend/src/components/ChatWidget/`:
- `index.js` — main export
- `ChatWidget.js` — container
- `ChatButton.js` — floating button
- `ChatPanel.js` — chat window
- `MessageList.js` — messages + typing indicator
- `MessageBubble.js` — single message
- `QuickActions.js` — service buttons
- `ChatInput.js` — input field
- `styles.js` — styled-components or CSS-in-JS

## TECHNICAL REQUIREMENTS
- React 18+ functional components
- UUID for session generation
- localStorage for session persistence
- fetch for API calls
- No external UI libraries (keep it lightweight)
- CSS-in-JS (styled-components or JSS)

## DO NOT DO
- ❌ Do NOT modify fixcraftvp.com main site files (only add the widget component)
- ❌ Do NOT add heavy dependencies (no Material-UI, no Bootstrap)
- ❌ Do NOT change the existing site design/colors
- ❌ Do NOT touch Google Analytics, SEO, or existing scripts

## BUILD INSTRUCTIONS
1. Create all files in the folder above
2. Export ChatWidget as default
3. Usage: `import ChatWidget from './components/ChatWidget';` then add to App.js
4. Write styles as JS objects (can use inline styles or styled-components)
5. Test locally first (mock API responses), then connect to real backend

## SAMPLE MOCK RESPONSE (for testing)
```javascript
const mockApiCall = async (message) => {
  await new Promise(r => setTimeout(r, 1000));
  return {
    reply: `You said: "${message}". I'm Alex from FixCraft VP. I'd love to help! Can you tell me more about what you need?`,
    handoff: false,
  };
};
```

Save all console output to /tmp/claude_chatwidget.log
Report: files created, lines of code, and any errors.
