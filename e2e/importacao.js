// E2E da importação: descarregar o modelo, carregar um Excel com erros, corrigir e importar.
// Uso: node e2e/importacao.js <lojas-com-erro.xlsx> <lojas-ok.xlsx> [pasta-capturas]
const { chromium } = require('playwright')
const [erroXlsx, okXlsx, out = '/tmp/shots'] = process.argv.slice(2)
;(async () => {
  const b = await chromium.launch()
  const p = await b.newPage({ viewport: { width: 1440, height: 950 } })
  const errors = []
  p.on('pageerror', (e) => errors.push(e.message))
  await p.goto('http://localhost:5173/login')
  await p.fill('input[type=email]', 'hugo@promovida.pt')
  await p.fill('input[type=password]', 'demo1234')
  await p.click('button[type=submit]')
  await p.waitForURL('http://localhost:5173/')
  await p.goto('http://localhost:5173/importacao')
  await p.click('button:has-text("2 · Lojas")')
  const [dl] = await Promise.all([p.waitForEvent('download'), p.getByRole('button', { name: 'Descarregar modelo Excel' }).click()])
  console.log('modelo:', dl.suggestedFilename())

  await p.setInputFiles('input[type=file]', erroXlsx)
  await p.waitForSelector('text=Pré-visualização')
  console.log('com erros:', await p.locator('text=/\\d+ com erros/').innerText(), '| importar ativo:', await p.locator('button:has-text("Importar")').last().isEnabled())
  await p.screenshot({ path: `${out}/i3-importacao-erros.png`, fullPage: true })

  await p.setInputFiles('input[type=file]', okXlsx)
  await p.waitForSelector('text=0 com erros')
  await p.locator('button:has-text("Importar")').last().click()
  await p.waitForSelector('text=Importação concluída')
  await p.waitForTimeout(500)
  console.log('contagem lojas:', await p.locator('button:has-text("2 · Lojas")').innerText().then((t) => t.split('\n').pop()))
  console.log(errors.length ? 'ERROS: ' + errors.join('\n') : 'sem erros')
  await b.close()
  if (errors.length) process.exit(1)
})().catch((e) => { console.error(e); process.exit(1) })
