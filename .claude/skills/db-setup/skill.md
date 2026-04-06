---
name: db-setup
description: Set up databases for projects — PostgreSQL, SQLite, MongoDB, Supabase, Firebase. Includes schema design, ORM setup, and migrations.
argument-hint: "[db type: postgres/sqlite/supabase/firebase/mongo] [project path]"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, WebSearch
---

# Database Setup

Set up and configure databases for any project.

## Arguments

- Database type and optional project path
- Example: `/db-setup supabase fixcraft`

## Supported Databases

### SQLite (simplest, local)
- Install better-sqlite3 or prisma with SQLite
- Create schema
- No server needed

### PostgreSQL (production)
- Check if postgres is installed, install via brew if not
- Create database and user
- Set up connection string in .env

### Supabase (cloud PostgreSQL + auth + storage)
- Initialize with Supabase CLI
- Create tables via SQL or dashboard
- Generate TypeScript types
- Set up Row Level Security

### Firebase (NoSQL + auth)
- Initialize Firebase project
- Set up Firestore collections
- Configure security rules

### MongoDB (document store)
- Local: install via brew, create database
- Atlas: guide through cloud setup
- Set up Mongoose models

## ORM Setup

Based on project type:
- **Next.js / Node.js** → Prisma or Drizzle
- **Python** → SQLAlchemy
- Install ORM, create schema, run initial migration

## Procedure

1. Detect project type (Next.js, Python, etc.)
2. Ask which database if not specified
3. Install dependencies
4. Create schema/models
5. Set up .env with connection string
6. Run migrations
7. Create seed data (optional)
8. Generate TypeScript types (if applicable)

## Output
```
=== DATABASE READY ===
Type: PostgreSQL via Supabase
ORM: Prisma
Schema: 3 tables (users, services, bookings)
Connection: .env.local configured
Commands:
  npx prisma studio  — visual editor
  npx prisma migrate — run migrations
```
