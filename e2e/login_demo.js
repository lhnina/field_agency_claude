const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 900 } })
  const erros = []; p.on('pageerror', (e) => erros.push(e.message))
  await p.goto('http://localhost:5173/login')
  await p.getByRole('button', { name: /Direção/ }).click()
  console.log('preenchido:', await p.inputValue('input[type=email]'), (await p.inputValue('input[type=password]')).length > 0)
  await p.screenshot({ path: '/tmp/shots/login-demo.png' })
  await p.click('button[type=submit]'); await p.waitForURL('http://localhost:5173/')
  console.log('entrou como:', (await p.locator('header').innerText()).replace(/\n/g, ' ').slice(-40))
  console.log(erros.length ? 'ERROS ' + erros.join('\n') : 'sem erros'); await b.close()
})()
