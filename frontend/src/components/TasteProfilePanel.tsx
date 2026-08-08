import { useProfile } from '../queries'
import { ApiError } from '../api'
import Spinner from './Spinner'
import TasteProfileView from './TasteProfileView'

interface Props {
  userId: string
}

export default function TasteProfilePanel({ userId }: Props) {
  const { data, isLoading, isError, error } = useProfile(userId)

  return (
    <section className="taste-profile-panel">
      <h2>Taste profile</h2>
      {isLoading && <Spinner />}
      {isError && error instanceof ApiError && error.status === 404 && (
        <p className="taste-profile-panel__empty">
          No taste profile yet — run recommendations once to generate one.
        </p>
      )}
      {data && <TasteProfileView profile={data} />}
    </section>
  )
}
