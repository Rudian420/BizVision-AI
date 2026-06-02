// Re-export the shared `RiskBadge` so existing recruitment imports
// keep working. The recruitment `RiskLevel` is structurally
// compatible with the shared one — both mirror the backend's
// `common.RiskLevel` enum.
export { RiskBadge } from '@/components/common/RiskBadge';
