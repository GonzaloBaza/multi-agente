---
name: Flujo de sincronización GitHub entre 2 PCs y servidor
description: Cómo se sincroniza el código entre PC escritorio, notebook y droplet
type: project
originSessionId: 6b8fdedc-5447-4fbf-8b01-d3f3827058a1
---
Gonzalo trabaja desde **2 PCs** (escritorio + notebook) y un **droplet**. GitHub (`github.com/GonzaloBazaMSK/multi-agente`) es el nodo central.

**Triángulo de sync** (configurado 2026-04-14):
```
PC escritorio ─┐
PC notebook  ──┼─→ GitHub (origin/main) ←─ Servidor /opt/multiagente
```

**Reglas:**
- Siempre `git pull` antes de empezar a trabajar en cualquier máquina.
- Commitear seguido y pushear al terminar una tarea lógica.
- El `.env` NO está en git — cada máquina tiene el suyo. Al clonar en una PC nueva, copiar `.env` manualmente.
- Carpeta `media/` está ignorada (user uploads, no código).
- Nunca editar directo en el servidor sin commitear, o el próximo `git pull` te lo pisa.

**Why:** Gonzalo arrancó en la PC de escritorio, después quiso seguir en la notebook, y además Claude venía editando directo en el server vía SSH. El setup actual unifica los 3 entornos vía GitHub.

**How to apply:** Si Gonzalo dice "estoy en la otra PC" o "no me aparecen los cambios", primer reflejo: `git pull`. Si hay conflicto, resolver manualmente y commitear, no `--force` a menos que sea consciente.
