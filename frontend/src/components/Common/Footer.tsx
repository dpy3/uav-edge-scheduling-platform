export function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="border-t py-4 px-6">
      <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
        <p className="text-muted-foreground text-sm">
          UAV Edge Scheduling Platform - {currentYear}
        </p>
        <p className="text-muted-foreground text-sm">Optimization algorithms and engineering practice</p>
      </div>
    </footer>
  )
}
