import { statusLabels } from '../../constants/statusLabels';

interface StatusBadgeProps {
  status: string;
  /** Extra class for page-specific badge styling (default: status-badge). */
  className?: string;
}

/** Appointment status badge with human-readable label (single copy). */
export default function StatusBadge({ status, className = 'status-badge' }: StatusBadgeProps) {
  return <span className={`${className} status-${status}`}>{statusLabels[status] || status}</span>;
}
