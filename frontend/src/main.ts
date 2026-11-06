const app = document.querySelector<HTMLDivElement>('#app')!

fetch('/api/health')
  .then((res) => res.ok)
  .catch(() => false)
  .then((ok) => {
    app.textContent = ok ? 'Fire Sim: backend ok' : 'Fire Sim: backend unreachable'
  })
