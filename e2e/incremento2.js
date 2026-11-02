// E2E do incremento 2: validar o mês anterior, conferir a pré-faturação e fechar o apuramento.
// Uso: node e2e/incremento2.js [pasta-capturas]   (API em :8000, frontend em :5173, dados de demonstração)
const { chromium } = require('playwright')
const out = process.argv[2] || '/tmp/shots'

async function entrar(p, email) {
  await p.goto('http://localhost:5173/login')
  await p.fill('input[type=email]', email)
  await p.fill('input[type=password]', 'demo1234')
  await p.click('button[type=submit]')
  await p.waitForURL('http://localhost:5173/')
}

;(async () => {
  const b = await chromium.launch()
  const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
  const errors = []
  p.on('pageerror', (e) => errors.push(e.message))
  p.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })

  await entrar(p, 'hugo@promovida.pt')
  await p.goto('http://localhost:5173/validacao')
  await p.waitForSelector('table')
  const antes = await p.locator('tbody tr').count()
  await p.screenshot({ path: `${out}/i2-1-validacao.png`, fullPage: true })
  // corrigir uma linha e depois validar tudo
  await p.locator('button[aria-label="Corrigir horas"]').first().click()
  await p.fill('role=dialog >> input[inputmode=decimal]', '1,5')
  await p.fill('role=dialog >> label:has-text("Motivo") + input', 'Teste E2E')
  await p.click('role=dialog >> button:has-text("Guardar")')
  await p.waitForSelector('text=Horas registadas')
  await p.waitForTimeout(400)
  await p.click('input[aria-label="Selecionar todos"]')
  await p.click('button:has-text("Validar selecionados")')
  await p.waitForSelector('text=/\\d+ validados/')
  await p.waitForTimeout(600)
  console.log('validação: linhas antes', antes, '| depois', await p.locator('tbody tr').count())

  await p.goto('http://localhost:5173/prefaturacao')
  await p.waitForSelector('table')
  await p.locator('tbody tr').first().click()
  await p.waitForTimeout(300)
  await p.screenshot({ path: `${out}/i2-2-prefaturacao.png`, fullPage: true })
  console.log('pré-faturação total:', (await p.locator('tfoot').innerText()).replace(/\s+/g, ' '))

  // fechar o apuramento exige Direção/Financeiro
  await p.click('text=Terminar sessão')
  await entrar(p, 'marta@promovida.pt')
  await p.goto('http://localhost:5173/apuramentos')
  await p.waitForSelector('table')
  console.log('pendentes no apuramento:', await p.locator('text=Por validar').locator('..').innerText().catch(() => '?'))
  await p.locator('tbody tr').first().click()
  await p.screenshot({ path: `${out}/i2-3-apuramento.png`, fullPage: true })
  const fechar = p.locator('button:has-text("Fechar período")')
  if (await fechar.isEnabled()) {
    await fechar.click()
    await p.click('role=dialog >> button:has-text("Fechar período")')
    await p.waitForSelector('text=Período fechado')
    console.log('apuramento fechado')
  } else {
    console.log('fecho indisponível:', await fechar.getAttribute('title'))
  }
  const [dl] = await Promise.all([p.waitForEvent('download'), p.click('button:has-text("Exportar para o PHC")')])
  console.log('CSV:', dl.suggestedFilename())

  // depois do fecho, a validação desse mês fica bloqueada
  await p.goto('http://localhost:5173/validacao')
  await p.click('button:has-text("Validadas")')
  await p.waitForSelector('table')
  console.log('bloqueio visível:', await p.locator('text=já foi fechado').count() > 0)
  await p.goto('http://localhost:5173/colaboradores')
  await p.click('button:has-text("Sofia Martins")')
  await p.waitForSelector('text=Contrato atual')
  await p.screenshot({ path: `${out}/i2-4-colaborador.png`, fullPage: true })
  console.log(errors.length ? 'ERROS: ' + errors.join('\n') : 'sem erros na consola')
  await b.close()
  if (errors.length) process.exit(1)
})().catch((e) => { console.error(e); process.exit(1) })
