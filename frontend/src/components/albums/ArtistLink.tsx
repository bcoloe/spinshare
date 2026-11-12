import { Anchor, type AnchorProps } from '@mantine/core'
import { Link } from 'react-router-dom'
import { artistPath } from '../../utils/artistPath'

interface Props extends AnchorProps {
  artist: string
}

/**
 * An artist name that routes to the artist's overview page.
 *
 * Click events stop propagating so the link can sit inside clickable rows and
 * cards (e.g. review history) without also triggering the row's own action.
 */
export default function ArtistLink({ artist, c = 'dimmed', ...anchorProps }: Props) {
  return (
    <Anchor
      component={Link}
      to={artistPath(artist)}
      c={c}
      underline="hover"
      onClick={(e) => e.stopPropagation()}
      {...anchorProps}
    >
      {artist}
    </Anchor>
  )
}
