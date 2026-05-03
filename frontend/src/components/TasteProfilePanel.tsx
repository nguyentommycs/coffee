import { useProfile } from '../queries'
import { ApiError } from '../api'
import Spinner from './Spinner'

interface Props {
  userId: string
}

function listOrNone(items: string[]): string {
  return items.length > 0 ? items.join(', ') : 'None'
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
      {data && (
        <div className="taste-profile-panel__content">
          <p className="taste-profile-panel__summary">{data.narrative_summary}</p>
          <table className="taste-profile-panel__table">
            <tbody>
              <tr>
                <th>Preferred origins</th>
                <td>{listOrNone(data.preferred_origins)}</td>
              </tr>
              <tr>
                <th>Preferred processes</th>
                <td>{listOrNone(data.preferred_processes)}</td>
              </tr>
              <tr>
                <th>Preferred roast levels</th>
                <td>{listOrNone(data.preferred_roast_levels)}</td>
              </tr>
              <tr>
                <th>Flavor affinities</th>
                <td>{listOrNone(data.flavor_affinities)}</td>
              </tr>
              <tr>
                <th>Avoided flavors</th>
                <td>{listOrNone(data.avoided_flavors)}</td>
              </tr>
              <tr>
                <th>Beans logged</th>
                <td>{data.total_beans_logged}</td>
              </tr>
              <tr>
                <th>Confidence</th>
                <td>{Math.round(data.profile_confidence * 100)}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
