const { chromium } = require('playwright');
const BASE = 'http://localhost:5173'
async function entrar(b, email) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
  p._erros = []; p.on('pageerror', (e) => p._erros.push(e.message)); p.on('console', (m) => m.type() === 'error' && p._erros.push(m.text()))
  await p.goto(BASE + '/login'); await p.fill('input[type=email]', email); await p.fill('input[type=password]', 'demo1234')
  await p.click('button[type=submit]'); await p.waitForURL(BASE + '/'); return p
}
const linhas = async (p) => (await p.locator('table.tbl tbody tr td:first-child').allInnerTexts()).map((t) => t.split('\n')[0].trim())
;(async () => {
  const b = await chromium.launch(); const erros = []
  // Gestor de conta
  let p = await entrar(b, 'joana@promovida.pt')
  console.log('joana perfil:', (await p.locator('header').innerText()).replace(/\s+/g, ' ').slice(-30))
  await p.goto(BASE + '/clientes'); await p.waitForSelector('table.tbl tbody tr'); console.log('joana clientes:', (await linhas(p)).join(', '))
  await p.goto(BASE + '/contratos'); await p.waitForSelector('table.tbl tbody tr'); await p.waitForTimeout(400)
  console.log('joana contratos:', (await p.locator('table.tbl tbody tr').allInnerTexts()).map((t) => t.split('\n').slice(0, 2).join(' ')).join(' | '))
  await p.goto(BASE + '/planeamento'); await p.waitForTimeout(1500)
  const cl = await p.evaluate(() => [...new Set([...document.querySelectorAll('[data-cliente]')].map((e) => e.dataset.cliente))])
  console.log('joana planeamento turnos:', await p.locator('text=/turnos ·/').first().innerText().catch(() => '?'))
  await p.screenshot({ path: '/tmp/shots/joana-plan.png' }); erros.push(...p._erros); await p.close()
  // Gestor operacional: ficha do cliente com lista de gestores de conta
  p = await entrar(b, 'hugo@promovida.pt')
  await p.goto(BASE + '/clientes'); await p.waitForSelector('table.tbl tbody tr')
  await p.getByRole('button', { name: 'Editar' }).first().click(); await p.getByRole('dialog').waitFor()
  console.log('opções gestor de conta:', (await p.getByLabel('Gestor de conta').locator('option').allInnerTexts()).join(' | '))
  await p.screenshot({ path: '/tmp/shots/cliente-gestor.png' }); erros.push(...p._erros); await p.close()
  // Supervisor Amadora
  p = await entrar(b, 'rui@promovida.pt')
  console.log('rui perfil:', (await p.locator('header').innerText()).replace(/\s+/g, ' ').slice(-30))
  await p.goto(BASE + '/colaboradores'); await p.waitForSelector('table.tbl tbody tr'); await p.waitForTimeout(400)
  console.log('rui colaboradores zonas:', [...new Set((await p.locator('table.tbl tbody tr').allInnerTexts()).map((t) => (t.match(/Amadora|Lisboa|Oeiras|Sintra|Odivelas|Loures/) || ['?'])[0]))].join(','))
  await p.goto(BASE + '/clientes?tab=lojas'); await p.waitForTimeout(800)
  erros.push(...p._erros); await p.close()
  // Sara: todas
  p = await entrar(b, 'sara@promovida.pt')
  await p.goto(BASE + '/colaboradores'); await p.waitForSelector('table.tbl tbody tr'); await p.waitForTimeout(400)
  console.log('sara n.º colaboradores:', await p.locator('table.tbl tbody tr').count()); erros.push(...p._erros); await p.close()
  // Direção: utilizadores com zona
  p = await entrar(b, 'marta@promovida.pt')
  await p.goto(BASE + '/configuracao'); await p.waitForTimeout(800)
  console.log('utilizadores:', (await p.locator('table.tbl tbody tr').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ').replace(/ Editar.*/, '')).filter((t) => /Supervisor|Gestor de conta/.test(t)).join(' | '))
  await p.locator('tr:has-text("Rui Matos")').getByRole('button', { name: 'Editar' }).click(); await p.getByRole('dialog').waitFor()
  console.log('zonas no diálogo:', (await p.getByLabel('Zona que supervisiona').locator('option').allInnerTexts()).join(','), '| atual:', await p.getByLabel('Zona que supervisiona').inputValue())
  await p.screenshot({ path: '/tmp/shots/user-zona.png' }); erros.push(...p._erros); await p.close()
  console.log(erros.length ? 'ERROS ' + erros.join('\n') : 'sem erros'); await b.close()
})()
