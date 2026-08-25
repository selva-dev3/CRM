import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Button } from './button'
import { ButtonGroup } from './button-group'

describe('ButtonGroup', () => {
  it('groups related actions with an accessible label', () => {
    render(
      <ButtonGroup aria-label="Pagination controls">
        <Button>Previous</Button>
        <Button>Next</Button>
      </ButtonGroup>,
    )

    const group = screen.getByRole('group', { name: 'Pagination controls' })
    expect(group).toHaveAttribute('data-orientation', 'horizontal')
    expect(screen.getAllByRole('button')).toHaveLength(2)
  })
})
