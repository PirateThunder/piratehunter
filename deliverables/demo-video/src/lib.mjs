import { chromium } from 'playwright'
import { execSync } from 'node:child_process'
import { mkdirSync, renameSync, readdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

export const BASE = process.env.BASE_URL ?? 'http://localhost:56151'
const ROOT = resolve(import.meta.dirname, '..')
const BUILD = resolve(ROOT, 'build')
const SCENES = resolve(ROOT, 'scenes')

/** Scene caption banner (bottom-left) + persistent brand pill (top-right). */
export async function chrome(page, caption, sub = '') {
  await page.evaluate(
    ({ caption, sub }) => {
      document.getElementById('__demo-caption')?.remove()
      document.getElementById('__demo-brand')?.remove()

      const brand = document.createElement('div')
      brand.id = '__demo-brand'
      brand.textContent = 'PirateHunter · piratehunter.fun'
      brand.style.cssText =
        'position:fixed;top:14px;right:16px;z-index:999999;background:#1B1C21;color:#fff;' +
        'font:500 15px/1 Inter,system-ui,sans-serif;padding:8px 16px;border-radius:100px;' +
        'box-shadow:0 2px 10px rgba(27,28,33,.18);letter-spacing:.02em'
      document.body.append(brand)

      if (caption) {
        const box = document.createElement('div')
        box.id = '__demo-caption'
        box.style.cssText =
          'position:fixed;left:24px;bottom:24px;z-index:999999;background:#fff;color:#1B1C21;' +
          'border-left:8px solid #402FFF;border-radius:12px;padding:16px 22px;max-width:900px;' +
          'box-shadow:0 8px 30px rgba(27,28,33,.16);font-family:Inter,system-ui,sans-serif'
        const h = document.createElement('div')
        h.textContent = caption
        h.style.cssText = 'font-size:26px;font-weight:650;line-height:1.25'
        box.append(h)
        if (sub) {
          const s = document.createElement('div')
          s.textContent = sub
          s.style.cssText = 'font-size:18px;color:#838388;margin-top:6px;line-height:1.35'
          box.append(s)
        }
        document.body.append(box)
      }
    },
    { caption, sub },
  )
}

export async function clearCaption(page) {
  await page.evaluate(() => document.getElementById('__demo-caption')?.remove())
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/** Click the first visible button/link/tab whose trimmed text matches. */
export async function clickText(page, text, { timeout = 8000 } = {}) {
  const loc = page
    .locator(`button:visible, a:visible, [role=tab]:visible`)
    .filter({ hasText: text })
    .first()
  await loc.waitFor({ state: 'visible', timeout })
  await sleep(350) // let the viewer read before the click lands
  await loc.click()
}

export async function typeHuman(page, locator, text, delay = 28) {
  await locator.click()
  await locator.pressSequentially(text, { delay })
}

/** Evaluate a Python snippet from an mcq question and return its stdout. */
export function evalPython(code) {
  try {
    // temp file avoids shell quoting issues with embedded newlines/quotes
    const f = resolve(BUILD, `eval-${Date.now()}.py`)
    writeFileSync(f, code)
    return execSync(`python3 ${f}`, { timeout: 5000 }).stdout.toString().trim()
  } catch {
    return null
  }
}

/**
 * Records one scene: fresh context at 1920×1080 with video on, runs `fn`,
 * saves scenes/<name>.webm. Scenes are independent — re-run a single one
 * with: node record.mjs --only <name>
 */
export async function recordScene(name, fn) {
  mkdirSync(BUILD, { recursive: true })
  mkdirSync(SCENES, { recursive: true })
  const browser = await chromium.launch()
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: BUILD, size: { width: 1920, height: 1080 } },
    deviceScaleFactor: 1,
  })
  const page = await context.newPage()
  page.setDefaultTimeout(12000)
  try {
    await fn(page)
  } finally {
    await context.close() // finalizes the video file
    const videos = readdirSync(BUILD).filter((f) => f.endsWith('.webm'))
    const latest = videos
      .map((f) => ({ f, mtime: +new Date() }))
      .sort((a, b) => a.f.localeCompare(b.f))
      .at(-1)
    if (latest) renameSync(resolve(BUILD, latest.f), resolve(SCENES, `${name}.webm`))
    await browser.close()
  }
  console.log(`[scene] ${name} done`)
}

export { resolve, SCENES, BUILD }
