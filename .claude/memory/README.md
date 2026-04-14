# Claude Code — Memorias del proyecto

Este directorio contiene los archivos de memoria que Claude Code acumuló
durante las sesiones de trabajo sobre este proyecto.

## ¿Qué son?

Cada archivo `.md` es un chunk de contexto que Claude consulta automáticamente
al arrancar una sesión en este repo. Incluye decisiones de diseño, preferencias
del usuario, credenciales (referencias, no secretos), flujo de deploy, etc.

## Cómo usarlos en otra PC

Claude Code por default lee las memorias desde:
```
~/.claude/projects/<ruta-sanitizada-del-proyecto>/memory/
```

En **Windows** (tu caso):
```
C:\Users\<Tu Usuario>\.claude\projects\C--Users-<Tu Usuario>-Documents-GitHub-multi-agente\memory\
```

Después de hacer `git clone` o `git pull`, copiá los archivos de este
directorio (`.claude/memory/*.md`) a la ruta de arriba. Una vez que Claude
los detecte, vas a tener el mismo contexto que en la otra máquina.

### Comandos rápidos (PowerShell)

```powershell
# Desde la raíz del repo clonado
$dest = "$env:USERPROFILE\.claude\projects\C--Users-$env:USERNAME-Documents-GitHub-multi-agente\memory"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item .claude\memory\*.md -Destination $dest -Force
Write-Host "✓ Memorias instaladas en $dest"
```

### Comandos rápidos (bash / Mac / Linux)

```bash
# Ajustá la ruta según tu sistema si sos usuario distinto
DEST="$HOME/.claude/projects/C--Users-$(whoami)-Documents-GitHub-multi-agente/memory"
mkdir -p "$DEST"
cp .claude/memory/*.md "$DEST/"
echo "✓ Memorias instaladas en $DEST"
```

## Alternativa: sin copiarlas

Si no querés copiarlas a la ruta de Claude, podés simplemente pedirle en
la nueva sesión:

> "Leé `.claude/memory/MEMORY.md` y todos los archivos de esa carpeta para
> entender el contexto del proyecto. También leé `SESSION_HANDOFF.md`."

Claude los lee como archivos del repo y adquiere el mismo contexto.

## Contenido actual

- **MEMORY.md** — índice maestro de memorias
- **deployment.md** — droplet DO, docker, dominio
- **stack_overview.md** — arquitectura del sistema
- **sync_workflow.md** — cómo trabajar entre 2 PCs + server via GitHub
- **workflow_preferences.md** — preferencias del usuario (sin worktrees, main directo)
- **language.md** — español rioplatense
- **pending_supabase_rotation.md** — pendiente rotar la Supabase secret key
