import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ActionMenu } from './action-menu'
import { PERMISSIONS } from '@/lib/permissions'

function setPermissions(permissions: string[]): void {
  window.localStorage.setItem('user', JSON.stringify({ permissions }))
}

afterEach(() => {
  window.localStorage.clear()
  window.sessionStorage.clear()
})

describe('ActionMenu', () => {
  it('filters actions by permission and invokes the original handler', async () => {
    const user = userEvent.setup()
    const edit = vi.fn()
    const remove = vi.fn()
    setPermissions([PERMISSIONS.CONTACTS.UPDATE])

    render(
      <ActionMenu
        label="More"
        actions={[
          { label: 'Edit contact', permission: PERMISSIONS.CONTACTS.UPDATE, onSelect: edit },
          { label: 'Delete contact', permission: PERMISSIONS.CONTACTS.DELETE, variant: 'destructive', onSelect: remove },
        ]}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'More' }))
    await user.click(screen.getByRole('menuitem', { name: 'Edit contact' }))

    expect(edit).toHaveBeenCalledOnce()
    expect(remove).not.toHaveBeenCalled()
    expect(screen.queryByText('Delete contact')).not.toBeInTheDocument()
  })

  it('supports keyboard navigation and distinguishes destructive actions', async () => {
    const user = userEvent.setup()
    const remove = vi.fn()
    setPermissions(['all'])

    render(
      <ActionMenu
        iconOnly
        label="Open row actions"
        actions={[
          { label: 'View contact', onSelect: vi.fn() },
          { label: 'Delete contact', variant: 'destructive', onSelect: remove },
        ]}
      />,
    )

    const trigger = screen.getByRole('button', { name: 'Open row actions' })
    trigger.focus()
    await user.keyboard('{Enter}')

    const deleteItem = await screen.findByRole('menuitem', { name: 'Delete contact' })
    expect(deleteItem).toHaveAttribute('data-variant', 'destructive')

    await user.keyboard('{End}{Enter}')
    expect(remove).toHaveBeenCalledOnce()
  })

  it('does not render an empty overflow trigger', () => {
    setPermissions([PERMISSIONS.CONTACTS.READ])
    render(
      <ActionMenu
        label="More"
        actions={[{ label: 'Delete contact', permission: PERMISSIONS.CONTACTS.DELETE, onSelect: vi.fn() }]}
      />,
    )

    expect(screen.queryByRole('button', { name: 'More' })).not.toBeInTheDocument()
  })
})
