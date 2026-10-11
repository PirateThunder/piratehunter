import { BASE, chrome, clickText, sleep, typeHuman } from './lib.mjs'

/** Assumes s03 ran (employer logged in, need page is the last one created). */
export async function s04_shortlist(page) {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
  await chrome(page, '')
  await clickText(page, 'Работодатель')
  await page.waitForURL('**/employer')

  // open the most recent need (top of the grid = the one from s03)
  await page.locator('a[href*="/employer/needs/"]:not([href$="new"])').first().click()
  await page.waitForURL('**/employer/needs/*')
  await sleep(2000)

  // money shot: ranked cards + opened explainability panel
  await chrome(page, 'Подборка с объяснением', 'score = 0.4·тест + 0.3·стек + 0.2·ФСП + 0.1·свежесть')
  await page.locator('text=Подборка по потребности').scrollIntoViewIfNeeded()
  await sleep(6000)

  // open the second card's «Почему в подборке» as well
  const toggles = page.locator('button:has-text("Почему в подборке")')
  if ((await toggles.count()) > 0) {
    await toggles.first().click()
    await sleep(4500)
  }

  // «рядом с запросом» block, if present
  const nearby = page.locator('text=Рядом с запросом')
  if ((await nearby.count()) > 0) {
    await chrome(page, 'Рядом с запросом', 'сильные профили вне целевой категории — не ломают категорийность')
    await nearby.scrollIntoViewIfNeeded()
    await sleep(4000)
  }

  // salary-vs-market widget on the editor: fill the range, save
  await page.locator('text=Редактировать потребность').scrollIntoViewIfNeeded()
  await chrome(page, 'Вилка vs рынок категории', 'медиана и квартили по данным платформы')
  const from = page.getByLabel('Вилка от, ₽')
  await from.click()
  await from.pressSequentially('250000', { delay: 25 })
  const to = page.getByLabel('Вилка до, ₽')
  await to.click()
  await to.pressSequentially('400000', { delay: 25 })
  await sleep(3500)
  await clickText(page, 'Сохранить изменения')
  await sleep(2500)

  // back to the money shot — let the two open explanation panels breathe
  await page.locator('text=Подборка по потребности').scrollIntoViewIfNeeded()
  await chrome(page, 'Объяснимый подбор', 'каждый фактор разложен: сколько дал к итоговому score')
  await sleep(8000)
}

export async function s05_invitation(page) {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
  await chrome(page, '')
  await clickText(page, 'Работодатель')
  await page.waitForURL('**/employer')
  await page.locator('a[href*="/employer/needs/"]:not([href$="new"])').first().click()
  await page.waitForURL('**/employer/needs/*')
  await sleep(1500)
  await page.locator('text=Подборка по потребности').scrollIntoViewIfNeeded()
  await sleep(1500)

  await chrome(page, 'Приглашение кандидату', 'текст + обязательная вилка ЗП + способ связи')
  await page.locator('button:has-text("Пригласить")').first().click()
  await page.locator('[data-slot=dialog-content]').waitFor({ state: 'visible' })
  await sleep(800)

  // refusal demo: clear the range → submit → validation toast
  const dlg = page.locator('[data-slot=dialog-content]')
  await dlg.getByLabel('Вилка от, ₽ *').fill('')
  await dlg.getByLabel('Вилка до, ₽ *').fill('')
  await dlg.locator('button:has-text("Отправить приглашение")').click()
  await chrome(page, 'Без вилки — нельзя', 'валидация на уровне формы и схемы API (400)')
  await sleep(2500)

  await typeHuman(
    page,
    dlg.locator('textarea'),
    'Здравствуйте! Увидели ваш подтверждённый профиль и историю ФСП — у нас задачи как раз под это. Готовы обсудить?',
    18,
  )
  await dlg.getByLabel('Вилка от, ₽ *').pressSequentially('260000', { delay: 25 })
  await dlg.getByLabel('Вилка до, ₽ *').pressSequentially('320000', { delay: 25 })
  await sleep(1000)
  await chrome(page, 'Кандидат увидит вилку ДО ответа')
  await dlg.locator('button:has-text("Отправить приглашение")').click()
  await sleep(2000)

  // tracker on the dashboard
  await page.goto(BASE + '/employer')
  await chrome(page, 'Трекер статусов', 'отправлено → просмотрено → принято / отклонено')
  await page.locator('text=Трекер приглашений').scrollIntoViewIfNeeded()
  await sleep(3500)
}
