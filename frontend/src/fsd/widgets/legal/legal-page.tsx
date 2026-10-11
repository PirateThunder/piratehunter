import Link from 'next/link'

/** Placeholder legal page (terms / privacy) — full text lands before launch. */
export function LegalPage({ title }: { title: string }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-4 py-16">
      <h1 className="text-3xl font-bold text-heading">{title}</h1>
      <p className="text-muted-foreground">
        Документ готовится к публикации. По вопросам обработки персональных данных (152-ФЗ)
        обращайтесь к команде проекта.
      </p>
      <Link href="/" className="text-primary hover:underline">
        ← На главную
      </Link>
    </main>
  )
}
