<script lang="ts">
	import { onMount } from 'svelte';
	import { roomsStore, type RoomSummary } from '$lib/roomsStore';
	import { env } from '$env/dynamic/public';
	import { enhance, deserialize } from '$app/forms';
	import { goto, invalidateAll } from '$app/navigation';
	import type { PageProps } from './$types';

	import InnerPanel from '$lib/components/chrome/InnerPanel.svelte';
	import SectionTitle from '$lib/components/chrome/SectionTitle.svelte';
	import OrnateButton from '$lib/components/chrome/OrnateButton.svelte';
	import StoneCheckbox from '$lib/components/chrome/StoneCheckbox.svelte';
	import Cycler from '$lib/components/chrome/Cycler.svelte';
	import ListRow from '$lib/components/chrome/ListRow.svelte';
	import PipMeter from '$lib/components/chrome/PipMeter.svelte';
	import ProgressBar from '$lib/components/chrome/ProgressBar.svelte';
	import SystemDialog from '$lib/components/chrome/SystemDialog.svelte';
	import Crest from '$lib/components/chrome/Crest.svelte';
	import GameManager from '$lib/components/GameManager.svelte';

	import { getHintsState } from '$lib/hintsContext.svelte';

	let { data, form }: PageProps = $props();

	// --- Ping ---
	let currentPing = $state<number | string>('...');

	async function measurePing() {
		const start = performance.now();
		try {
			const baseUrl = env.PUBLIC_BACKEND_URL || 'http://localhost:8000';
			await fetch(`${baseUrl}/`);
			const end = performance.now();
			currentPing = Math.round(end - start);
		} catch {
			currentPing = 'ERR';
		}
	}

	$effect(() => {
		measurePing();
		const interval = setInterval(measurePing, 15000);
		return () => clearInterval(interval);
	});

	// --- Time ---
	let currentTime = $state(new Date());
	$effect(() => {
		const interval = setInterval(() => {
			currentTime = new Date();
		}, 1000);
		return () => clearInterval(interval);
	});

	function getRemainingTime(expiresAtIso: string): string {
		const expiry = new Date(expiresAtIso).getTime();
		const diff = expiry - currentTime.getTime();
		if (diff <= 0) return '00:00';
		const minutes = Math.floor(diff / 60000);
		const seconds = Math.floor((diff % 60000) / 1000);
		return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
	}

	function timerLow(room: RoomSummary): boolean {
		return new Date(room.expires_at).getTime() - currentTime.getTime() < 60_000;
	}

	// --- Per-room ping (synthetic but stable) ---
	// Backend has no per-room latency, so each room's ping is the user's measured
	// ping plus a deterministic offset derived from the room name. Same room
	// always shows the same ping; differs across rooms; tracks real link health.
	function hashRoomName(name: string): number {
		let h = 5381;
		for (let i = 0; i < name.length; i++) h = ((h << 5) + h + name.charCodeAt(i)) | 0;
		return Math.abs(h);
	}

	function pingForRoom(room: RoomSummary): number | null {
		if (typeof currentPing !== 'number') return null;
		const offset = (hashRoomName(room.name) % 240) - 20; // -20..+219ms
		return Math.max(8, currentPing + offset);
	}

	type PingBucket = 'LOW' | 'MID' | 'HIGH';

	function pingBucket(ms: number): PingBucket {
		if (ms <= 80) return 'LOW';
		if (ms <= 160) return 'MID';
		return 'HIGH';
	}

	function pipsForPing(ms: number | null): number {
		if (ms === null) return 0;
		const b = pingBucket(ms);
		return b === 'LOW' ? 3 : b === 'MID' ? 2 : 1;
	}

	// --- Active rooms ---
	let activeRooms = $derived($roomsStore.filter((r) => new Date(r.expires_at) > currentTime));

	// --- Filters ---
	interface FilterState {
		name: string;
		slots2: boolean;
		slots4: boolean;
		slots8: boolean;
		slots16: boolean;
		status: 'ANY' | 'OPEN' | 'FULL';
		ping: 'ANY' | 'LOW' | 'MID' | 'HIGH';
	}

	let filters = $state<FilterState>({
		name: '',
		slots2: false,
		slots4: false,
		slots8: false,
		slots16: false,
		status: 'ANY',
		ping: 'ANY'
	});

	function resetFilters() {
		filters.name = '';
		filters.slots2 = false;
		filters.slots4 = false;
		filters.slots8 = false;
		filters.slots16 = false;
		filters.status = 'ANY';
		filters.ping = 'ANY';
	}

	let filteredRooms = $derived.by(() => {
		const anySlot = filters.slots2 || filters.slots4 || filters.slots8 || filters.slots16;
		const q = filters.name.trim().toLowerCase();

		return activeRooms.filter((room) => {
			if (q) {
				const hay = `${room.name} ${room.game}`.toLowerCase();
				if (!hay.includes(q)) return false;
			}
			if (anySlot) {
				const m = room.players_max;
				const matched =
					(filters.slots2 && m === 2) ||
					(filters.slots4 && m === 4) ||
					(filters.slots8 && m === 8) ||
					(filters.slots16 && m >= 16);
				if (!matched) return false;
			}
			if (filters.status === 'OPEN' && room.players_active >= room.players_max) return false;
			if (filters.status === 'FULL' && room.players_active < room.players_max) return false;
			if (filters.ping !== 'ANY') {
				const ms = pingForRoom(room);
				if (ms === null) return false;
				if (pingBucket(ms) !== filters.ping) return false;
			}
			return true;
		});
	});

	// --- Selection ---
	let selectedName = $state<string | null>(null);
	let selectedRoom = $derived(
		selectedName ? (filteredRooms.find((r) => r.name === selectedName) ?? null) : null
	);
	let listColRef = $state<HTMLElement | null>(null);
	let sideColRef = $state<HTMLElement | null>(null);

	$effect(() => {
		// If the selected room disappears (filter or expiry), clear selection.
		if (selectedName && !filteredRooms.some((r) => r.name === selectedName)) {
			selectedName = null;
		}
	});

	// Click outside the list/side panel deselects current room.
	$effect(() => {
		if (!selectedName) return;
		function handler(e: MouseEvent) {
			const t = e.target as Node | null;
			if (!t) return;
			if (sideColRef?.contains(t)) return;
			if (listColRef?.contains(t)) return;
			selectedName = null;
		}
		window.addEventListener('mousedown', handler);
		return () => window.removeEventListener('mousedown', handler);
	});

	// Helper: check whether the current user is a member of the room.
	function isMemberOf(room: RoomSummary): boolean {
		if (!data.isAuthenticated || !data.user) return false;
		return room.member_addresses.includes(data.user.address);
	}

	// --- Updated-at clock for the section title trail ---
	let updatedHHMM = $derived(
		`${currentTime.getHours().toString().padStart(2, '0')}:${currentTime
			.getMinutes()
			.toString()
			.padStart(2, '0')}`
	);

	// --- Toast ---
	let toastMessage = $state<{ text: string; type: 'success' | 'error' } | null>(null);
	let toastTimeout: ReturnType<typeof setTimeout>;

	function showToast(text: string, type: 'success' | 'error') {
		toastMessage = { text, type };
		if (toastTimeout) clearTimeout(toastTimeout);
		toastTimeout = setTimeout(() => {
			toastMessage = null;
		}, 4500);
	}

	$effect(() => {
		if (form) {
			if ('error' in form && form.error) {
				showToast(form.error, 'error');
			} else if ('success' in form && form.success && form.message) {
				showToast(form.message, 'success');
			}
		}
	});

	// --- Create dialog ---
	let createOpen = $state(false);

	// --- Admin: game manager + room deletion ---
	let gamesOpen = $state(false);
	let confirmDeleteName = $state<string | null>(null);
	let deletingRoom = $state(false);

	async function closeRoom(name: string) {
		if (deletingRoom) return;
		deletingRoom = true;
		try {
			const body = new FormData();
			body.append('room_name', name);
			const res = await fetch('?/deleteRoom', { method: 'POST', body });
			const result = deserialize(await res.text()) as
				| { type: 'success' }
				| { type: 'failure'; data?: { error?: string } }
				| { type: 'error' | 'redirect' };
			if (result.type === 'success') {
				showToast(`Closed room: ${name}`, 'success');
				if (selectedName === name) selectedName = null;
				await invalidateAll();
			} else if (result.type === 'failure') {
				showToast(result.data?.error ?? 'Failed to close room', 'error');
			} else {
				showToast('Failed to close room', 'error');
			}
		} finally {
			deletingRoom = false;
			confirmDeleteName = null;
		}
	}

	// --- Refs ---
	let nameInputRef = $state<HTMLInputElement | null>(null);

	// --- Hints + global keys ---
	const hintsState = getHintsState();

	$effect(() => {
		hintsState?.set([
			{ key: 'Enter', label: 'Open', tone: 'gold' },
			{ key: 'R', label: 'Refresh', tone: 'green' },
			{ key: '/', label: 'Search', tone: 'amber' },
			{ key: 'N', label: 'Create', tone: 'gold' },
			{ key: 'Esc', label: 'Back', tone: 'red' }
		]);
	});

	onMount(() => {
		const handler = (e: KeyboardEvent) => {
			const target = e.target as HTMLElement | null;
			const tag = target?.tagName;
			const isTyping =
				tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target?.isContentEditable;

			if (e.key === 'Escape') {
				if (createOpen) {
					createOpen = false;
					e.preventDefault();
					return;
				}
				if (selectedName) {
					selectedName = null;
					e.preventDefault();
					return;
				}
				if (!isTyping) {
					history.back();
				}
				return;
			}

			if (isTyping) return;

			if (e.key === '/') {
				e.preventDefault();
				nameInputRef?.focus();
				return;
			}
			if (e.key === 'r' || e.key === 'R') {
				e.preventDefault();
				location.reload();
				return;
			}
			if (e.key === 'n' || e.key === 'N') {
				if (data.isAuthenticated) {
					e.preventDefault();
					createOpen = true;
				}
				return;
			}
			if (e.key === 'Enter' && selectedRoom && data.isAuthenticated && data.user) {
				const isMember = selectedRoom.member_addresses.includes(data.user.address);
				if (isMember) {
					e.preventDefault();
					goto(`/rooms/${encodeURIComponent(selectedRoom.name)}`);
				}
			}
		};

		window.addEventListener('keydown', handler);
		return () => window.removeEventListener('keydown', handler);
	});
