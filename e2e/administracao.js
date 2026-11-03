// E2E: o Administrador cria uma supervisora, que entra e muda a palavra-passe;
// o gestor cria um feriado municipal e os serviços dessa data passam para outro dia.
const { chromium } = require('playwright')
const out = process.argv[2] || '/tmp/shots'
async function entrar(p, email, pw = 'demo1234') {
  await p.goto('http://localhost:5173/login')
  await p.fill('input[type=email]', email)
  await p.fill('input[type=password]', pw)
  await p.click('button[type=submit]')
  await p.waitForURL('http://localhost:5173/')
}
;(async () => {
  const b = await chromium.launch()
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  p.on('pageerror', (e) => errors.push(e.message))

  await entrar(p, 'admin@promovida.pt')
  await p.goto('http://localhost:5173/configuracao')
  await p.waitForSelector('text=Novo utilizador')
  await p.click('button:has-text("Novo utilizador")')
  await p.getByLabel('Nome').fill('Joana Pires')
  await p.getByLabel('Email (para entrar)').fill('joana@promovida.pt')
  await p.getByLabel('Perfil').selectOption('supervisor')
  await p.getByLabel('Palavra-passe temporária').fill('Inicio2026')
  await p.click('role=dialog >> button:has-text("Guardar")')
  await p.waitForSelector('text=Utilizador criado')
  await p.screenshot({ path: `${out}/i3-utilizadores.png`, fullPage: true })
  await p.click('text=Terminar sessão')

  await entrar(p, 'joana@promovida.pt', 'Inicio2026')
  await p.click('button[title="Alterar a minha palavra-passe"]')
  await p.getByLabel('Palavra-passe atual').fill('Inicio2026')
  await p.getByLabel('Nova palavra-passe', { exact: true }).fill('Joana2026x')
  await p.getByLabel('Repetir a nova palavra-passe').fill('Joana2026x')
  await p.click('role=dialog >> button:has-text("Alterar")')
  await p.waitForSelector('text=Palavra-passe alterada')
  console.log('supervisora criada, entrou e alterou a palavra-passe')
  await p.click('text=Terminar sessão')

  await entrar(p, 'hugo@promovida.pt')
  await p.goto('http://localhost:5173/configuracao')
  await p.click('role=group[name="Secção"] >> button:has-text("Feriados")')
  await p.click('button:has-text("Feriado municipal ou da agência")')
  const d = new Date(); d.setDate(d.getDate() + ((8 - d.getDay()) % 7 || 7) + 1) // próxima terça
  const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  await p.getByLabel('Data').fill(iso)
  await p.getByLabel('Nome').fill('Feriado municipal de teste')
  await p.click('role=dialog >> button:has-text("Criar")')
  const t = await p.waitForSelector('text=/Feriado criado/')
  console.log(await t.innerText())
  await p.screenshot({ path: `${out}/i3-feriados.png`, fullPage: true })
  console.log(errors.length ? 'ERROS: ' + errors.join('\n') : 'sem erros')
  await b.close()
  if (errors.length) process.exit(1)
})().catch((e) => { console.error(e); process.exit(1) })
