import type {
  CandidateEmployer,
  CandidateSelf,
  CompanySelf,
  Grade,
  GradeInfo,
  InvitationCandidate,
  InvitationEmployer,
  Need,
  SalaryMarket,
  Shortlist,
  SpecSlug,
} from '../types'

/*
 * MOCK (offline dev only): typed fixtures matching the live contract
 * (verified 2026-10-08 against OpenAPI). Active when NEXT_PUBLIC_API_MOCK=1;
 * production and the dev stand run live (default). Data density follows §10:
 * a candidate with ФСП history, one without, an unverified profile ranked down.
 */

const candidatePublic = {
  candidate_id: 'cand-1',
  fio: 'Иван Петров',
  spec_slug: 'backend',
  grade_claimed: 'middle' as const,
  grade_verified: 'middle' as const,
  grade_status: 'confirmed' as const,
  experience_years: 4,
  stack: ['Python', 'FastAPI', 'PostgreSQL', 'Redis', 'Docker'],
  roles: ['backend-разработчик'],
  soft_skills: ['командная работа'],
  about: 'Пишу сервисы на Python, люблю понятные API и тесты.',
  has_fsp: true,
  fsp: {
    score: 0.86,
    achievements: {
      rating: 1840,
      contests: [{ name: 'Чемпионат ФСП 2026', diploma: 2, place: 2 }],
    },
  },
  updated_at: '2026-10-01T12:00:00Z',
}

const profile: CandidateSelf = {
  ...candidatePublic,
  email: 'ivan@example.com',
  phone: '+7 900 123-45-67',
  contacts: { telegram: '@ivanpetrov' },
  privacy: { anonymous: false, show_fsp: true, show_stack: true },
  fsp_id: 'FSP-241-804',
}

const grade: GradeInfo = {
  spec_slug: 'backend',
  grade_claimed: 'middle',
  grade_verified: 'middle',
  status: 'confirmed',
  theta: 1.21,
  last_test_at: '2026-09-28T15:40:00Z',
  grade_changed_at: '2026-09-28T15:40:00Z',
  retest_available_at: '2026-10-28T15:40:00Z',
  change_available_at: '2026-12-27T15:40:00Z',
  category_rank: 7,
  category_size: 42,
}

const companyPublic = {
  company_id: 'comp-1',
  name: 'ООО «Северный вектор»',
  description: 'Платформа грузовой логистики: 40 микросервисов, высокие нагрузки.',
  industry: 'Логистика / SaaS',
  site: 'https://sevvector.ru',
}

const candidateInvitations: InvitationCandidate[] = [
  {
    id: 'inv-1',
    text: 'Иван, увидели ваш подтверждённый middle по backend и диплом чемпионата ФСП. Ищем разработчика на платформу логистики: FastAPI, PostgreSQL, очереди.',
    salary_from: 220000,
    salary_to: 280000,
    salary_type: 'gross',
    contact_method: 'telegram',
    status: 'sent',
    created_at: '2026-10-05T10:12:00Z',
    status_at: '2026-10-05T10:12:00Z',
    company: { company: companyPublic, contacts: null },
  },
  {
    id: 'inv-2',
    text: 'Добрый день! Команда платёжного ядра, стек совпал 4/5 must. Вилка — на руки, премии отдельно.',
    salary_from: 250000,
    salary_to: 310000,
    salary_type: 'net',
    contact_method: 'email',
    status: 'accepted',
    created_at: '2026-10-03T18:44:00Z',
    status_at: '2026-10-04T09:00:00Z',
    company: {
      company: { ...companyPublic, company_id: 'comp-2', name: 'АО «Финтех Лаб»' },
      contacts: { contacts: { telegram: '@fintech_hr', email: 'hr@fintech.dev' } },
    },
  },
]

const company: CompanySelf = {
  company_id: 'comp-1',
  name: 'ООО «Северный вектор»',
  description: 'Платформа грузовой логистики: 40 микросервисов, высокие нагрузки.',
  industry: 'Логистика / SaaS',
  contacts: { email: 'hr@sevvector.ru', telegram: '@sevvector_hr' },
  site: 'https://sevvector.ru',
}

const need: Need = {
  id: 'need-1',
  company_id: 'comp-1',
  raw_text:
    'Нужен бэкенд-разработчик на Python уровня middle в команду платформы. Обязательно: FastAPI и PostgreSQL, плюсом — Kubernetes и очереди. Вилка до 280к.',
  parsed: null,
  stack_must: ['Python', 'FastAPI', 'PostgreSQL'],
  stack_nice: ['Kubernetes', 'RabbitMQ'],
  spec_slug: 'backend',
  grade: 'middle',
  salary_from: 200000,
  salary_to: 280000,
  created_at: '2026-10-02T14:00:00Z',
}

