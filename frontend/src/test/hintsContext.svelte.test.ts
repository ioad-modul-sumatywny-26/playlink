import { describe, expect, it } from 'vitest';
import { HintsState } from '$lib/hintsContext.svelte';

describe('HintsState', () => {
	it('initializes with provided hints', () => {
		const state = new HintsState([
			{
				key: 'welcome',
				label: 'Welcome'
			}
		]);

		expect(state.hints).toHaveLength(1);
		expect(state.hints[0].key).toBe('welcome');
	});

	it('starts empty by default', () => {
		const state = new HintsState();

		expect(state.hints).toEqual([]);
	});

	it('sets hints', () => {
		const state = new HintsState();

		state.set([
			{
				key: 'test',
				label: 'Hello',
				tone: 'gold'
			}
		]);

		expect(state.hints).toEqual([
			{
				key: 'test',
				label: 'Hello',
				tone: 'gold'
			}
		]);
	});

	it('clears hints', () => {
		const state = new HintsState([
			{
				key: 'remove',
				label: 'Delete me'
			}
		]);

		state.clear();

		expect(state.hints).toEqual([]);
	});
});
