import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import RichText from './RichText'

function renderText(props: Parameters<typeof RichText>[0]) {
  return render(
    <MantineProvider>
      <RichText {...props} />
    </MantineProvider>,
  )
}

describe('RichText', () => {
  it('renders bold and italic as strong and em', () => {
    renderText({ text: '**loud** and *soft*' })
    expect(screen.getByText('loud').tagName).toBe('STRONG')
    expect(screen.getByText('soft').tagName).toBe('EM')
  })

  it('renders markup-looking text literally', () => {
    const { container } = renderText({ text: '<b>not bold</b>' })
    expect(container.querySelector('b')).toBeNull()
    expect(screen.getByText('<b>not bold</b>')).toBeInTheDocument()
  })

  it('highlights resolved mentions inside formatting', () => {
    renderText({ text: '**hey @bob**', mentions: [{ user_id: 2, username: 'bob' }] })
    const mention = screen.getByText('@bob')
    expect(mention.tagName).toBe('SPAN')
    expect(mention.closest('strong')).not.toBeNull()
  })
})
