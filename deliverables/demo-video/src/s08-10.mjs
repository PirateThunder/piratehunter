import { BASE, chrome, clickText, evalPython, sleep } from './lib.mjs'

/** Express test on the unverified demo candidate («грейд не подтверждён»). */
export async function s08_test(page) {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
  await chrome(page, '')
  await clickText(page, 'Кандидат', { timeout: 8000 })
  await page.waitForURL('**/candidate')
  await sleep(1200)

  await clickText(page, 'Категория и грейд')
  await sleep(1200)
  await chrome(page, 'Грейд не подтверждён', 'категория появится после теста')
  await sleep(2500)

  await clickText(page, 'Пройти тест')
  await page.waitForURL('**/candidate/test')
  await sleep(800)
  // экспресс-режим выбран по умолчанию; подчеркнуть выбор грейда
  await chrome(page, 'Экспресс-режим для жюри', '4 вопроса · ~3 минуты · те же полосы θ')
  await sleep(2500)
  await clickText(page, 'Начать тест')

  for (let i = 0; i < 4; i++) {
    await page.waitForSelector('button[aria-pressed], textarea', { timeout: 15000 })
    await sleep(2200) // viewer reads the question; timer visibly ticks
    const options = page.locator('button[aria-pressed]')
    if ((await options.count()) > 0) {
      // mcq: solve the snippet for real, pick the matching option
      const code = (await page.locator('pre code').first().textContent()) ?? ''
      const output = evalPython(code)
      let picked = false
      if (output != null) {
        const count = await options.count()
        for (let k = 0; k < count; k++) {
          const text = (await options.nth(k).textContent())?.trim()
          if (text && text.replace(/\s+/g, ' ') === output.replace(/\s+/g, ' ')) {
            await options.nth(k).click()
            picked = true
            break
          }
        }
      }
      if (!picked) await options.first().click()
    } else {
      await page.locator('textarea').pressSequentially('SELECT 1', { delay: 40 })
    }
    await sleep(600)
    await clickText(page, 'Ответить')
    await sleep(1200)
  }

  await page.waitForSelector('text=Результат теста', { timeout: 15000 })
  await chrome(page, 'Грейд = навык по тесту, не стаж', 'θ и погрешность SE · разбор по темам')
  await sleep(6500)
}

export async function s09_fsp_id(page) {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
  await chrome(page, 'Вход через FSP ID', 'ожидаемый сценарий ТЗ — мок OIDC-провайдера')
  await sleep(1500)
  await clickText(page, 'Войти через FSP ID')

  // mock registry identity picker (fsp_registry:52457) — navigation wiped the
  // overlay, re-inject it on the picker page too
  await page.waitForURL('**/oidc/authorize**', { timeout: 15000 })
  await chrome(page, 'Вход через FSP ID', 'ожидаемый сценарий ТЗ — мок OIDC-провайдера')
  await sleep(2000)
  await page.locator('a.user').first().click()

  // back to the app: /login/callback → cabinet (or role select on first entry)
  await page.waitForURL('**/login/callback**', { timeout: 15000 })
  await sleep(2500)
  const roleBtn = page.locator('button:has-text("Я кандидат")')
  if (await roleBtn.isVisible().catch(() => false)) {
    await page.locator('input[type=checkbox]').first().check()
    await roleBtn.click()
  }
  await page.waitForURL('**/candidate', { timeout: 15000 })
  await sleep(1500)
  await clickText(page, 'Категория и грейд')
  await sleep(1000)
  await page.locator('text=Достижения ФСП').scrollIntoViewIfNeeded()
  await chrome(page, 'История ФСП подтянута автоматически', 'рейтинг, дипломы, разряды — из реестра по fsp_id')
  await sleep(5000)
}

export async function s10_final(page) {
  await page.goto(BASE + '/', { waitUntil: 'networkidle' })
  await page.evaluate(() => {
    const wrap = document.createElement('div')
    wrap.style.cssText =
      'position:fixed;inset:0;z-index:999999;background:#1B1C21;color:#fff;display:flex;' +
      'flex-direction:column;align-items:center;justify-content:center;gap:18px;' +
      'font-family:Inter,system-ui,sans-serif'
    const img = document.createElement('img')
    img.src = '/brand/logo_01.svg'
    img.alt = ''
    img.style.cssText = 'height:72px;width:auto'
    const h = document.createElement('div')
    h.textContent = 'PirateHunter · piratehunter.fun'
    h.style.cssText = 'font-size:44px;font-weight:700'
    const s = document.createElement('div')
    s.textContent = '202 автотеста · смоук 14 шагов · ресед одной командой'
    s.style.cssText = 'font-size:26px;color:#C8C9CA;font-family:"JetBrains Mono",monospace'
    wrap.append(img, h, s)
    document.body.append(wrap)
  })
  await sleep(6000)
}
