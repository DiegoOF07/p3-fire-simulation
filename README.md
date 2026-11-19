# p3-fire-simulation

Simulador web de incendio forestal: el backend (Python) resuelve las ecuaciones diferenciales sobre una malla 2D y el navegador la muestra en 3D.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (instala Python 3.12 por su cuenta si hace falta)
- Node.js 22+ y pnpm 11 (`npm i -g pnpm`)

Instalar y correr siempre desde el mismo sistema (Windows o WSL/Linux). `node_modules` y `.venv` creados en uno no funcionan en el otro; si se cambia, borrar `node_modules`, `frontend/node_modules` y `backend/.venv` y reinstalar.

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

En WSL con el repo bajo `/mnt/c`, si Vite no recarga al guardar, usar `VITE_POLL=1 pnpm dev`.

En la interfaz: elegir escenario, densidad y semilla en **Escena**, ajustar parámetros y hacer clic sobre el terreno para encender un foco (si la simulación no ha iniciado, el clic la inicia). Los parámetros de combustible y humedad solo cambian antes de iniciar. **Vista** activa isócronas, brasas y humo, y flechas de viento.

## Implementaciones

Por defecto se usan el solver (`app/solver`) y las escenas (`app/scenes`). Para correr con la simulación y la escena falsas, o probar otra implementación, sin tocar código:

```powershell
$env:FIRE_SIM_MODULE = "app.mock.simulation"   # PowerShell; en bash: export FIRE_SIM_MODULE=...
$env:FIRE_SCENES_MODULE = "app.mock.scenes"
pnpm dev
```

`tests/test_api_contract.py` y `tests/test_api_integration.py` verifican la implementación activa contra el contrato y de punta a punta.

## Experimentos

Cada experimento es un `.toml` en `backend/experiments/specs/` (ver `ejemplo.toml`). Una lista en `[scene]` o `[params]` es un barrido; cada combinación es una corrida.

```bash
pnpm experiments                                  # todos los specs
pnpm experiments experiments/specs/ejemplo.toml   # uno (ruta relativa a backend/)
pnpm experiments --jobs 4                         # en paralelo
pnpm experiments --dry-run                        # validar y listar corridas
pnpm bench                                        # costo por cuadro según malla y velocidad
```

Los resultados quedan en `backend/experiments/results/`: un CSV por corrida, `summary.csv` por experimento, y `summary.csv` y `summary.md` con todos los experimentos.

## Estructura

```text
backend/
  app/contracts.py   # Scene, Simulation, parámetros, cuantización
  app/protocol.py    # formato binario de cuadros y mensajes WebSocket
  app/api/           # REST y WebSocket
  app/session.py     # sesión: pausa, velocidad, hilo del solver
  app/mock/          # simulación y escena falsas
  app/solver/        # modelo y métodos numéricos
  app/scenes/        # relieves, árboles y escenarios
  analysis/          # notebooks de validación y experimentos
  experiments/       # corridas sin interfaz y benchmark
  tests/
frontend/
  src/core/          # cliente, decodificador, estado
  src/metrics/       # gráficas en vivo
  src/scene/ src/ui/ # escena 3D y panel
```
