import { useBeans } from '../queries'
import AddBeanForm from './AddBeanForm'
import BeanTable from './BeanTable'
import Spinner from './Spinner'

interface Props {
  userId: string
}

export default function BeansPanel({ userId }: Props) {
  const { data: beans, isLoading } = useBeans(userId)

  return (
    <section className="beans-panel">
      <div className="beans-panel__left">
        <AddBeanForm userId={userId} />
      </div>
      <div className="beans-panel__right">
        <h2>Your beans</h2>
        {isLoading ? <Spinner /> : <BeanTable beans={beans ?? []} />}
      </div>
    </section>
  )
}
