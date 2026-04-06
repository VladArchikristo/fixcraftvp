---
name: create-api
description: Scaffold a new API endpoint with route, controller, validation, and tests
argument-hint: "[method] [path] [description]"
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
---

# Create API Endpoint

Create a new API endpoint: $ARGUMENTS

Process:
1. **Detect** existing API patterns in the project (framework, structure, naming)
2. **Route** — Add the route definition following existing conventions
3. **Controller** — Implement the handler with proper error handling
4. **Validation** — Add input validation using project's validation approach
5. **Types** — Add TypeScript types/interfaces if applicable
6. **Tests** — Write tests for the new endpoint
7. **Docs** — Update API docs if they exist

Follow existing project conventions exactly. Communicate in Russian.
