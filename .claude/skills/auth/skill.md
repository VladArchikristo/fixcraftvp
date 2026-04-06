---
name: auth
description: Add authentication to any project — login, signup, OAuth, JWT, sessions. Supports NextAuth, Supabase Auth, Firebase Auth, custom JWT.
argument-hint: "[method: nextauth/supabase/firebase/jwt] [project path]"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, WebSearch, Agent
---

# Authentication Setup

Add complete authentication system to any web project.

## Arguments

- Auth method and optional project path
- Example: `/auth nextauth fixcraft`

## Methods

### NextAuth.js (recommended for Next.js)
- Install next-auth
- Configure providers (Google, GitHub, Email, Credentials)
- Set up session handling
- Create login/signup pages
- Protect API routes and pages
- Add middleware for route protection

### Supabase Auth
- Set up Supabase client
- Email/password authentication
- OAuth providers (Google, GitHub, etc.)
- Magic link authentication
- Row Level Security policies
- Session management

### Firebase Auth
- Initialize Firebase
- Email/password + OAuth
- Phone number authentication
- Custom tokens
- Auth state listener

### Custom JWT
- Generate and verify JWT tokens
- Bcrypt password hashing
- Refresh token rotation
- HTTP-only cookie storage
- CSRF protection

## What Gets Created

1. **Auth API routes** — login, signup, logout, refresh
2. **Auth middleware** — protect routes/pages
3. **UI Components** — LoginForm, SignupForm, UserMenu
4. **Auth context/hook** — useAuth() for client components
5. **Database schema** — users table (if needed)
6. **.env variables** — all secrets with placeholders

## Security Checklist
- Passwords hashed with bcrypt (min 12 rounds)
- HTTP-only cookies for tokens
- CSRF protection enabled
- Rate limiting on auth endpoints
- Input validation and sanitization
- Secure session configuration
