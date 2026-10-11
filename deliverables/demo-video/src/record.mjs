import { recordScene } from './lib.mjs'
import { s01_landing, s02_employer_login, s03_need } from './s01-03.mjs'
import { s04_shortlist, s05_invitation } from './s04-05.mjs'
import { s06_candidate_fsp, s07_inbox } from './s06-07.mjs'
import { s08_test, s09_fsp_id, s10_final } from './s08-10.mjs'

const ORDER = [
  ['01-landing', s01_landing],
  ['02-employer-login', s02_employer_login],
  ['03-need', s03_need],
  ['04-shortlist', s04_shortlist],
  ['05-invitation', s05_invitation],
  ['06-candidate-fsp', s06_candidate_fsp],
  ['07-inbox', s07_inbox],
  ['08-test', s08_test],
  ['09-fsp-id', s09_fsp_id],
  ['10-final', s10_final],
]

const only = process.argv.includes('--only') ? process.argv.at(-1) : null

// Pre-stage scene 07: a pending invitation for demo-candidate-fsp from the
// demo employer (skipped with --only unless --prestage is passed).
async function prestageInbox() {
  const login = await fetch(`${process.env.BACKEND ?? 'http://localhost:64844'}/api/v1/auth/dev`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ account: 'employer' }),
  }).then((r) => r.json())
  const token = login.access_token
  const candidates = await fetch(
    `${process.env.BACKEND ?? 'http://localhost:64844'}/api/v1/employer/candidates?limit=50`,
    { headers: { Authorization: `Bearer ${token}` } },
  ).then((r) => r.json())
  const target = candidates.find((c) => c.profile.fsp_id === 'fsp_001') ?? candidates[0]
  const res = await fetch(
    `${process.env.BACKEND ?? 'http://localhost:64844'}/api/v1/employer/invitations`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        candidate_id: target.profile.candidate_id,
        text: 'Мария, добрый день! Ваша история ФСП и подтверждённый middle по backend — то, что ищем в платформенную команду. Гибрид СПб, премии отдельно.',
        salary_from: 260000,
        salary_to: 320000,
        salary_type: 'net',
        contact_method: 'telegram',
      }),
    },
  )
  console.log('[prestage] invitation →', target.profile.fio, res.status)
}

// Scene 07 relies on the invitation created on camera in scene 05 (same
// employer → Мария/fsp_001). --prestage adds an extra one via API (used only
// when re-shooting 07 standalone, without scene 05 in the same dataset).
if (process.argv.includes('--prestage')) await prestageInbox()

for (const [name, fn] of ORDER) {
  if (only && name !== only && !name.startsWith(only)) continue
  await recordScene(name, fn)
}
console.log('all scenes recorded')
