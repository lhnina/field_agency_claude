// E2E: a Direção altera os encargos e a margem da pré-faturação muda.
const { chromium } = require('playwright')
const out = process.argv[2] || '/tmp/shots'
;(async () => {
  const b = await chromium.launch()
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  p.on('pageerror', (e) => errors.push(e.message))
  await p.goto('http://localhost:5173/login')
  await p.fill('input[type=email]', 'marta@promovida.pt')
  await p.fill('input[type=password]', 'demo1234')
  await p.click('button[type=submit]')
  await p.waitForURL('http://localhost:5173/')
  const margem = async () => {
    await p.goto('http://localhost:5173/prefaturacao')
    await p.waitForSelector('tfoot')
    return (await p.locator('text=Margem bruta').locator('..').innerText()).split('\n')[1]
  }
  const antes = await margem()
  await p.goto('http://localhost:5173/configuracao')
  await p.waitForSelector('text=Encargos sociais')
  await p.screenshot({ path: `${out}/i3-configuracao.png`, fullPage: true })
  for (const l of ['Sem termo (%)', 'A termo (%)', 'Muito curta duração (%)']) await p.getByLabel(l).fill('0')
  await p.click('button:has-text("Guardar")')
  await p.waitForSelector('text=Configuração guardada')
  const sem = await margem()
  await p.goto('http://localhost:5173/configuracao')
  for (const l of ['Sem termo (%)', 'A termo (%)', 'Muito curta duração (%)']) await p.getByLabel(l).fill('40')
  await p.click('button:has-text("Guardar")')
  await p.waitForSelector('text=Configuração guardada')
  console.log('margem com 40 %:', antes, '| sem encargos:', sem)
  console.log(errors.length ? 'ERROS: ' + errors.join('\n') : 'sem erros')
  await b.close()
  if (errors.length || antes === sem) process.exit(1)
})().catch((e) => { console.error(e); process.exit(1) })
