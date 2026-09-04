import type { ServiceStatus } from '@/types/health'

interface ServiceStatusCardProps {
  services: ServiceStatus[]
}

export function ServiceStatusCard({ services }: ServiceStatusCardProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="mb-3 text-xs font-medium text-muted-foreground">Service Status</p>
      <div className="space-y-2">
        {services.map((service) => {
          const ok = service.status === 'ok'
          return (
            <div key={service.name} className="flex items-start gap-2.5">
              <span
                className={`mt-1.5 size-2 shrink-0 rounded-full ${ok ? 'bg-emerald-500' : 'bg-red-500'}`}
                aria-hidden
              />
              <p className="text-sm text-foreground">
                <span className="font-medium capitalize">{service.name}</span>
                {service.detail && (
                  <span className="text-muted-foreground"> — {service.detail}</span>
                )}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
