const { chromium } = require('playwright');
const BASE = 'http://localhost:5173'
;(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1500, height: 950 } }); const p = await ctx.newPage()
  const erros = []; p.on('pageerror', (e) => erros.push(e.message)); p.on('console', (m) => m.type() === 'error' && erros.push(m.text()))
  await p.goto(BASE + '/login'); await p.fill('input[type=email]', 'hugo@promovida.pt'); await p.fill('input[type=password]', 'demo1234')
  await p.click('button[type=submit]'); await p.waitForURL(BASE + '/')
  console.log('dashboard:', await p.locator('text=/^Documentação: \\d+ expirados/').innerText())
  await p.getByRole('link', { name: 'Documentação' }).click(); await p.waitForURL(BASE + '/documentacao'); await p.waitForSelector('table.tbl tbody tr')
  const kpis = (await p.locator('button:has-text("documentos obrigatórios"), button:has-text("prazo de aviso"), button:has-text("pendências")').allInnerTexts()).map((t) => t.replace(/\s+/g, ' '))
  console.log('kpis:', kpis.join(' | '))
  console.log('pendências:', await p.locator('table.tbl tbody tr').count())
  await p.screenshot({ path: '/tmp/shots/doc-pendencias.png' })
  // registar o CC do Tiago com anexo
  const linha = p.locator('tr:has-text("Tiago Moreira"):has-text("Doc. de Identificação")')
  await linha.getByRole('button', { name: /^Registar/ }).click(); await p.getByRole('dialog').waitFor()
  await p.getByLabel('Número / referência').fill('15328877')
  await p.getByLabel('Válido até').fill('15/03/2031'); await p.getByLabel('Válido até').press('Tab')
  await p.setInputFiles('input[type=file]', '/tmp/cc-tiago.pdf')
  await p.screenshot({ path: '/tmp/shots/doc-registar.png' })
  await p.getByRole('dialog').getByRole('button', { name: 'Guardar' }).click(); await p.waitForSelector('text=Documento registado')
  await p.getByLabel('Estado').selectOption('todos'); await p.getByLabel('Pesquisar').fill('tiago')
  const t = (await p.locator('tr:has-text("Doc. de Identificação")').innerText()).replace(/\s+/g, ' ')
  console.log('Tiago CC:', t)
  const [popup] = await Promise.all([ctx.waitForEvent('page'), p.locator('tr:has-text("Doc. de Identificação")').getByRole('button', { name: /cc-tiago/ }).click()])
  // em headless não há visualizador de PDF: o separador transfere o ficheiro; validamos o conteúdo transferido
  const dl = await popup.waitForEvent('download', { timeout: 10000 }).catch(() => null)
  const path = dl ? await dl.path() : null
  console.log('anexo abre:', popup.url().startsWith('blob:') || (!!path && require('fs').readFileSync(path).subarray(0, 5).toString() === '%PDF-'))
  await popup.close().catch(() => {})
  // tipos: criar
  await p.getByRole('button', { name: 'Tipos de documento' }).click(); await p.getByRole('button', { name: 'Novo tipo' }).click()
  await p.getByLabel('Nome').fill('Carta de condução'); await p.getByLabel('Avisar com antecedência (dias)').fill('45')
  await p.getByRole('dialog').getByRole('button', { name: 'Guardar' }).click(); await p.waitForSelector('text=Tipo criado'); await p.waitForSelector('td:has-text("Carta de condução")')
  console.log('tipos:', (await p.locator('table.tbl tbody tr td:first-child').allInnerTexts()).join(', '))
  await p.screenshot({ path: '/tmp/shots/doc-tipos.png' })
  // requisitos: criar
  await p.getByRole('button', { name: 'Requisitos' }).click(); await p.getByRole('button', { name: 'Novo requisito' }).click()
  await p.getByLabel('Documento obrigatório').selectOption({ label: 'Carta de condução' }); await p.getByLabel('Para a função').selectOption('Promotor(a)')
  await p.getByRole('dialog').getByRole('button', { name: 'Criar' }).click(); await p.waitForSelector('text=Requisito criado'); await p.waitForSelector('td:has-text("Carta de condução")')
  console.log('requisitos:', (await p.locator('table.tbl tbody tr').allInnerTexts()).map((x) => x.replace(/\s+/g, ' ').replace(' Remover', '')).join(' | '))
  await p.screenshot({ path: '/tmp/shots/doc-requisitos.png' })
  // ficha do colaborador
  await p.goto(BASE + '/colaboradores?id=' + await p.evaluate(async () => {
    const r = await fetch('/api/colaboradores?q=Jo%C3%A3o', { headers: { Authorization: 'Bearer ' + localStorage.getItem('fa.token') } }); return (await r.json())[0].id }))
  await p.waitForSelector('text=Documentação'); await p.waitForTimeout(600)
  await p.getByRole('button', { name: /^Documentação/ }).click()  // abre a secção
  const sec = p.locator('div.border-t:has(button[aria-expanded]:has-text("Documentação"))')
  console.log('ficha João:', (await sec.innerText()).replace(/\s+/g, ' ').slice(0, 220))
  await p.screenshot({ path: '/tmp/shots/doc-ficha.png' })
  // planeamento
  await p.goto(BASE + '/planeamento'); await p.waitForTimeout(1500)
  console.log('planeamento:', await p.locator('text=/com documentação pendente/').innerText())
  console.log(erros.length ? 'ERROS ' + erros.join('\n') : 'sem erros'); await b.close()
})()
