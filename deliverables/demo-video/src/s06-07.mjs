import { BASE, chrome, clickText, sleep } from './lib.mjs'

export async function s06_candidate_fsp(page) {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
  await chrome(page, 'Вход кандидата', 'демо-аккаунт с историей ФСП')
  await clickText(page, 'Кандидат с ФСП')
  await page.waitForURL('**/candidate', { timeout: 10000 })
  await sleep(1500)

  await clickText(page, 'Категория и грейд')
  await sleep(1200)
  await chrome(page, 'Категория: специализация × грейд', 'место в ранжировании — «3 из 19»')
  await sleep(3500)

  const fsp = page.locator('text=Достижения ФСП')
  await fsp.scrollIntoViewIfNeeded()
  await chrome(page, 'Достижения ФСП', 'влияют на ранжирование в категории — не на грейд')
  await sleep(4500)
}

/** Needs a pending invitation for demo-candidate-fsp (pre-staged via API by record.mjs). */
export async function s07_inbox(page) {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
  await chrome(page, '')
  await clickText(page, 'Кандидат с ФСП')
  await page.waitForURL('**/candidate')
  await sleep(1500)

  await clickText(page, 'Приглашения')
  await sleep(1500)
  await chrome(page, 'Вилка ЗП видна до ответа', 'ЗП обязательна и прозрачна — принцип ТЗ')
  await sleep(4500)

  await clickText(page, 'Принять')
  await sleep(2000)
  await chrome(page, 'Контакты раскрыты обеим сторонам', 'до принятия контакты скрыты — §7.6')
  await sleep(4000)
}
