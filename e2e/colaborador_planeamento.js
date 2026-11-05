// E2E: zona e carga afetada nos colaboradores; "Ver no planeamento" filtrado por colaborador;
// filtros cliente + supervisor no planeamento combinam-se (E).
const { chromium } = require('playwright')
const out = process.argv[2] || '/tmp/shots'
;(async () => {
  const b = await chromium.launch()
  const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
  const errors = []
  p.on('pageerror', (e) => errors.push(e.message))
  await p.goto('http://localhost:5173/login')
  await p.fill('input[type=email]', 'hugo@promovida.pt')
  await p.fill('input[type=password]', 'demo1234')
  await p.click('button[type=submit]')
  await p.waitForURL('http://localhost:5173/')

  await p.goto('http://localhost:5173/colaboradores')
  await p.waitForSelector('th:has-text("Carga afetada/semana")')
  const total = await p.locator('tbody tr').count()
  await p.locator('label:has-text("Zona:") select').selectOption({ label: 'Amadora' })
  await p.waitForTimeout(500)
  const zonas = await p.locator('tbody tr td:nth-child(3)').allInnerTexts()
  console.log('filtro zona Amadora:', total, '->', zonas.length, '| todas Amadora:', zonas.every((z) => z === 'Amadora'))
  await p.click('table >> button:has-text("Inês Carvalho")')
  await p.waitForSelector('text=Lojas afetas')
  await p.screenshot({ path: `${out}/col-carga.png`, fullPage: true })
  console.log('carga Inês:', await p.locator('tr:has-text("Inês Carvalho") td:nth-child(5)').innerText())

  await p.click('button:has-text("Ver no planeamento")')
  await p.waitForURL(/planeamento\?colaborador=/)
  await p.waitForSelector('[role=grid]')
  await p.waitForTimeout(500)
  const linhas = await p.locator('[role=grid] .font-medium.text-\\[13px\\]').allInnerTexts()
  console.log('linhas no planeamento:', linhas.join(' | '))
  await p.screenshot({ path: `${out}/col-planeamento.png`, fullPage: true })

  // cliente + supervisor: todas as linhas de colaborador têm turnos desse cliente
  await p.click('button:has-text("Limpar filtros")')
  await p.locator('label:has-text("Cliente:") select').selectOption({ label: 'Atlântico Conservas' })
  await p.locator('label:has-text("Supervisor:") select').selectOption({ label: 'Rui Matos' })
  await p.waitForTimeout(800)
  const clientes = await p.locator('[role=grid] button[draggable=true] span:nth-child(3)').allInnerTexts()
  console.log('cliente+supervisor só Atlântico:', clientes.length > 0 && clientes.every((c) => c.includes('Atlântico')))
  console.log(errors.length ? 'ERROS: ' + errors.join('\n') : 'sem erros')
  await b.close()
  if (errors.length) process.exit(1)
})().catch((e) => { console.error(e); process.exit(1) })
