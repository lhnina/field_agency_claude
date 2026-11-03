const { chromium } = require('playwright');
const BASE = 'http://localhost:5173'
;(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1500, height: 950 } })
  const erros = []; p.on('pageerror', (e) => erros.push(e.message)); p.on('console', (m) => m.type() === 'error' && erros.push(m.text()))
  await p.goto(BASE + '/login'); await p.fill('input[type=email]', 'hugo@promovida.pt'); await p.fill('input[type=password]', 'demo1234')
  await p.click('button[type=submit]'); await p.waitForURL(BASE + '/')
  // --- colaboradores: muito curta duração na 2.ª linha da coluna Vínculo
  await p.goto(BASE + '/colaboradores'); await p.waitForSelector('table.tbl tbody tr')
  console.log('Sofia:', (await p.locator('tr:has-text("Sofia Martins") td').nth(1).innerText()).replace(/\n/g, ' / '))
  await p.screenshot({ path: '/tmp/shots/colab-lista-mcd.png' })
  await p.getByRole('tab', { name: 'Muito curta duração' }).click(); await p.waitForTimeout(500)
  console.log('separador MCD:', (await p.locator('table.tbl tbody tr').allInnerTexts()).map((t) => t.split('\n')[0]).join(', '))
  await p.getByRole('tab', { name: 'Todos' }).click(); await p.waitForTimeout(400)
  // ficha: datas e checkbox
  await p.getByText('Sofia Martins').first().click(); await p.waitForTimeout(400)
  await p.getByRole('button', { name: 'Editar', exact: true }).first().click(); const d = p.getByRole('dialog'); await d.waitFor()
  console.log('checkbox MCD marcada:', await d.getByLabel('Muito curta duração').isChecked())
  await d.getByLabel('Data de admissão').fill('01/10/2026'); await d.getByLabel('Data de admissão').press('Enter')
  await p.screenshot({ path: '/tmp/shots/colab-form-termo.png' })
  await d.getByLabel('Vínculo').selectOption('recibos_verdes'); await p.waitForTimeout(200)
  console.log('recibos verdes → datas desativadas:', await d.getByLabel('Data de admissão').isDisabled(), await d.getByLabel('Fim do contrato').isDisabled(), '| MCD desativada:', await d.getByLabel('Muito curta duração').isDisabled())
  await p.screenshot({ path: '/tmp/shots/colab-form-rv.png' })
  await d.getByLabel('Vínculo').selectOption('a_termo'); await d.getByLabel('Muito curta duração').check()
  await d.getByRole('button', { name: 'Guardar' }).click(); await p.waitForSelector('text=Ficha atualizada')
  // --- contratos: estados
  await p.goto(BASE + '/contratos'); await p.waitForSelector('table.tbl tbody tr')
  console.log('estados na grelha:', [...new Set((await p.locator('table.tbl tbody tr td:nth-child(3)').allInnerTexts()).map((t) => t.trim()))].join(', '))
  await p.screenshot({ path: '/tmp/shots/contratos-estados.png' })
  const row = p.locator('table.tbl tbody tr', { hasText: 'Em curso' }).filter({ hasNotText: 'Logística' }).first()
  const num = (await row.locator('td').first().innerText()).split('\n')[1]  // nome do cliente
  await row.locator('a, button').first().click(); await p.waitForURL(/contratos\/\d+/); await p.waitForTimeout(500)
  const planear = async () => {
    await p.goto(BASE + '/planeamento'); await p.waitForTimeout(1500)
    return await p.getByText(num).count()
  }
  const url = p.url()
  console.log(num, 'no planeamento (em curso):', await planear())
  await p.goto(url); await p.getByRole('button', { name: 'Suspender' }).click(); await p.waitForSelector('text=Contrato suspenso')
  console.log(num, 'no planeamento (suspenso):', await planear())
  await p.goto(url); await p.getByRole('button', { name: 'Terminar', exact: true }).click(); await p.getByRole('dialog').waitFor()
  await p.screenshot({ path: '/tmp/shots/contrato-terminar.png' })
  await p.getByRole('dialog').getByRole('button', { name: 'Cancelar' }).click()
  await p.getByRole('button', { name: 'Retomar' }).click(); await p.waitForSelector('text=Contrato em curso')
  console.log(num, 'no planeamento (retomado):', await planear())
  console.log(erros.length ? 'ERROS ' + erros.join('\n') : 'sem erros'); await b.close()
})()
