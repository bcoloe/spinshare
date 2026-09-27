import { describe, it, expect } from 'vitest'
import { canGuessAlbum, nominatorUsernames } from './nominators'

const MEMBERS = [
  { user_id: 1, username: 'kate' },
  { user_id: 2, username: 'alex' },
  { user_id: 3, username: 'sam' },
]

describe('nominatorUsernames', () => {
  it('returns every co-nominator, alphabetised', () => {
    expect(nominatorUsernames({ added_by: 1, nominator_user_ids: [1, 3, 2] }, MEMBERS))
      .toEqual(['alex', 'kate', 'sam'])
  })

  it('falls back to added_by when nominator_user_ids is empty', () => {
    expect(nominatorUsernames({ added_by: 3, nominator_user_ids: [] }, MEMBERS)).toEqual(['sam'])
  })

  it('returns nothing for a chaos pick', () => {
    expect(nominatorUsernames({ added_by: null, nominator_user_ids: [] }, MEMBERS)).toEqual([])
  })

  it('omits nominators who are no longer members and de-duplicates', () => {
    expect(nominatorUsernames({ added_by: 1, nominator_user_ids: [1, 1, 99] }, MEMBERS))
      .toEqual(['kate'])
  })
})

describe('canGuessAlbum', () => {
  it('asks members other than the nominator to guess', () => {
    expect(canGuessAlbum({ added_by: 1 }, 2, true)).toBe(true)
  })

  it('never asks the nominator to guess their own pick', () => {
    expect(canGuessAlbum({ added_by: 1 }, 1, true)).toBe(false)
  })

  it('asks nobody to guess when guessing is off', () => {
    expect(canGuessAlbum({ added_by: 1 }, 2, false)).toBe(false)
  })
})
