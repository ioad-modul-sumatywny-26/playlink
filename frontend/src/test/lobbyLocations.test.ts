import { describe, expect, it } from 'vitest';

import {
	FALLBACK_LOBBY_LOCATIONS,
	FALLBACK_LOBBY_LOCATION,
	isLobbyLocation,
	lobbyLocationLabel,
	distanceKm,
	nearestLobbyLocation
} from '$lib/lobbyLocations';

describe('isLobbyLocation', () => {
	it('accepts valid locations', () => {
		expect(
			isLobbyLocation({
				code: 'eu-central',
				label: 'Europe Central',
				lat: 50.1,
				lon: 8.7
			})
		).toBe(true);
	});

	it('rejects invalid locations', () => {
		expect(
			isLobbyLocation({
				code: 'eu-central',
				label: 'Europe Central',
				lat: '50.1',
				lon: 8.7
			})
		).toBe(false);
	});

	it('rejects null', () => {
		expect(isLobbyLocation(null)).toBe(false);
	});
});

describe('lobbyLocationLabel', () => {
	it('returns matching label', () => {
		const label = lobbyLocationLabel(FALLBACK_LOBBY_LOCATIONS, 'eu-central');

		expect(label).toBe('Europe Central');
	});

	it('returns code when location is missing', () => {
		expect(lobbyLocationLabel([], 'unknown')).toBe('unknown');
	});
});

describe('distanceKm', () => {
	it('returns zero for same coordinates', () => {
		const distance = distanceKm(
			{
				lat: 50,
				lon: 10
			},
			{
				lat: 50,
				lon: 10
			}
		);

		expect(distance).toBeCloseTo(0);
	});

	it('calculates distance between locations', () => {
		const distance = distanceKm(
			{
				lat: 51.5,
				lon: -0.1
			},
			{
				lat: 50.1,
				lon: 8.7
			}
		);

		// London -> Frankfurt roughly 640km
		expect(distance).toBeGreaterThan(500);
		expect(distance).toBeLessThan(800);
	});
});

describe('nearestLobbyLocation', () => {
	it('finds nearest location', () => {
		const nearest = nearestLobbyLocation(FALLBACK_LOBBY_LOCATIONS, {
			lat: 51.5,
			lon: -0.1
		});

		expect(nearest?.code).toBe('eu-west');
	});

	it('returns null for empty list', () => {
		expect(
			nearestLobbyLocation([], {
				lat: 0,
				lon: 0
			})
		).toBe(null);
	});

	it('has a valid fallback location', () => {
		const fallback = FALLBACK_LOBBY_LOCATIONS.find((x) => x.code === FALLBACK_LOBBY_LOCATION);

		expect(fallback).toBeDefined();
	});
});
