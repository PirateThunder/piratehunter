import type { InvitationStatus } from '@/fsd/shared/api/types'
import { Badge } from '@/fsd/shared/ui/badge'

const STATUS_META: Record<
  InvitationStatus,
  { label: string; variant: 'default' | 'accent' | 'success' | 'danger' }
> = {
  sent: { label: 'отправлено', variant: 'accent' },
  viewed: { label: 'просмотрено', variant: 'default' },
  accepted: { label: 'принято', variant: 'success' },
  declined: { label: 'отклонено', variant: 'danger' },
}

export function InvitationStatusBadge({ status }: { status: InvitationStatus }) {
  const meta = STATUS_META[status]
  return <Badge variant={meta.variant}>{meta.label}</Badge>
}
