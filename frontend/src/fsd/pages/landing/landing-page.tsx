import { HeroSection } from '@/fsd/widgets/landing/hero-section'
import { HowItWorksSection } from '@/fsd/widgets/landing/how-it-works-section'
import { LandingFooter } from '@/fsd/widgets/landing/landing-footer'
import { LandingHeader } from '@/fsd/widgets/landing/landing-header'
import { PrinciplesSection } from '@/fsd/widgets/landing/principles-section'

export function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <LandingHeader />
      <main className="flex-1">
        <HeroSection />
        <HowItWorksSection />
        <PrinciplesSection />
      </main>
      <LandingFooter />
    </div>
  )
}