const explanationIvan = [
  {
    factor: 'test',
    weight: 0.4,
    value: 0.83,
    contribution: 0.33,
    human_text: 'тест: middle подтверждён, θ=1.21 → 0.83',
  },
  {
    factor: 'stack',
    weight: 0.3,
    value: 1.0,
    contribution: 0.3,
    human_text: 'стек: совпало must 3/3, nice 0/2 → 1.00',
  },
  {
    factor: 'fsp',
    weight: 0.2,
    value: 0.8,
    contribution: 0.16,
    human_text: 'достижения ФСП: диплом II степени, чемпионат ФСП 2026 → 0.80',
  },
  {
    factor: 'freshness',
    weight: 0.1,
    value: 0.8,
    contribution: 0.08,
    human_text: 'свежесть профиля: активность 7 дн. назад → 0.80',
  },
]

const shortlist: Shortlist = {
  need_id: 'need-1',
  results: [
    {
      candidate: { profile: candidatePublic, contacts: null },
      score: 0.87,
      explanation: explanationIvan,
      in_category: true,
    },
    {
      candidate: {
        profile: {
          ...candidatePublic,
          candidate_id: 'cand-2',
          fio: 'Мария Соколова',
          stack: ['Python', 'Django', 'PostgreSQL', 'Kubernetes'],
          experience_years: 5,
          has_fsp: false,
          fsp: null,
        },
        contacts: null,
      },
      score: 0.74,
      explanation: [
        {
          factor: 'test',
          weight: 0.4,
          value: 0.75,
          contribution: 0.3,
          human_text: 'тест: middle подтверждён, θ=0.95 → 0.75',
        },
        {
          factor: 'stack',
          weight: 0.3,
          value: 0.8,
          contribution: 0.24,
          human_text: 'стек: совпало must 2/3, nice 1/2 → 0.80',
        },
        {
          factor: 'fsp',
          weight: 0.2,
          value: 0,
          contribution: 0,
          human_text: 'достижения ФСП: нет истории ФСП',
        },
        {
          factor: 'freshness',
          weight: 0.1,
          value: 0.95,
          contribution: 0.1,
          human_text: 'свежесть профиля: активность 2 дн. назад → 0.95',
        },
      ],
      in_category: true,
    },
    {
      candidate: {
        profile: {
          ...candidatePublic,
          candidate_id: 'cand-3',
          fio: 'Кандидат #2417',
          grade_verified: null,
          grade_status: 'unverified' as const,
          stack: ['Python', 'FastAPI', 'MongoDB'],
          experience_years: 2,
        },
        contacts: null,
      },
      score: 0.4,
      explanation: [
        {
          factor: 'test',
          weight: 0.4,
          value: 0.4,
          contribution: 0.16,
          human_text: 'тест: грейд не подтверждён (потолок 0.4) → 0.40',
        },
        {
          factor: 'stack',
          weight: 0.3,
          value: 0.53,
          contribution: 0.16,
          human_text: 'стек: совпало must 2/3 → 0.53',
        },
        {
          factor: 'fsp',
          weight: 0.2,
          value: 0.7,
          contribution: 0.14,
          human_text: 'достижения ФСП: победитель хакатона ФСП 2025 → 0.70',
        },
        {
          factor: 'freshness',
          weight: 0.1,
          value: 1,
          contribution: 0.1,
          human_text: 'свежесть профиля: активность вчера → 1.00',
        },
      ],
      in_category: false,
    },
  ],
}

const bank: CandidateEmployer[] = shortlist.results.map((r) => r.candidate)

const employerInvitations: InvitationEmployer[] = [
  {
    id: 'inv-1',
    text: 'Иван, увидели ваш подтверждённый middle по backend и диплом чемпионата ФСП…',
    salary_from: 220000,
    salary_to: 280000,
    salary_type: 'gross',
    contact_method: 'telegram',
    status: 'viewed',
    created_at: '2026-10-05T10:12:00Z',
    status_at: '2026-10-05T18:40:00Z',
    candidate: { profile: candidatePublic, contacts: null },
  },
]

const salaryMarket: SalaryMarket = {
  spec: 'backend',
  grade: 'middle',
  category_size: 42,
  sample_needs: 12,
  sample_invitations: 30,
  from_p25: 200000,
  from_p50: 230000,
  from_p75: 260000,
  to_p25: 250000,
  to_p50: 280000,
  to_p75: 320000,
}

/** Resolved promise keeps the same async shape as the live API. */
function respond<T>(data: T): Promise<T> {
  return Promise.resolve(structuredClone(data))
}

export const mockApi = {
  candidate: {
    getProfile: () => respond(profile),
    getGrade: () => respond(grade),
    getInvitations: () => respond(candidateInvitations),
  },
  employer: {
    getCompany: () => respond(company),
    getNeeds: () => respond([need]),
    getNeed: (needId: string) =>
      respond([need].find((n) => n.id === needId) ?? { ...need, id: needId }),
    getShortlist: (_needId: string) => respond(shortlist),
    getCandidates: () => respond(bank),
    getInvitations: () => respond(employerInvitations),
    getSalaryMarket: (_spec: SpecSlug, _grade: Grade) => respond(salaryMarket),
  },
}

export type CabinetApi = typeof mockApi
