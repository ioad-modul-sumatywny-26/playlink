import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';
import { writable, type Readable } from 'svelte/store';

// ---------- Public types ----------

export interface ChatMessage {
	id: number;
	sender_address: string;
	sender_username: string;
	content: string;
	created_at: string;
}

export interface RoomMember {
	address: string;
	username: string;
}

export type RsvpStatus = 'present' | 'absent' | 'maybe';

export interface RsvpEntry {
	address: string;
	username: string;
	status: RsvpStatus;
	updated_at: string;
}

export interface RoomEventState {
	starts_at: string;
	ends_at: string;
	created_by: string;
	created_at: string;
	updated_at: string;
	rsvps: RsvpEntry[];
}

// ---------- Frame types (private) ----------

interface HistoryFrame {
	type: 'history';
	messages: ChatMessage[];
}

interface MessageFrame {
	type: 'message';
	message: ChatMessage;
}

interface EventUpdateFrame {
	type: 'event_update';
	event: RoomEventState | null;
}

interface RsvpUpdateFrame {
	type: 'rsvp_update';
	rsvp: RsvpEntry;
}

interface RosterUpdateFrame {
	type: 'roster_update';
	members: RoomMember[];
}

interface RoomClosedFrame {
	type: 'room_closed';
	room: string;
}

type ChatFrame =
	| HistoryFrame
	| MessageFrame
	| EventUpdateFrame
	| RsvpUpdateFrame
	| RosterUpdateFrame
	| RoomClosedFrame;

// ---------- Frame validation ----------

function isChatMessage(value: unknown): value is ChatMessage {
	if (typeof value !== 'object' || value === null) return false;
	const m = value as Record<string, unknown>;
	return (
		typeof m.id === 'number' &&
		typeof m.sender_address === 'string' &&
		typeof m.sender_username === 'string' &&
		typeof m.content === 'string' &&
		typeof m.created_at === 'string'
	);
}

function isRoomMember(value: unknown): value is RoomMember {
	if (typeof value !== 'object' || value === null) return false;
	const m = value as Record<string, unknown>;
	return typeof m.address === 'string' && typeof m.username === 'string';
}

function isRsvpStatus(value: unknown): value is RsvpStatus {
	return value === 'present' || value === 'absent' || value === 'maybe';
}

function isRsvpEntry(value: unknown): value is RsvpEntry {
	if (typeof value !== 'object' || value === null) return false;
	const r = value as Record<string, unknown>;
	return (
		typeof r.address === 'string' &&
		typeof r.username === 'string' &&
		isRsvpStatus(r.status) &&
		typeof r.updated_at === 'string'
	);
}

function isRoomEventState(value: unknown): value is RoomEventState {
	if (typeof value !== 'object' || value === null) return false;
	const e = value as Record<string, unknown>;
	return (
		typeof e.starts_at === 'string' &&
		typeof e.ends_at === 'string' &&
		typeof e.created_by === 'string' &&
		typeof e.created_at === 'string' &&
		typeof e.updated_at === 'string' &&
		Array.isArray(e.rsvps) &&
		e.rsvps.every(isRsvpEntry)
	);
}

function parseFrame(raw: string): ChatFrame | null {
	let data: unknown;
	try {
		data = JSON.parse(raw);
	} catch {
		return null;
	}
	if (typeof data !== 'object' || data === null) return null;
	const f = data as Record<string, unknown>;
	if (f.type === 'history' && Array.isArray(f.messages) && f.messages.every(isChatMessage)) {
		return { type: 'history', messages: f.messages as ChatMessage[] };
	}
	if (f.type === 'message' && isChatMessage(f.message)) {
		return { type: 'message', message: f.message };
	}
	if (f.type === 'event_update' && (f.event === null || isRoomEventState(f.event))) {
		return {
			type: 'event_update',
			event: f.event as RoomEventState | null
		};
	}
	if (f.type === 'rsvp_update' && isRsvpEntry(f.rsvp)) {
		return { type: 'rsvp_update', rsvp: f.rsvp };
	}
	if (f.type === 'roster_update' && Array.isArray(f.members) && f.members.every(isRoomMember)) {
		return { type: 'roster_update', members: f.members as RoomMember[] };
	}
	if (f.type === 'room_closed' && typeof f.room === 'string') {
		return { type: 'room_closed', room: f.room };
	}
	return null;
}

