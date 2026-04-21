import { useParams, Navigate } from 'react-router-dom'

export default function DailySpinPage() {
  const { groupId } = useParams<{ groupId: string }>()
  return <Navigate to={`/groups/${groupId}`} replace />
}
