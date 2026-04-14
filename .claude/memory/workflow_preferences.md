---
name: Preferencias de flujo de trabajo
description: Cómo prefiere Gonzalo que trabajemos (worktrees, rama, comunicación)
type: feedback
originSessionId: afc9a303-de9b-483e-b191-c75bf4d36177
---
Gonzalo prefiere trabajar **directamente sobre `main`**, no sobre worktrees de Claude Code.

**Why:** En la sesión inicial apareció un worktree `claude/crazy-archimedes` creado por una sesión anterior. Cuando se dio cuenta ("como que se duplicó todo") pidió borrarlo. No le gusta la duplicación de carpetas ni la complejidad de manejar ramas paralelas creadas por el agente.

**How to apply:**
- Nunca usar `EnterWorktree` automáticamente en este proyecto
- Si Claude Code intenta arrancar en modo worktree aislado, salir al directorio principal
- Trabajar en `C:\Users\Gonzalo Baza\Documents\GitHub\multi-agente` directamente
- Para cambios experimentales, preferir una branch simple sobre worktree