// ---------- Store ----------

export interface ChatStore {
	/** Live chat history for the room. */
	messages: Readable<ChatMessage[]>;
	/** Current scheduled event (or null when none / not yet observed). */
	event: Readable<RoomEventState | null>;
	/** Live room roster (address + username), updated as members join/leave. */
	members: Readable<RoomMember[]>;
	/** Becomes `true` when an admin closes the room (`room_closed` frame). */
	closed: Readable<boolean>;
	send(content: string): void;
	destroy(): void;
}

export interface CreateChatStoreOptions {
	/** Initial event state from SSR, if any. Avoids a flash of empty content. */
	initialEvent?: RoomEventState | null;
	/** Initial member roster from SSR, used until the first WS update. */
	initialMembers?: RoomMember[];
}

export function createChatStore(
	roomName: string,
	token: string,
	options: CreateChatStoreOptions = {}
): ChatStore {
	const messages = writable<ChatMessage[]>([]);
	const event = writable<RoomEventState | null>(options.initialEvent ?? null);
	const members = writable<RoomMember[]>(options.initialMembers ?? []);
	const closed = writable<boolean>(false);

	let ws: WebSocket | null = null;
	let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
	let reconnectAttempts = 0;
	let isTornDown = false;
	const baseDelayMs = 1000;
	const maxDelayMs = 30000;

	function applyRsvpUpdate(rsvp: RsvpEntry) {
		event.update((current) => {
			if (!current) return current;
			const filtered = current.rsvps.filter(
				(r) => r.address.toLowerCase() !== rsvp.address.toLowerCase()
			);
			return { ...current, rsvps: [...filtered, rsvp] };
		});
	}

	function connect() {
		const wsUrl = env.PUBLIC_WS_URL;
		if (!wsUrl) {
			console.error('Missing PUBLIC_WS_URL');
			return;
		}
		const url =
			`${wsUrl}/ws/rooms/${encodeURIComponent(roomName)}/chat` +
			`?token=${encodeURIComponent(token)}`;
		ws = new WebSocket(url);

		ws.onopen = () => {
			reconnectAttempts = 0;
		};

		ws.onmessage = (frameEvent: MessageEvent<string>) => {
			const frame = parseFrame(frameEvent.data);
			if (!frame) {
				console.error('Bad chat frame', frameEvent.data);
				return;
			}
			switch (frame.type) {
				case 'history':
					messages.set(frame.messages);
					break;
				case 'message':
					messages.update((msgs) => [...msgs, frame.message]);
					break;
				case 'event_update':
					event.set(frame.event);
					break;
				case 'rsvp_update':
					applyRsvpUpdate(frame.rsvp);
					break;
				case 'roster_update':
					members.set(frame.members);
					break;
				case 'room_closed':
					// The room is gone. Flag it, tear down the socket and suppress any
					// reconnect attempts — the page will redirect the user out.
					closed.set(true);
					isTornDown = true;
					if (reconnectTimeout) clearTimeout(reconnectTimeout);
					ws?.close();
					break;
			}
		};

		ws.onclose = () => {
			scheduleReconnect();
		};

		ws.onerror = () => {
			ws?.close();
		};
	}

	function scheduleReconnect() {
		if (isTornDown) return;
		if (reconnectTimeout) clearTimeout(reconnectTimeout);
		const exp = Math.min(maxDelayMs, baseDelayMs * Math.pow(2, reconnectAttempts));
		const jitter = Math.random() * (exp * 0.5);
		reconnectAttempts += 1;
		reconnectTimeout = setTimeout(connect, exp + jitter);
	}

	if (browser) {
		connect();
	}

	return {
		messages: { subscribe: messages.subscribe },
		event: { subscribe: event.subscribe },
		members: { subscribe: members.subscribe },
		closed: { subscribe: closed.subscribe },
		send(content: string) {
			const trimmed = content.trim();
			if (!trimmed || !ws || ws.readyState !== WebSocket.OPEN) return;
			ws.send(JSON.stringify({ content: trimmed }));
		},
		destroy() {
			isTornDown = true;
			if (reconnectTimeout) clearTimeout(reconnectTimeout);
			if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
				ws.close();
			}
		}
	};
}
