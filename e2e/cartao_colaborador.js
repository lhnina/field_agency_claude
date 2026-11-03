const { chromium } = require('playwright');
const BASE = 'http://localhost:5173'
;(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1500, height: 950 } })
  const erros = []; p.on('pageerror', (e) => erros.push(e.message)); p.on('console', (m) => m.type() === 'error' && erros.push(m.text()))
  await p.goto(BASE + '/login'); await p.fill('input[type=email]', 'hugo@promovida.pt'); await p.fill('input[type=password]', 'demo1234')
  await p.click('button[type=submit]'); await p.waitForURL(BASE + '/')
  await p.goto(BASE + '/colaboradores'); await p.waitForSelector('table.tbl tbody tr')
  await p.getByText('Tiago Moreira').first().click(); await p.waitForTimeout(700)
  for (const s of ['Lojas afetas', 'Documentação', 'Credenciais']) {
    const btn = p.getByRole('button', { name: new RegExp('^' + s) })
    console.log(s, '| fechada:', await btn.getAttribute('aria-expanded'), '|', (await btn.innerText()).replace(/\s+/g, ' '))
  }
  await p.screenshot({ path: '/tmp/shots/cartao-fechado.png' })
  await p.getByRole('button', { name: /^Documentação/ }).click(); await p.waitForTimeout(300)
  await p.screenshot({ path: '/tmp/shots/cartao-doc-aberta.png' })
  await p.getByRole('button', { name: 'Ver na documentação' }).click(); await p.waitForURL(/documentacao\?colaborador=/); await p.waitForTimeout(600)
  console.log('filtro:', (await p.locator('text=/Colaborador:/').first().innerText()).replace(/\s+/g, ' '), '| linhas:', (await p.locator('table.tbl tbody tr').allInnerTexts()).map((t) => t.split('\n')[0]).filter((x, i, a) => a.indexOf(x) === i).join(','))
  await p.screenshot({ path: '/tmp/shots/doc-filtro-colab.png' })
  // editar requisito
  await p.getByRole('button', { name: 'Requisitos', exact: true }).click(); await p.waitForTimeout(400)
  await p.getByRole('button', { name: 'Editar requisito Registo criminal' }).click(); await p.getByRole('dialog').waitFor()
  await p.getByLabel('Nas lojas da cadeia').selectOption({ label: 'Pingo Doce' }); await p.getByRole('dialog').getByRole('button', { name: 'Guardar' }).click()
  await p.waitForSelector('text=Requisito atualizado')
  console.log('requisito:', (await p.locator('tr:has-text("Registo criminal")').innerText()).replace(/\s+/g, ' '))
  console.log(erros.length ? 'ERROS ' + erros.join('\n') : 'sem erros'); await b.close()
})()
