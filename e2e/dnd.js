// Teste E2E: arrastar um turno "por atribuir" para um colaborador e afetar até ao fim;
// depois substituir um turno pelo diálogo de candidatos.
const { chromium } = require('playwright')
;(async () => {
  const b = await chromium.launch()
  const p = await b.newPage({ viewport: { width: 1440, height: 1900 } })
  const errors = []
  p.on('pageerror', (e) => errors.push(e.message))
  await p.goto('http://localhost:5173/login')
  await p.fill('input[type=email]', 'hugo@promovida.pt')
  await p.fill('input[type=password]', 'demo1234')
  await p.click('button[type=submit]')
  await p.waitForURL('http://localhost:5173/')
  await p.goto('http://localhost:5173/planeamento')
  await p.waitForSelector('[role=grid]')

  const antes = await p.locator('text=/\\d+ por atribuir/').first().innerText()
  // primeiro cartão da linha "por atribuir" (ordem do DOM: header 8, lane label, 7 células)
  const grid = p.locator('[role=grid] > div')
  let src = null, srcCol = -1
  for (let col = 0; col < 7; col++) {
    const cell = grid.nth(9 + col)
    if (await cell.locator('button').count()) { src = cell.locator('button').first(); srcCol = col; break }
  }
  if (!src) throw new Error('sem turnos por atribuir')
  const loja = (await src.getAttribute('aria-label')).split(',')[0]
  // destino: linha do colaborador "Marco Dias", mesma coluna
  const rowLabel = p.locator('[role=grid] > div', { hasText: 'Marco Dias' }).first()
  const idx = await rowLabel.evaluate((el) => [...el.parentElement.children].indexOf(el))
  const dst = grid.nth(idx + 1 + srcCol)
  await src.dragTo(dst)
  await p.waitForSelector('role=dialog')
  console.log('DIALOG:', (await p.locator('role=dialog').innerText()).replace(/\n/g,' | ').slice(0,200))
  await p.click('role=dialog >> button:has-text("Afetar até ao fim")')
  await p.waitForSelector('text=Colaborador afeto até ao fim do contrato')
  await p.waitForTimeout(600)
  const depois = await p.locator('text=/\\d+ por atribuir/').first().innerText()
  const marco = await p.locator('[role=grid] > div').nth(idx + 1 + srcCol).innerText()
  console.log('drag:', loja, '|', antes, '->', depois, '| célula Marco contém loja:', marco.includes(loja.slice(0, 12)))

  // substituição pelo diálogo de candidatos
  await p.locator('[role=grid] > div').nth(idx + 1 + srcCol).locator('button').first().click()
  await p.click('button:has-text("Substituir")')
  await p.waitForSelector('role=dialog >> text=Escolher')
  const cand = await p.locator('role=dialog >> li').first().innerText()
  await p.locator('role=dialog >> button:has-text("Escolher")').first().click()
  await p.waitForSelector('text=Turno atualizado')
  console.log('substituição para:', cand.split('\n')[0])
  await p.waitForTimeout(500)
  await p.screenshot({ path: '/tmp/shots/8-apos-dnd.png' })
  console.log(errors.length ? 'ERROS: ' + errors.join('\n') : 'sem erros')
  await b.close()
  if (errors.length) process.exit(1)
})().catch((e) => { console.error(e); process.exit(1) })
