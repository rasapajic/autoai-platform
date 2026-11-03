export type ModelOption = { model: string; count: number }

export function prepareModelOptions(data: unknown): ModelOption[] {
  if (!Array.isArray(data)) throw new Error('Neispravan odgovor za modele')
  const grouped = new Map<string, ModelOption>()
  for (const row of data) {
    if (typeof row?.model !== 'string' || !row.model.trim() || !Number.isInteger(row.count) || row.count <= 0) continue
    const key = row.model.toLowerCase()
    const previous = grouped.get(key)
    grouped.set(key, { model: previous?.model || row.model, count: (previous?.count || 0) + row.count })
  }
  return [...grouped.values()].sort((a, b) => a.model.localeCompare(b.model, 'sr', { sensitivity: 'base', numeric: true }))
}

export function changeListingFilter<T extends { make: string; model: string; page: number }>(filters: T, key: string, value: any): T {
  return {
    ...filters, [key]: value, page: key === 'page' ? value : 1,
    ...(key === 'make' ? { model: '', model_exact: false } : {}),
    ...(key === 'model' ? { model_exact: Boolean(value) } : {}),
  }
}

export function mergeParsedFilters<T extends { make: string; model: string; model_exact: boolean; page: number }>(filters: T, parsed: Partial<T>): T {
  const makeChanged = parsed.make !== undefined && parsed.make !== filters.make
  return {
    ...filters, ...parsed,
    ...(makeChanged && parsed.model === undefined ? { model: '' } : {}),
    model_exact: parsed.model !== undefined || makeChanged ? false : filters.model_exact,
    page: 1,
  }
}
