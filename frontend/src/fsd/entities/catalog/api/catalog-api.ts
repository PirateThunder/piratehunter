import { api } from '@/fsd/shared/api/http'
import type { Catalog } from '@/fsd/shared/api/types'

/** GET /catalog — специализации и грейды (публичный, кэшируется backend'ом). */
export function fetchCatalog() {
  return api.get('catalog').json<Catalog>()
}
