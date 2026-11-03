const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1440, height: 1000 } })
  const erros = []; p.on('pageerror', (e) => erros.push(e.message)); p.on('console', (m) => m.type() === 'error' && erros.push(m.text()))
  await p.goto('http://localhost:5173/login')
  await p.fill('input[type=email]', 'hugo@promovida.pt'); await p.fill('input[type=password]', 'demo1234'); await p.click('button[type=submit]')
  await p.waitForURL('http://localhost:5173/'); await p.goto('http://localhost:5173/contratos')
  await p.getByText('CT-REP-2026/0001').first().click(); await p.waitForURL(/contratos\/\d+/); await p.getByRole('button', { name: 'Adicionar loja' }).waitFor(); await p.waitForTimeout(500)
  const al = await p.evaluate(() => {
    const t = document.querySelector('table.tbl'); const ths = [...t.querySelectorAll('thead th')]
    return ['Total/sem', 'Preço/h', 'Valor mensal'].map((n) => {
      const i = ths.findIndex((h) => h.textContent.trim() === n); const td = t.querySelector(`tbody tr td:nth-child(${i + 1})`)
      const a = (el) => { const r = document.createRange(); r.selectNodeContents(el); return Math.round(r.getBoundingClientRect().right) }
      return `${n}: ${a(ths[i])} vs ${a(td)}`
    })
  }); console.log('alinhamento', al.join(' | '))
  await p.screenshot({ path: '/tmp/shots/contrato-linhas.png' })
  await p.getByRole('button', { name: 'Adicionar loja' }).click()
  const inp = p.getByRole('combobox'); await inp.fill('c')
  console.log('1 letra:', await p.locator('[role=listbox]').innerText())
  await inp.fill('conti'); await p.waitForSelector('[role=option]')
  console.log('opções "conti":', (await p.locator('[role=option]').allInnerTexts()).map((t) => t.replace(/\n/g, ' / ')).join(' || '))
  await p.screenshot({ path: '/tmp/shots/loja-picker.png' })
  await inp.press('ArrowDown'); await inp.press('Enter')
  console.log('escolhida:', await p.locator('.inp:has-text("Alterar")').innerText())
  console.log(erros.length ? 'ERROS ' + erros.join('\n') : 'sem erros'); await b.close()
})()
