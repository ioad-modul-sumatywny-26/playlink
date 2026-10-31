import { describe, expect, it, vi } from 'vitest';

vi.mock('$env/dynamic/public', () => ({
	env: {
		PUBLIC_REGION: 'eu',
		PUBLIC_ENTRY_HOST: '127.0.0.1:3000',
		PUBLIC_REGION_EU_FRONTEND: 'http://localhost:3000',
		PUBLIC_REGION_EU_API: 'http://localhost:8000',
		PUBLIC_REGION_EU_WS: 'ws://localhost:8000',
		PUBLIC_REGION_US_FRONTEND: 'http://localhost:3001',
		PUBLIC_REGION_US_API: 'http://localhost:8001',
		PUBLIC_REGION_US_WS: 'ws://localhost:8001'
	}
}));

vi.mock('$app/environment', () => ({
	dev: true,
	browser: false
}));

import { isMeaningfullyFaster, liveRegionsSorted, type ProbeResult } from '$lib/regions';

describe('isMeaningfullyFaster', () => {
	it('rejects nulls and non-improvements', () => {
		expect(isMeaningfullyFaster(null, 100)).toBe(false);
		expect(isMeaningfullyFaster(100, null)).toBe(false);
		expect(isMeaningfullyFaster(120, 100)).toBe(false);
		expect(isMeaningfullyFaster(100, 100)).toBe(false);
	});

	it('accepts clear absolute improvement', () => {
		expect(isMeaningfullyFaster(50, 100, { minDeltaMs: 25, minRatio: 0.85 })).toBe(true);
	});

	it('accepts clear relative improvement', () => {
		expect(isMeaningfullyFaster(80, 100, { minDeltaMs: 50, minRatio: 0.85 })).toBe(true);
	});

	it('rejects tiny noise under strict thresholds', () => {
		expect(isMeaningfullyFaster(98, 100, { minDeltaMs: 25, minRatio: 0.85 })).toBe(false);
	});
});

describe('liveRegionsSorted', () => {
	it('keeps only live probes and sorts by latency', () => {
		const input: ProbeResult[] = [
			{
				region: { id: 'us', label: 'USA', frontend: '', api: '', ws: '', healthPath: '/h' },
				ok: true,
				ms: 40
			},
			{
				region: { id: 'eu', label: 'Europa', frontend: '', api: '', ws: '', healthPath: '/h' },
				ok: false,
				ms: null
			},
			{
				region: { id: 'eu', label: 'Europa', frontend: '', api: '', ws: '', healthPath: '/h' },
				ok: true,
				ms: 12
			}
		];
		const live = liveRegionsSorted(input);
		expect(live).toHaveLength(2);
		expect(live[0].ms).toBe(12);
		expect(live[1].ms).toBe(40);
	});
});
