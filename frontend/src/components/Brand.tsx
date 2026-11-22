/** Собственный знак концепта (не логотип вуза): папка-досье с отметкой — «дела студента в одном месте». */
export function BrandMark({ className = 'brand-mark' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 36 36" aria-hidden="true">
      <rect width="36" height="36" rx="8" fill="#ffffff" />
      <rect x="0.5" y="0.5" width="35" height="35" rx="7.5" fill="none" stroke="#c9d3ea" />
      <path d="M8 12.5a2 2 0 0 1 2-2h5.2l2 2.2H26a2 2 0 0 1 2 2V25a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2z" fill="#22396b" />
      <path d="M13.5 19.6l3 3 6-6.2" fill="none" stroke="#ffffff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="27.5" cy="9" r="3" fill="#b3261e" />
    </svg>
  )
}

export function Brand({ sub = true }: { sub?: boolean }) {
  return (
    <>
      <BrandMark />
      <span>
        <span className="brand-name">Цифровой деканат</span>
        {sub && <span className="brand-sub">личный кабинет · концепт</span>}
      </span>
    </>
  )
}
