import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';
import { writable, type Readable } from 'svelte/store';

export interface RoomSummary {
	name: string;
	game: string;
	players_active: number;
	players_max: number;
	member_addresses: string[];
	expires_at: string;
}

function isRoomSummary(value: unknown): value is RoomSummary {
	if (typeof value !== 'object' || value === null) {
		return false;
	}

	const room = value as Record<string, unknown>;

	return (
		typeof room.name === 'string' &&
		typeof room.game === 'string' &&
		typeof room.players_active === 'number' &&
		typeof room.players_max === 'number' &&
		Array.isArray(room.member_addresses) &&
		typeof room.expires_at === 'string'
	);
}

function createRoomsStore(): Readable<RoomSummary[]> & { destroy(): void } {
	const { subscribe, set } = writable<RoomSummary[]>([]);

	let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
	let ws: WebSocket | null = null;
	let reconnectAttempts = 0;
	const baseReconnectDelayMs = 1000;
	const maxReconnectDelayMs = 30000;
	let isTornDown = false;

	function connect() {
		const wsUrl = env.PUBLIC_WS_URL;
		if (!wsUrl) {
			console.error('Missing PUBLIC_WS_URL');
			return;
		}

		ws = new WebSocket(`${wsUrl}/ws/rooms`);

		ws.onopen = () => {
			console.log('WebSocket connected');
			reconnectAttempts = 0;
		};

		ws.onmessage = (event: MessageEvent<string>) => {
			let data: unknown;
			try {
				data = JSON.parse(event.data);
			} catch (error) {
				console.error('Failed to parse rooms WebSocket message', error, event.data);
				return;
			}

			if (!Array.isArray(data) || !data.every(isRoomSummary)) {
				console.error('Unexpected rooms WebSocket payload, expected an array of rooms', data);
				return;
			}

			set(data);
		};

		ws.onclose = () => {
			console.log('WebSocket disconnected, retrying...');
			reconnect();
		};

		ws.onerror = () => {
			ws?.close();
		};
	}

	function reconnect() {
		if (isTornDown) {
			return;
		}

		if (reconnectTimeout) {
			clearTimeout(reconnectTimeout);
		}

		const expDelay = Math.min(
			maxReconnectDelayMs,
			baseReconnectDelayMs * Math.pow(2, reconnectAttempts)
		);
		const jitter = Math.random() * (expDelay * 0.5);
		const delay = expDelay + jitter;

		reconnectAttempts += 1;
		reconnectTimeout = setTimeout(connect, delay);
	}

	if (browser) {
		connect();
	}

	return {
		subscribe,
		destroy() {
			isTornDown = true;
			if (reconnectTimeout) {
				clearTimeout(reconnectTimeout);
			}
			if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
				ws.close();
			}
		}
	};
}

export const roomsStore = createRoomsStore();
