import { BASE, chrome, clickText, sleep, typeHuman } from './lib.mjs'

export async function s01_landing(page) {
  await page.goto(BASE + '/', { waitUntil: 'networkidle' })
  await chrome(page, 'PirateHunter', 'работодатель находит вас сам · piratehunter.fun')
  await sleep(6000)
}

export async function s02_employer_login(page) {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
  await chrome(page, 'Вход работодателя', 'демо-режим для жюри — без регистрации')
  await sleep(1200)
  await clickText(page, 'Работодатель')
  await page.waitForURL('**/employer', { timeout: 10000 })
  await sleep(2500)
}

export async function s03_need(page) {
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' })
  await chrome(page, '')
  await clickText(page, 'Работодатель')
  await page.waitForURL('**/employer')
  await clickText(page, 'Новая потребность')
  await page.waitForURL('**/employer/needs/new')

  await chrome(page, 'Потребность свободным текстом')
  await typeHuman(
    page,
    page.getByLabel('Свободный текст'),
    'Ищем backend-разработчика middle: Python, FastAPI, PostgreSQL, Redis, 250–400к',
  )
  await sleep(600)

  await chrome(page, '«Разобрать» → структура', 'LLM-парсинг; без ключа — детерминированный fallback')
  await clickText(page, 'Разобрать')
  // wait for the parsed structure to land (spec select gets a value)
  await page.waitForFunction(
    () => document.querySelector('select')?.value === 'backend',
    { timeout: 15000 },
  )
  await sleep(2500)

  await clickText(page, 'Создать потребность')
  await page.waitForURL('**/employer/needs/*', { timeout: 10000 })
  await sleep(1200)
}
