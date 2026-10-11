'use client'

import { useState } from 'react'

import { RoleGate } from '@/fsd/features/auth/role-gate'
import { cabinetApi } from '@/fsd/shared/api/cabinet-api'
import type {
  ApplicationCandidate,
  CandidateSelf,
  InvitationCandidate,
} from '@/fsd/shared/api/types'
import { useQuery } from '@/fsd/shared/lib/use-query'
import { Tabs, TabsList, TabsPanel, TabsTab } from '@/fsd/shared/ui/tabs'
import { GradeSection } from '@/fsd/widgets/candidate/grade-section'
import { InvitationsSection } from '@/fsd/widgets/candidate/invitations-section'
import { MyApplicationsSection } from '@/fsd/widgets/candidate/my-applications-section'
import { ProfileSection, ProfileSectionSkeleton } from '@/fsd/widgets/candidate/profile-section'
import { SettingsSection } from '@/fsd/widgets/candidate/settings-section'
import { VacanciesSection } from '@/fsd/widgets/candidate/vacancies-section'

/** Candidate cabinet (PRD §7.2): profile, category/grade, invitations, settings. */
export function CandidatePage() {
  return (
    <RoleGate allowedRole="candidate">
      <CandidateCabinet />
    </RoleGate>
  )
}

function CandidateCabinet() {
  const [profile, setProfile] = useState<CandidateSelf | null>(null)
  const [invitations, setInvitations] = useState<InvitationCandidate[] | null>(null)
  const [applications, setApplications] = useState<ApplicationCandidate[] | null>(null)

  useQuery(async () => {
    const p = await cabinetApi.candidate.getProfile()
    setProfile(p)
    return p
  })
  const gradeQuery = useQuery(() => cabinetApi.candidate.getGrade())
  useQuery(async () => {
    const list = await cabinetApi.candidate.getInvitations()
    setInvitations(list)
    return list
  })
  useQuery(async () => {
    const list = await cabinetApi.candidate.getApplications()
    setApplications(list)
    return list
  })

  const openCount = (invitations ?? []).filter(
    (i) => i.status === 'sent' || i.status === 'viewed',
  ).length

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-heading">Кабинет кандидата</h1>
        <p className="text-sm text-muted-foreground">
          Профиль, категория и грейд, входящие приглашения
        </p>
      </div>

      <Tabs defaultValue={openCount > 0 ? 'invitations' : 'profile'}>
        <TabsList>
          <TabsTab value="profile">Профиль</TabsTab>
          <TabsTab value="grade">Категория и грейд</TabsTab>
          <TabsTab value="invitations">Приглашения{openCount > 0 ? ` (${openCount})` : ''}</TabsTab>
          <TabsTab value="vacancies">Вакансии</TabsTab>
          <TabsTab value="applications">Мои отклики</TabsTab>
          <TabsTab value="settings">Настройки</TabsTab>
        </TabsList>

        <TabsPanel value="profile">
          {profile ? (
            <ProfileSection profile={profile} onSaved={setProfile} />
          ) : (
            <ProfileSectionSkeleton />
          )}
        </TabsPanel>
        <TabsPanel value="grade">
          {gradeQuery.data ? (
            <GradeSection grade={gradeQuery.data} profile={profile} />
          ) : (
            <ProfileSectionSkeleton />
          )}
        </TabsPanel>
        <TabsPanel value="invitations">
          {invitations ? (
            <InvitationsSection
              invitations={invitations}
              onChanged={(updated) =>
                setInvitations((list) =>
                  (list ?? []).map((i) => (i.id === updated.id ? updated : i)),
                )
              }
            />
          ) : (
            <ProfileSectionSkeleton />
          )}
        </TabsPanel>
        <TabsPanel value="vacancies">
          <VacanciesSection />
        </TabsPanel>
        <TabsPanel value="applications">
          {applications ? (
            <MyApplicationsSection applications={applications} />
          ) : (
            <ProfileSectionSkeleton />
          )}
        </TabsPanel>
        <TabsPanel value="settings">
          {profile ? (
            <SettingsSection profile={profile} onSaved={setProfile} />
          ) : (
            <ProfileSectionSkeleton />
          )}
        </TabsPanel>
      </Tabs>
    </div>
  )
}
