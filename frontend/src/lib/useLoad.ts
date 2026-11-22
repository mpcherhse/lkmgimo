import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from './api'

/** загрузка данных страницы: состояние загрузки, ошибка, повтор */
export function useLoad<T>(url: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(!!url)
  const seq = useRef(0)
  const load = useCallback(async (quiet = false) => {
    if (!url) return
    const my = ++seq.current
    if (!quiet) setLoading(true)
    setError(null)
    try {
      const d = await api.get<T>(url)
      if (my === seq.current) setData(d)
    } catch (e) {
      if (my === seq.current) setError(e as ApiError)
    } finally {
      if (my === seq.current) setLoading(false)
    }
  }, [url])
  useEffect(() => { load() }, [load])
  return { data, error, loading, reload: load, setData }
}