</script>

<svelte:head>
	<title>PlayLink — Game List</title>
</svelte:head>

<div class="rooms-page">
	<header class="page-head">
		<SectionTitle title="Game List" size="large" tone="gold">
			<span>{activeRooms.length} ACTIVE · UPDATED {updatedHHMM}</span>
		</SectionTitle>
	</header>

	<div class="split">
		<div class="list-col" bind:this={listColRef}>
			<InnerPanel padded={false}>
				<div class="list">
					<ListRow header>
						<span>Game Name</span>
						<span class="col-game">Game</span>
						<span>Players</span>
						<span class="col-ping">Ping</span>
						<span class="col-timer">Timer</span>
					</ListRow>

					<div class="rows scroll-d2">
						{#each filteredRooms as room (room.name)}
							{@const member = isMemberOf(room)}
							{@const ping = pingForRoom(room)}
							<ListRow
								selected={selectedName === room.name}
								{member}
								onclick={() => (selectedName = room.name)}
							>
								<span class="cell-name fw-700" class:is-member={member}>
									<span class="name-text">{room.name}</span>
									{#if member}
										<span class="member-tag" aria-label="You are a member">JOINED</span>
									{/if}
								</span>
								<span class="cell-game col-game">{room.game}</span>
								<span class="cell-slots mono">
									{room.players_active}/{room.players_max}
								</span>
								<span class="cell-ping col-ping">
									<PipMeter value={pipsForPing(ping)} tone="auto" size="md" />
									<span class="ping-ms mono">
										{ping === null ? '—' : `${ping}ms`}
									</span>
								</span>
								<span class="cell-timer mono col-timer" class:warn={timerLow(room)}>
									{getRemainingTime(room.expires_at)}
								</span>
								{#if data.isAdmin}
									<button
										class="admin-x"
										type="button"
										title="Close room (admin)"
										aria-label="Close room {room.name}"
										onclick={(e) => {
											e.stopPropagation();
											confirmDeleteName = room.name;
										}}
									>
										✕
									</button>
								{/if}
							</ListRow>
						{/each}

						{#if filteredRooms.length === 0}
							<div class="empty">
								<Crest size={64} tone="iron" />
								<p>Awaiting signals…</p>
							</div>
						{/if}
					</div>
				</div>
			</InnerPanel>
		</div>

		<aside class="side-col" bind:this={sideColRef}>
			<div class="create-fab">
				{#if !data.isAuthenticated}
					<span class="auth-warn small-caps">Identity required</span>
				{/if}
				{#if data.isAdmin}
					<OrnateButton variant="secondary" size="md" onclick={() => (gamesOpen = true)}>
						Manage Games
					</OrnateButton>
				{/if}
				<OrnateButton
					variant="primary"
					size="md"
					disabled={!data.isAuthenticated}
					onclick={() => (createOpen = true)}
				>
					+ Create Lobby
				</OrnateButton>
			</div>

			<InnerPanel>
				{#if selectedRoom}
					{@const room = selectedRoom}
					{@const isMember =
						data.isAuthenticated &&
						data.user !== null &&
						room.member_addresses.includes(data.user.address)}
					{@const isFull = room.players_active >= room.players_max}
					{@const sidePing = pingForRoom(room)}

					<SectionTitle title={room.name} size="normal" tone="bone" />

					<dl class="details">
						<dt>Game</dt>
						<dd>{room.game}</dd>
						<dt>Players</dt>
						<dd class="mono">{room.players_active} / {room.players_max}</dd>
						<dt>Ping</dt>
						<dd class="ping-side">
							<PipMeter value={pipsForPing(sidePing)} tone="auto" size="sm" />
							<span class="mono">{sidePing === null ? '—' : `${sidePing}ms`}</span>
						</dd>
						<dt>Expires</dt>
						<dd class="mono" class:warn={timerLow(room)}>
							{getRemainingTime(room.expires_at)}
						</dd>
					</dl>

					<div class="bar-wrap">
						<ProgressBar value={room.players_active} max={room.players_max} ticks variant="gold" />
					</div>

					{#if room.description || room.communicator_link || room.requirements}
						<dl class="meta-list">
							{#if room.description}
								<div class="meta-item">
									<dt class="small-caps">Description</dt>
									<dd>{room.description}</dd>
								</div>
							{/if}
							{#if room.communicator_link}
								<div class="meta-item">
									<dt class="small-caps">Communicator</dt>
									<dd>
										<a
											class="meta-link"
											href={room.communicator_link}
											target="_blank"
											rel="noopener noreferrer"
										>
											{room.communicator_link}
										</a>
									</dd>
								</div>
							{/if}
							{#if room.requirements}
								<div class="meta-item">
									<dt class="small-caps">Requirements</dt>
									<dd>{room.requirements}</dd>
								</div>
							{/if}
						</dl>
					{/if}

					{#if data.isAuthenticated}
						<div class="actions stack">
							<form method="POST" action="?/join" use:enhance class="action-form">
								<input type="hidden" name="room_name" value={room.name} />
								<OrnateButton
									variant="primary"
									size="md"
									type="submit"
									fullWidth
									disabled={isMember || isFull}
								>
									Join
								</OrnateButton>
							</form>

							<form method="POST" action="?/leave" use:enhance class="action-form">
								<input type="hidden" name="room_name" value={room.name} />
								<OrnateButton
									variant="danger"
									size="md"
									type="submit"
									fullWidth
									disabled={!isMember}
								>
									Leave
								</OrnateButton>
							</form>

							{#if isMember}
								<OrnateButton
									variant="secondary"
									size="md"
									fullWidth
									href="/rooms/{encodeURIComponent(room.name)}"
								>
									Open
								</OrnateButton>
							{/if}

							{#if data.isAdmin}
								<OrnateButton
									variant="danger"
									size="md"
									fullWidth
									disabled={deletingRoom}
									onclick={() => (confirmDeleteName = room.name)}
								>
									Close Room (Admin)
								</OrnateButton>
							{/if}

							<OrnateButton
								variant="ghost"
								size="sm"
								fullWidth
								onclick={() => (selectedName = null)}
							>
								Back to Filters
							</OrnateButton>
						</div>
					{:else}
						<p class="auth-note">Identity required to join or leave.</p>
						<OrnateButton variant="ghost" size="sm" fullWidth onclick={() => (selectedName = null)}>
							Back to Filters
						</OrnateButton>
					{/if}
				{:else}
					<SectionTitle title="Filters" size="small" tone="gold" />

					<div class="filter-group">
						<span class="filter-label small-caps">Max Slots</span>
						<div class="checks">
							<StoneCheckbox bind:checked={filters.slots2} label="2" size="sm" />
							<StoneCheckbox bind:checked={filters.slots4} label="4" size="sm" />
							<StoneCheckbox bind:checked={filters.slots8} label="8" size="sm" />
							<StoneCheckbox bind:checked={filters.slots16} label="16+" size="sm" />
						</div>
					</div>

					<div class="filter-group">
						<Cycler label="Status" bind:value={filters.status} values={['ANY', 'OPEN', 'FULL']} />
					</div>

					<div class="filter-group">
						<Cycler label="Ping" bind:value={filters.ping} values={['ANY', 'LOW', 'MID', 'HIGH']} />
					</div>

					<div class="filter-actions">
						<OrnateButton variant="secondary" size="sm" fullWidth onclick={resetFilters}>
							Reset Filters
						</OrnateButton>
					</div>

					<SectionTitle title="Name Filter" size="small" tone="gold" />
					<div class="name-filter">
						<input
							class="text-input bevel-in"
							type="text"
							bind:value={filters.name}
							bind:this={nameInputRef}
							placeholder="Filter by name…"
						/>
					</div>

					<SectionTitle title="Status" size="small" tone="gold" />
					<div class="stats">
						<div class="stat">
							<span class="stat-label small-caps">Open</span>
							<span class="stat-value etched-bone">{activeRooms.length}</span>
						</div>
						<div class="stat">
							<span class="stat-label small-caps">Ping</span>
							<span class="stat-value mono">
								{currentPing}
								<small>MS</small>
							</span>
						</div>
					</div>
				{/if}
			</InnerPanel>
		</aside>
	</div>
</div>

<SystemDialog
	bind:open={createOpen}
	title="Configure Signal"
	tone="gold"
	modal
	width="480px"
	onclose={() => (createOpen = false)}
>
	{#if form && 'error' in form && form.error}
		<p class="dialog-error">{form.error}</p>
	{/if}

	<form
		id="create-form"
		method="POST"
		action="?/create"
		use:enhance={() => {
			return async ({ update }) => {
				await update();
				if (!form || !('error' in form) || !form.error) {
					createOpen = false;
				}
			};
		}}
	>
		<div class="form-row">
			<label for="create-name" class="small-caps">Identifier (Lobby Name)</label>
			<input
				id="create-name"
				class="text-input bevel-in"
				type="text"
				name="name"
				required
				placeholder="e.g. My Retro Match"
			/>
		</div>

		<div class="form-row">
			<label for="create-game" class="small-caps">Target Program (Game)</label>
			<select
				id="create-game"
				class="text-input bevel-in"
				name="game"
				required
				disabled={!data.games.length}
			>
				{#if data.games.length > 0}
					{#each data.games as g (g)}
						<option value={g}>{g}</option>
					{/each}
				{:else}
					<option value="" disabled selected>No games available</option>
				{/if}
			</select>
		</div>

		<div class="form-row">
			<label for="create-slots" class="small-caps">Max Connections (Slots)</label>
			<input
				id="create-slots"
				class="text-input bevel-in"
				type="number"
				name="players_max"
				min="2"
				max="64"
				value="4"
				required
			/>
		</div>

		<div class="form-row">
			<label for="create-description" class="small-caps">Description (optional)</label>
			<textarea
				id="create-description"
				class="text-input bevel-in"
				name="description"
				maxlength="500"
				rows="3"
				placeholder="Short note about the session"
			></textarea>
		</div>

		<div class="form-row">
			<label for="create-communicator" class="small-caps">Communicator Link (optional)</label>
			<input
				id="create-communicator"
				class="text-input bevel-in"
				type="url"
				name="communicator_link"
				maxlength="500"
				placeholder="https://discord.gg/..."
			/>
		</div>

		<div class="form-row">
			<label for="create-requirements" class="small-caps">Requirements (optional)</label>
			<textarea
				id="create-requirements"
				class="text-input bevel-in"
				name="requirements"
				maxlength="1000"
				rows="3"
				placeholder="Game version, mods, network setup..."
			></textarea>
		</div>
	</form>

	{#snippet footer()}
		<OrnateButton variant="ghost" size="md" onclick={() => (createOpen = false)}>
			Cancel
		</OrnateButton>
		<OrnateButton
			variant="primary"
			size="md"
			onclick={() => {
				const f = document.getElementById('create-form') as HTMLFormElement | null;
				f?.requestSubmit();
			}}
		>
			Broadcast
		</OrnateButton>
	{/snippet}
</SystemDialog>

{#if toastMessage}
	{@const toast = toastMessage}
	<SystemDialog
		open={true}
		title={toast.type === 'error' ? 'System Error' : 'System Confirm'}
		tone={toast.type === 'error' ? 'blood' : 'green'}
		position="bottom-right"
		onclose={() => (toastMessage = null)}
	>
		<p class="toast-text">{toast.text}</p>
	</SystemDialog>
{/if}

{#if data.isAdmin}
	<GameManager bind:open={gamesOpen} games={data.games} onclose={() => (gamesOpen = false)} />
{/if}

{#if confirmDeleteName}
	{@const target = confirmDeleteName}
	<SystemDialog
		open={true}
		title="Close Room"
		tone="blood"
		modal
		width="440px"
		onclose={() => (confirmDeleteName = null)}
	>
		<p class="confirm-text">
			Close room <strong>{target}</strong>? This deletes its chat, scheduled event and all RSVPs,
			and disconnects everyone inside. This cannot be undone.
		</p>
		{#snippet footer()}
			<OrnateButton variant="ghost" size="md" onclick={() => (confirmDeleteName = null)}>
				Cancel
			</OrnateButton>
			<OrnateButton
				variant="danger"
				size="md"
				disabled={deletingRoom}
				onclick={() => closeRoom(target)}
			>
				Close Room
			</OrnateButton>
		{/snippet}
	</SystemDialog>
{/if}

<style>
	.rooms-page {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
		min-height: 0;
		flex: 1;
		padding: 0.5rem 0 4rem;
	}

	.page-head {
		padding: 0 0.5rem;
	}

	.split {
		display: grid;
		grid-template-columns: 1fr;
		gap: 1.25rem;
		min-height: 0;
		flex: 1;
	}

	/* Tablet portrait/landscape: keep side panel visible, slightly narrower. */
	@media (min-width: 768px) and (max-width: 1023px) {
		.split {
			grid-template-columns: 6fr 4fr;
		}
		.side-col {
			position: sticky;
			top: 0;
			align-self: start;
			max-height: calc(100vh - 6rem);
			overflow: auto;
		}
	}

	@media (min-width: 1024px) {
		.split {
			grid-template-columns: 7fr 3fr;
			position: relative;
		}

		.side-col {
			position: sticky;
			top: 0;
			align-self: start;
			max-height: calc(100vh - 8rem);
			overflow: auto;
		}
	}

	.list-col {
		display: flex;
		min-height: 0;
	}

	.list-col :global(.inner-panel) {
		display: flex;
		flex-direction: column;
		min-height: 480px;
	}

	.list {
		display: flex;
		flex-direction: column;
		min-height: 0;
		flex: 1;
		/* Default (mobile): 3 visible columns — Name, Players, Ping */
		--list-cols: 1.6fr 0.8fr 0.7fr;
		--list-gap: 0.8rem;
	}

	/* Hide non-essential columns on narrow viewports. */
	.list :global(.col-game),
	.list :global(.col-timer) {
		display: none;
	}

	@media (min-width: 600px) {
		.list {
			/* Add Timer */
			--list-cols: 1.6fr 0.8fr 0.7fr 0.6fr;
			--list-gap: 1rem;
		}
		.list :global(.col-timer) {
			display: inline-flex;
		}
	}

	@media (min-width: 900px) {
		.list {
			/* Add Game column → all 5 visible */
			--list-cols: 1.6fr 1fr 0.7fr 0.8fr 0.6fr;
			--list-gap: 1.2rem;
		}
		.list :global(.col-game) {
			display: inline-flex;
		}
	}

	@media (min-width: 1280px) {
		.list {
			--list-cols: 1.7fr 1fr 0.6fr 0.7fr 0.5fr;
			--list-gap: 1.5rem;
		}
	}

	.rows {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
		max-height: calc(100vh - 16rem);
		overflow-y: auto;
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1rem;
		padding: 4rem 1rem;
		flex: 1;
	}

	.empty p {
		margin: 0;
		font-style: italic;
		color: var(--bone-muted);
		font-family: var(--font-display);
		letter-spacing: var(--track-loose);
	}

	/* Cells */
	.cell-name {
		color: var(--bone-bright);
		min-width: 0;
		overflow: hidden;
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
	}

	/* The name itself truncates; the JOINED tag keeps its size. */
	.cell-name .name-text {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.cell-name .member-tag {
		flex-shrink: 0;
	}

	.cell-name.is-member {
		color: var(--gold-lit);
	}

	.member-tag {
		display: inline-block;
		font-family: var(--font-display);
		font-size: 0.62em;
		letter-spacing: var(--track-extra);
		padding: 1px 6px;
		color: var(--gold-hot);
		background: rgba(227, 188, 116, 0.14);
		border: 1px solid rgba(227, 188, 116, 0.5);
		text-shadow: 0 1px 0 rgba(0, 0, 0, 0.7);
		flex-shrink: 0;
	}

	.cell-game {
		color: var(--bone-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		transition: color 140ms ease;
	}

	:global(.row.is-interactive:hover) .cell-game,
	:global(.row.is-selected) .cell-game,
	:global(.row.is-member) .cell-game {
		color: var(--bone);
	}

	.cell-slots {
		color: var(--bone);
	}

	.cell-timer {
		color: var(--bone);
	}

	.cell-timer.warn {
		color: var(--blood-bright);
	}

	.cell-ping {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
	}

	.ping-ms {
		font-size: 0.7rem;
		color: var(--bone-dim);
		letter-spacing: 0.04em;
		min-width: 3.6em;
	}

	.ping-side {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--bone-dim);
	}

	.fw-700 {
		font-weight: 700;
	}

	.mono {
		font-family: var(--font-mono);
		letter-spacing: 0.04em;
		font-feature-settings: normal;
		text-transform: none;
	}

	/* Side panel */
	.details {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.4rem 1rem;
		margin: 0 0 1rem 0;
		padding: 0.5rem 0 1rem;
		border-bottom: 1px solid var(--stone-5);
	}

	.details dt {
		font-family: var(--font-display);
		font-size: 0.7rem;
		letter-spacing: var(--track-extra);
		text-transform: uppercase;
		color: var(--bone-muted);
		font-feature-settings:
			'smcp' 1,
			'c2sc' 1;
	}

	.details dd {
		margin: 0;
		color: var(--bone-bright);
		font-family: var(--font-display);
		font-size: 0.85rem;
		letter-spacing: var(--track-loose);
		text-transform: uppercase;
	}

	.details dd.mono {
		font-family: var(--font-mono);
		text-transform: none;
		letter-spacing: 0.04em;
	}

	.details dd.warn {
		color: var(--blood-bright);
	}

	.bar-wrap {
		margin-bottom: 1.25rem;
	}

	.meta-list {
		margin: 0 0 1.25rem 0;
		padding: 0;
		display: grid;
		gap: 0.55rem;
	}

	.meta-item {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.meta-item dt {
		margin: 0;
		font-family: var(--font-display);
		font-size: 0.6rem;
		color: var(--bone-dim);
		letter-spacing: var(--track-loose);
	}

	.meta-item dd {
		margin: 0;
		font-family: var(--font-display);
		font-size: 0.78rem;
		color: var(--bone);
		line-height: 1.45;
		word-break: break-word;
	}

	.meta-link {
		color: var(--gold-base);
		text-decoration: none;
		border-bottom: 1px dashed var(--gold-muted);
		transition: color 140ms ease;
	}
	.meta-link:hover {
		color: var(--gold-lit);
		border-bottom-color: var(--gold-lit);
	}

	.actions.stack {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.action-form {
		display: contents;
	}

	.auth-note {
		font-family: var(--font-display);
		font-size: 0.78rem;
		letter-spacing: var(--track-loose);
		color: var(--blood-bright);
		text-transform: uppercase;
		margin: 0 0 1rem 0;
	}

	.filter-group {
		margin-bottom: 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.filter-label {
		font-family: var(--font-display);
		font-size: 0.7rem;
		letter-spacing: var(--track-extra);
		color: var(--bone-muted);
		text-transform: uppercase;
		font-feature-settings:
			'smcp' 1,
			'c2sc' 1;
	}

	.checks {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem 1rem;
	}

	.filter-actions {
		margin-bottom: 1.25rem;
	}

	.name-filter {
		margin-bottom: 1.25rem;
	}

	.text-input {
		width: 100%;
		background: #080604;
		border: 1px solid var(--stone-5);
		border-radius: 0;
		color: var(--bone-bright);
		padding: 0.65rem 0.8rem;
		font-family: var(--font-mono);
		font-size: 0.85rem;
		letter-spacing: 0.03em;
	}

	.text-input::placeholder {
		color: var(--bone-dim);
		font-style: italic;
	}

	.text-input:focus {
		outline: none;
		border-color: var(--gold-muted);
		box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.85);
	}

	textarea.text-input {
		resize: vertical;
		min-height: 3rem;
		line-height: 1.45;
	}

	.stats {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
		padding-top: 0.5rem;
	}

	.stat {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.6rem 0.75rem;
		border: 1px solid var(--stone-5);
		background: #080604;
	}

	.stat-label {
		font-family: var(--font-display);
		font-size: 0.65rem;
		letter-spacing: var(--track-extra);
		color: var(--bone-muted);
		text-transform: uppercase;
		font-feature-settings:
			'smcp' 1,
			'c2sc' 1;
	}

	.stat-value {
		font-family: var(--font-display);
		font-size: 1.4rem;
		color: var(--bone-bright);
		letter-spacing: var(--track-loose);
	}

	.stat-value.mono {
		font-family: var(--font-mono);
		font-size: 1.05rem;
		letter-spacing: 0.04em;
		text-transform: none;
	}

	.stat-value small {
		font-size: 0.6rem;
		color: var(--bone-muted);
		margin-left: 0.2rem;
		font-family: var(--font-display);
		letter-spacing: var(--track-loose);
		text-transform: uppercase;
	}

	/* Floating create button — fixed only on desktop (≥1024px).
	   On smaller screens the side panel stacks below the list and the FAB
	   would overlap it, so it flows into normal document order at the bottom. */
	.create-fab {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 0.75rem;
		flex-wrap: wrap;
		margin: 0 0 1rem;
	}

	.auth-warn {
		font-family: var(--font-mono);
		font-size: 0.7rem;
		letter-spacing: var(--track-loose);
		color: var(--blood-bright);
		text-transform: uppercase;
		padding: 0.45rem 0.7rem;
		background: #080604;
		border: 1px solid #4a1414;
	}

	.dialog-error {
		font-family: var(--font-mono);
		font-size: 0.8rem;
		color: var(--blood-bright);
		margin: 0 0 1rem 0;
		padding: 0.6rem 0.8rem;
		border: 1px solid #4a1414;
		background: rgba(181, 54, 54, 0.08);
	}

	.toast-text {
		margin: 0;
		font-family: var(--font-display);
		font-size: 0.9rem;
		color: var(--bone-bright);
		letter-spacing: var(--track-loose);
	}

	.confirm-text {
		margin: 0;
		font-family: var(--font-display);
		font-size: 0.9rem;
		color: var(--bone);
		line-height: 1.5;
		letter-spacing: 0.02em;
	}
	.confirm-text strong {
		color: var(--gold-base);
	}

	/* Admin close-room affordance. Absolutely positioned so it sits on top of the
	   row without consuming a grid track (abspos items don't size grid columns),
	   keeping the carefully-tuned list layout intact. */
	.admin-x {
		position: absolute;
		top: 50%;
		right: 0.4rem;
		transform: translateY(-50%);
		z-index: 3;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 22px;
		height: 22px;
		padding: 0;
		border: 1px solid #4a1414;
		background: rgba(20, 8, 8, 0.9);
		color: var(--blood-bright);
		font-family: var(--font-mono);
		font-size: 0.8rem;
		line-height: 1;
		cursor: pointer;
		opacity: 0;
		transition:
			opacity 140ms ease,
			color 140ms ease,
			border-color 140ms ease;
	}

	:global(.row.is-interactive:hover) .admin-x,
	:global(.row.is-selected) .admin-x,
	.admin-x:focus-visible {
		opacity: 1;
	}

	.admin-x:hover {
		color: #ffd9d9;
		border-color: var(--blood-bright);
	}

	/* Create dialog form rows */
	.form-row {
		margin-bottom: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.form-row label {
		font-family: var(--font-display);
		font-size: 0.7rem;
		letter-spacing: var(--track-extra);
		color: var(--bone-muted);
		text-transform: uppercase;
		font-feature-settings:
			'smcp' 1,
			'c2sc' 1;
	}
</style>
