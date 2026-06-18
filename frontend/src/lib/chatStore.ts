import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';
import { writable, type Readable } from 'svelte/store';
import { signChatMessage, type ChatSigner } from '$lib/signing';

// ---------- Public types ----------

export interface ChatMessage {
	id: number;
	sender_address: string;
	sender_username: string;
	content: string;
	created_at: string;
	kind?: 'user' | 'system';
	/** EIP-191 signature over the canonical payload, or null for legacy/unsigned. */
	signature?: string | null;
	/** Exact client timestamp that was signed, or null for legacy/unsigned. */
	sent_at?: string | null;
	/** True when the server recovered a valid signer for this message. */
	verified?: boolean;
}

export interface RoomMember {
	address: string;
	username: string;
	is_admin: boolean;
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

interface MemberKickedFrame {
	type: 'member_kicked';
	member_address: string;
	member_username: string;
	created_by: string;
	ownership_transferred: boolean;
}

/** Server rejected an inbound message (e.g. a signature that failed to verify). */
interface ErrorFrame {
	type: 'error';
	detail: string;
}

type ChatFrame =
	| HistoryFrame
	| MessageFrame
	| EventUpdateFrame
	| RsvpUpdateFrame
	| RosterUpdateFrame
	| RoomClosedFrame
	| MemberKickedFrame
	| ErrorFrame;

// ---------- Frame validation ----------

export function isChatMessage(value: unknown): value is ChatMessage {
	if (typeof value !== 'object' || value === null) return false;
	const m = value as Record<string, unknown>;
	return (
		typeof m.id === 'number' &&
		typeof m.sender_address === 'string' &&
		typeof m.sender_username === 'string' &&
		typeof m.content === 'string' &&
		typeof m.created_at === 'string' &&
		(m.kind === undefined || m.kind === 'user' || m.kind === 'system') &&
		(m.signature === undefined || m.signature === null || typeof m.signature === 'string') &&
		(m.sent_at === undefined || m.sent_at === null || typeof m.sent_at === 'string') &&
		(m.verified === undefined || typeof m.verified === 'boolean')
	);
}

export function isRoomMember(value: unknown): value is RoomMember {
	if (typeof value !== 'object' || value === null) return false;
	const m = value as Record<string, unknown>;
	return (
		typeof m.address === 'string' &&
		typeof m.username === 'string' &&
		typeof m.is_admin === 'boolean'
	);
}

export function isRsvpStatus(value: unknown): value is RsvpStatus {
	return value === 'present' || value === 'absent' || value === 'maybe';
}

export function isRsvpEntry(value: unknown): value is RsvpEntry {
	if (typeof value !== 'object' || value === null) return false;
	const r = value as Record<string, unknown>;
	return (
		typeof r.address === 'string' &&
		typeof r.username === 'string' &&
		isRsvpStatus(r.status) &&
		typeof r.updated_at === 'string'
	);
}

export function isRoomEventState(value: unknown): value is RoomEventState {
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

export function parseFrame(raw: string): ChatFrame | null {
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
	if (
		f.type === 'member_kicked' &&
		typeof f.member_address === 'string' &&
		typeof f.member_username === 'string' &&
		typeof f.created_by === 'string' &&
		typeof f.ownership_transferred === 'boolean'
	) {
		return f as unknown as MemberKickedFrame;
	}
	if (f.type === 'error' && typeof f.detail === 'string') {
		return { type: 'error', detail: f.detail };
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
	/** Current room owner, updated after creator kicks. */
	owner: Readable<string>;
	/** Becomes `true` when this client is removed from the room. */
	kicked: Readable<boolean>;
	send(content: string): Promise<void>;
	destroy(): void;
}

export interface CreateChatStoreOptions {
	/** Initial event state from SSR, if any. Avoids a flash of empty content. */
	initialEvent?: RoomEventState | null;
	/** Initial member roster from SSR, used until the first WS update. */
	initialMembers?: RoomMember[];
	/** Initial room owner from SSR. */
	initialOwner?: string;
	/** Address represented by this browser session. */
	currentAddress?: string;
	/**
	 * Key used to sign outgoing messages (issue #59). When absent, messages are
	 * sent unsigned and the server marks them unverified.
	 */
	signer?: ChatSigner | null;
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
	const owner = writable<string>(options.initialOwner ?? '');
	const kicked = writable<boolean>(false);

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
				case 'member_kicked':
					owner.set(frame.created_by);
					if (
						options.currentAddress &&
						frame.member_address.toLowerCase() === options.currentAddress.toLowerCase()
					) {
						kicked.set(true);
						isTornDown = true;
						if (reconnectTimeout) clearTimeout(reconnectTimeout);
					}
					break;
				case 'error':
					// The server rejected our last message (e.g. signature mismatch
					// or stale timestamp). It is never stored or broadcast.
					console.warn('Chat message rejected:', frame.detail);
					break;
			}
		};

		ws.onclose = (event) => {
			if (event.code === 4403 || event.code === 4409) {
				kicked.set(true);
				isTornDown = true;
				if (reconnectTimeout) clearTimeout(reconnectTimeout);
				return;
			}
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
		owner: { subscribe: owner.subscribe },
		kicked: { subscribe: kicked.subscribe },
		async send(content: string) {
			const trimmed = content.trim();
			if (!trimmed || !ws || ws.readyState !== WebSocket.OPEN) return;

			// Issue #59: sign the canonical payload so the server can verify
			// authorship. A signing failure degrades to an unsigned (unverified)
			// message rather than dropping it.
			if (options.signer) {
				const sentAt = new Date().toISOString();
				try {
					const signature = await signChatMessage(options.signer, roomName, trimmed, sentAt);
					if (!ws || ws.readyState !== WebSocket.OPEN) return;
					ws.send(JSON.stringify({ content: trimmed, sent_at: sentAt, signature }));
					return;
				} catch (e) {
					console.error('Message signing failed; sending unsigned', e);
				}
			}

			if (!ws || ws.readyState !== WebSocket.OPEN) return;
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
