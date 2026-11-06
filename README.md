# p3-fire-simulation

Simulador web de incendio forestal: el backend (Python) resuelve las ecuaciones diferenciales sobre una malla 2D y el navegador la muestra en 3D.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (instala Python 3.12 por su cuenta si hace falta)
- Node.js 22+ y pnpm 11 (`npm i -g pnpm`)

En WSL, usar el `pnpm` y `node` de Linux, no los de Windows (`which pnpm` no debe apuntar a `/mnt/c/...`).

## Instalación

```bash
pnpm install
uv sync --directory backend
```

## Uso

```bash
pnpm dev        # backend en :8000 y frontend en http://localhost:5173
pnpm dev:back   # solo backend
pnpm dev:front  # solo frontend
pnpm test       # pruebas de backend y frontend
```

Si el repo está bajo `/mnt/c` en WSL y Vite no recarga al guardar, usar `VITE_POLL=1 pnpm dev`.

## Estructura

```text
backend/
  app/contracts.py   # Scene, Simulation, parámetros, cuantización (P1)
  app/protocol.py    # formato binario de cuadros y mensajes WebSocket (P1)
  app/api/  app/mock/                # P1
  app/solver/                        # P2
  app/scenes/                        # P3
  analysis/  experiments/  tests/
frontend/
  src/core/          # cliente, decodificador, estado (P1)
  src/metrics/       # gráficas en vivo (P1)
  src/scene/ src/ui/ # escena 3D y panel (P3)
```

`contracts.py`, `protocol.py` y `frontend/src/core/protocol.ts` solo los modifica la Persona 1, y los cambios se avisan antes de subirlos.
