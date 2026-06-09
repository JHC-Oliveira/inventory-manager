export default function ProductsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          <div className="h-5 w-2/3 animate-pulse rounded bg-slate-800" />
          <div className="mt-2 h-4 w-1/3 animate-pulse rounded bg-slate-800" />
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="h-16 animate-pulse rounded-lg bg-slate-800" />
            <div className="h-16 animate-pulse rounded-lg bg-slate-800" />
          </div>
        </div>
      ))}
    </div>
  )
}