---
name: code-explain
description: Explain any code, file, or project in simple terms. Break down complex logic, algorithms, and architecture for learning. Adapts to user's level.
argument-hint: "[file path or code concept]"
allowed-tools: Read, Grep, Glob, WebSearch, Agent
---

# Code Explainer

Explain code, algorithms, and architecture in clear, simple terms.

## Arguments

- File path, function name, or concept
- Example: `/code-explain ~/my_bot/bot.py`
- Example: `/code-explain "how does JWT work"`

## Modes

### File Explanation
1. Read the file
2. Explain what it does overall (1-2 sentences)
3. Go through section by section:
   - What each import does
   - What each function/class does
   - How data flows through the code
   - What the tricky parts are

### Concept Explanation
1. Explain the concept simply (ELI5 style)
2. Show a minimal code example
3. Explain when and why to use it
4. Common pitfalls

### Project Architecture
1. Map the project structure
2. Explain how parts connect
3. Draw ASCII diagram of data flow
4. Identify patterns used (MVC, REST, etc.)

## Explanation Style

- Use analogies from real life
- Explain in Russian with English technical terms
- Start simple, add detail progressively
- Use code snippets to illustrate points
- Highlight "gotchas" and common mistakes
- Compare with alternatives when helpful

## Visual Aids
- ASCII diagrams for architecture
- Step-by-step flow for algorithms
- Before/after for refactoring explanations
- Table comparisons (e.g., REST vs GraphQL)

## Output Format

```
## Что делает этот файл
[1-2 sentence summary]

## Разбор по частям

### Импорты (строки 1-5)
[explanation]

### Функция handleMessage (строки 10-25)
[explanation with key lines highlighted]

### Как всё работает вместе
[ASCII diagram or flow description]

## Ключевые моменты
- [important thing 1]
- [important thing 2]
```
