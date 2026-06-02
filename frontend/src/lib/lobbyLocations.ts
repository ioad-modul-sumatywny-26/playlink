export interface LobbyLocation {
	code: string;
	label: string;
	lat: number;
	lon: number;
}

export const FALLBACK_LOBBY_LOCATIONS: LobbyLocation[] = [
	{ code: 'na-east', label: 'North America East', lat: 39.0, lon: -77.0 },
	{ code: 'na-west', label: 'North America West', lat: 37.8, lon: -122.4 },
	{ code: 'eu-west', label: 'Europe West', lat: 51.5, lon: -0.1 },
	{ code: 'eu-central', label: 'Europe Central', lat: 50.1, lon: 8.7 },
	{ code: 'eu-north', label: 'Europe North', lat: 59.3, lon: 18.1 },
	{ code: 'sa-east', label: 'South America East', lat: -23.6, lon: -46.6 },
	{ code: 'asia-east', label: 'Asia East', lat: 35.7, lon: 139.7 },
	{ code: 'asia-south', label: 'Asia South', lat: 1.3, lon: 103.8 },
	{ code: 'oceania', label: 'Oceania', lat: -33.9, lon: 151.2 },
	{ code: 'africa-south', label: 'Africa South', lat: -26.2, lon: 28.0 }
];

export const FALLBACK_LOBBY_LOCATION = 'eu-central';

export function isLobbyLocation(value: unknown): value is LobbyLocation {
	if (typeof value !== 'object' || value === null) return false;
	const location = value as Record<string, unknown>;
	return (
		typeof location.code === 'string' &&
		typeof location.label === 'string' &&
		typeof location.lat === 'number' &&
		typeof location.lon === 'number'
	);
}

export function lobbyLocationLabel(locations: LobbyLocation[], code: string): string {
	return locations.find((location) => location.code === code)?.label ?? code;
}

export function distanceKm(a: Pick<LobbyLocation, 'lat' | 'lon'>, b: Pick<LobbyLocation, 'lat' | 'lon'>) {
	const toRad = (deg: number) => (deg * Math.PI) / 180;
	const earthRadiusKm = 6371;
	const dLat = toRad(b.lat - a.lat);
	const dLon = toRad(b.lon - a.lon);
	const lat1 = toRad(a.lat);
	const lat2 = toRad(b.lat);
	const h =
		Math.sin(dLat / 2) ** 2 +
		Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
	return 2 * earthRadiusKm * Math.asin(Math.sqrt(h));
}

export function nearestLobbyLocation(
	locations: LobbyLocation[],
	coords: Pick<LobbyLocation, 'lat' | 'lon'>
): LobbyLocation | null {
	let nearest: LobbyLocation | null = null;
	let nearestDistance = Number.POSITIVE_INFINITY;
	for (const location of locations) {
		const d = distanceKm(coords, location);
		if (d < nearestDistance) {
			nearestDistance = d;
			nearest = location;
		}
	}
	return nearest;
}
