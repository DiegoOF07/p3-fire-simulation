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

## Implementaciones

Por defecto se usan la simulación y las escenas falsas (`app/mock`). Para usar otras sin tocar código:

```powershell
$env:FIRE_SIM_MODULE = "app.solver"      # PowerShell; en bash: export FIRE_SIM_MODULE=app.solver
$env:FIRE_SCENES_MODULE = "app.scenes"
pnpm test:back   # tests/test_api_contract.py verifica que cumplan el contrato
pnpm dev
```

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
  app/api/  app/mock/                
  app/solver/                        
  app/scenes/                        
  analysis/  experiments/  tests/
frontend/
  src/core/          # cliente, decodificador, estado
  src/metrics/       # gráficas en vivo 
  src/scene/ src/ui/ # escena 3D y panel
```
