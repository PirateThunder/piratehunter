/**
 * Central env access. NEXT_PUBLIC_* values are inlined into the client bundle
 * at build time — rebuilding the image is required to change them.
 * No backend URL here on purpose: the browser only talks to same-origin /api/*.
 */
export const env = {
  /** Dev-only demo-account login (POST /auth/dev). Hidden unless '1'. */
  devLogin: process.env.NEXT_PUBLIC_DEV_LOGIN === '1',
  /** Phase-2 default is live data; '1' forces typed mock fixtures (offline dev). */
  apiMock: process.env.NEXT_PUBLIC_API_MOCK === '1',
} as const
