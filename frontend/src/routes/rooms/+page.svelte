<script lang="ts">
	import { roomsStore } from '$lib/roomsStore';
	import { env } from '$env/dynamic/public';
	import { enhance } from '$app/forms';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();

	let currentPing = $state<number | string>('...');
	let isCreating = $state(false);

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
			if (form.error) {
				showToast(form.error, 'error');
			} else if (form.success && form.message) {
				showToast(form.message, 'success');
			}
		}
	});

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

	let currentTime = $state(new Date());

	$effect(() => {
		const interval = setInterval(() => {
			currentTime = new Date();
		}, 1000);
		return () => clearInterval(interval);
	});

	let activeRooms = $derived($roomsStore.filter(r => new Date(r.expires_at) > currentTime));

	function getRemainingTime(expiresAtIso: string): string {
		const expiry = new Date(expiresAtIso).getTime();
		const diff = expiry - currentTime.getTime();
		if (diff <= 0) return '00:00';
		
		const minutes = Math.floor(diff / 60000);
		const seconds = Math.floor((diff % 60000) / 1000);
		return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
	}
</script>

<svelte:head>
	<title>PlayLink - Rooms</title>
</svelte:head>

<div class="rooms-page-container">
	<div class="rooms-page">
		<header class="header">
			<div class="logo-section">
				<h1 class="logo">PLAYLINK</h1>
				<p class="description">
					Find players for forgotten servers, overhaul mods, and retro netplay nights without account walls.
					This concept focuses on instant browsing, strong atmosphere, and a clear path to a later backend.
				</p>

				{#if data.isAuthenticated}
					<div class="actions">
						<button class="btn btn-primary" onclick={() => (isCreating = !isCreating)}>
							{isCreating ? 'CANCEL' : 'CREATE ROOM'}
						</button>
					</div>
				{:else}
					<p class="description" style="color: #ff6b6b; font-size: 0.85rem;">
						» Please sign in to create or join rooms.
					</p>
				{/if}
			</div>

			<div class="stats-grid">
				<div class="stat-card">
					<h3 class="stat-title">OPEN ROOMS</h3>
					<div class="stat-value">{activeRooms.length}</div>
					<p class="stat-desc">Lobbies currently broadcasting</p>
				</div>
				<div class="stat-card">
					<h3 class="stat-title">AVERAGE PING</h3>
					<div class="stat-value">
						{#if typeof currentPing === 'number'}
							{currentPing} MS
						{:else}
							{currentPing}
						{/if}
					</div>
					<p class="stat-desc">Healthy enough for browse mode</p>
				</div>
			</div>
		</header>

		<section class="board-section">
			{#if isCreating}
				<div class="create-room-panel">
					<h3 class="panel-title">CONFIGURE SIGNAL</h3>

					{#if form?.error}
						<p class="error-msg">{form.error}</p>
					{/if}

					<form
						method="POST"
						action="?/create"
						use:enhance={() => {
							return async ({ update }) => {
								await update();
								if (!form?.error) isCreating = false;
							};
						}}
					>
						<div class="form-group">
							<label for="name">Identifier (Lobby Name)</label>
							<input type="text" id="name" name="name" required placeholder="e.g. My Retro Match" />
						</div>

						<div class="form-group">
							<label for="game">Target Program (Game)</label>
							<select id="game" name="game" required disabled={!data.games.length}>
								{#if data.games.length > 0}
									{#each data.games as game (game)}
										<option value={game}>{game}</option>
									{/each}
								{:else}
									<option value="" disabled selected>No games available</option>
								{/if}
							</select>
						</div>

						<div class="form-group">
							<label for="players_max">Max Connections (Slots)</label>
							<input type="number" id="players_max" name="players_max" min="2" max="64" value="4" required />
						</div>

						<button type="submit" class="btn btn-primary" style="margin-top: 1rem;">BROADCAST</button>
					</form>
				</div>
			{/if}

			<div class="section-header" style={isCreating ? 'margin-top: 3rem;' : ''}>
				<h2 class="section-title">— ACTIVE ROOMS</h2>
			</div>

			{#if activeRooms.length === 0}
				<div class="empty-state">
					<p>Awaiting signals...</p>
				</div>
			{:else}
				<div class="signals-grid">
					{#each activeRooms as room (room.id ?? room.name)}
						<div class="signal-card">
							<div class="signal-header">
								<span class="signal-badge">LOBBY</span>
								<span
									class="signal-slots"
									style="color: #ff6b6b; margin-right: auto; padding-left: 0.5rem; font-family: ui-monospace, sans-serif;"
								>
									{getRemainingTime(room.expires_at)}
								</span>
								<span class="signal-slots">{room.players_active} / {room.players_max} SLOTS</span>
							</div>
							<div class="signal-name">{room.name}</div>
							<div class="signal-game">Playing: {room.game}</div>
							<div class="signal-footer">
								<div class="progress-bar">
									<div
										class="progress-fill"
										style="width: {(room.players_active / room.players_max) * 100}%"
									></div>
								</div>

								{#if data.isAuthenticated && data.user}
									{@const isMember = room.member_addresses.includes(data.user.address)}
									{@const isFull = room.players_active >= room.players_max}
									<div class="card-actions">
										<form method="POST" action="?/join" use:enhance>
											<input type="hidden" name="room_name" value={room.name} />
											<button type="submit" class="card-btn join" disabled={isMember || isFull}>
												[ JOIN ]
											</button>
										</form>

										<form method="POST" action="?/leave" use:enhance>
											<input type="hidden" name="room_name" value={room.name} />
											<button type="submit" class="card-btn leave" disabled={!isMember}>
												[ LEAVE ]
											</button>
										</form>
									</div>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</section>
	</div>
</div>

{#if toastMessage}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="toast {toastMessage.type}"
		onclick={() => {
			toastMessage = null;
		}}
	>
		<div class="toast-indicator"></div>
		<div class="toast-content">
			<div class="toast-title">
				{toastMessage.type === 'error' ? 'SYSTEM ERROR' : 'SYSTEM CONFIRM'}
			</div>
			<div class="toast-text">{toastMessage.text}</div>
		</div>
		<div class="toast-close">×</div>
	</div>
{/if}

<style>
	.toast {
		position: fixed;
		bottom: 2rem;
		right: 2rem;
		z-index: 100;
		background: #0d0d0d;
		border: 1px solid #332f26;
		box-shadow: 0 10px 30px rgba(0,0,0,0.8), inset 0 0 15px rgba(0,0,0,0.5);
		padding: 1rem 1.5rem;
		display: flex;
		align-items: center;
		gap: 1rem;
		min-width: 300px;
		max-width: 450px;
		cursor: pointer;
		animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
	}

	.toast.success {
		border-color: #4a5c40;
	}

	.toast.success .toast-indicator {
		background-color: #a4ce82;
		box-shadow: 0 0 10px rgba(164, 206, 130, 0.3);
	}

	.toast.success .toast-title {
		color: #a4ce82;
	}

	.toast.error {
		border-color: #7a1d1d;
	}

	.toast.error .toast-indicator {
		background-color: #ff6b6b;
		box-shadow: 0 0 10px rgba(255, 107, 107, 0.3);
	}

	.toast.error .toast-title {
		color: #ff6b6b;
	}

	.toast-indicator {
		width: 4px;
		height: 100%;
		position: absolute;
		left: 0;
		top: 0;
	}

	.toast-content {
		flex: 1;
		padding-left: 0.5rem;
	}

	.toast-title {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.7rem;
		letter-spacing: 0.1em;
		margin-bottom: 0.3rem;
	}

	.toast-text {
		color: #f1e9cd;
		font-size: 0.95rem;
		line-height: 1.4;
	}

	.toast-close {
		color: #8c877a;
		font-size: 1.5rem;
		line-height: 1;
	}

	.toast:hover .toast-close {
		color: #f1e9cd;
	}

	@keyframes slideIn {
		0% {
			opacity: 0;
			transform: translateX(20px) scale(0.95);
		}
		100% {
			opacity: 1;
			transform: translateX(0) scale(1);
		}
	}

	.rooms-page-container {
		background-color: #0d0d0d;
		color: #e4d8b8;
		font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
		min-height: 100vh;
		padding: 2rem 0;
	}

	.rooms-page {
		max-width: 1200px;
		margin: 0 auto;
		padding: 2.5rem;
		background: #111111;
		border: 1px solid #23201a;
		border-radius: 12px;
		box-shadow: inset 0 0 40px rgba(0,0,0,0.5), 0 10px 40px rgba(0,0,0,0.8);
	}

	.top-bar {
		margin-bottom: 2rem;
	}

	.eyebrow {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.7rem;
		letter-spacing: 0.15em;
		color: #6a675d;
		text-transform: uppercase;
	}

	.header {
		display: flex;
		flex-wrap: wrap;
		gap: 4rem;
		margin-bottom: 3rem;
		border-bottom: 1px solid #1a1916;
		padding-bottom: 3rem;
	}

	.logo-section {
		flex: 1;
		min-width: 300px;
		max-width: 600px;
	}

	.logo {
		font-family: 'Exocet', serif;
		font-size: 4.5rem;
		font-weight: normal;
		color: #f1e9cd;
		letter-spacing: 0.05em;
		margin: 0 0 1.5rem 0;
		text-shadow: 0 0 20px rgba(241, 233, 205, 0.15);
	}

	.description {
		color: #8c877a;
		font-size: 1rem;
		line-height: 1.6;
		margin-bottom: 2rem;
	}

	.badges {
		display: flex;
		flex-wrap: wrap;
		gap: 0.8rem;
		margin-bottom: 2rem;
	}

	.badge {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.65rem;
		letter-spacing: 0.1em;
		color: #8c877a;
		background: #191815;
		border: 1px solid #28251e;
		padding: 0.4rem 0.8rem;
		border-radius: 20px;
	}

	.actions {
		display: flex;
		gap: 1rem;
	}

	.btn {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.75rem;
		letter-spacing: 0.15em;
		padding: 0.8rem 1.5rem;
		border-radius: 6px;
		cursor: pointer;
		text-transform: uppercase;
		transition: all 0.2s;
	}

	.btn-primary {
		background: #e3bc74;
		color: #1a1405;
		border: none;
		box-shadow: 0 0 15px rgba(227, 188, 116, 0.3);
		font-weight: bold;
	}

	.btn-primary:hover {
		background: #f1cf8f;
		box-shadow: 0 0 25px rgba(227, 188, 116, 0.5);
	}

	.btn-secondary {
		background: transparent;
		color: #a39c8c;
		border: 1px solid #3d3930;
	}

	.btn-secondary:hover {
		border-color: #e3bc74;
		color: #e3bc74;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.5rem;
		align-content: start;
	}

	.stat-card {
		background: #141415;
		border: 1px solid #25221b;
		border-radius: 8px;
		padding: 1.5rem;
		min-width: 200px;
	}

	.stat-title {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.75rem;
		letter-spacing: 0.15em;
		color: #8c877a;
		margin: 0 0 1rem 0;
		font-weight: normal;
	}

	.stat-value {
		font-family: 'Exocet', serif;
		font-size: 2.5rem;
		color: #e4d8b8;
		margin-bottom: 0.5rem;
	}

	.stat-desc {
		font-size: 0.75rem;
		color: #5c584a;
		margin: 0;
	}

	.board-section {
		background: #141415;
		border: 1px solid #25221b;
		border-radius: 10px;
		padding: 2rem;
	}

	.section-title {
		font-family: ui-monospace, SFMono-Regular, monospace;
		font-size: 0.8rem;
		letter-spacing: 0.2em;
		color: #8c877a;
		text-transform: uppercase;
		margin: 0 0 2rem 0;
	}

	.empty-state {
		text-align: center;
		color: #6a675d;
		font-family: ui-monospace, monospace;
		padding: 4rem;
		border: 1px dashed #28251e;
		border-radius: 6px;
	}

	.signals-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 1.5rem;
	}

	.signal-card {
		background: #0a0a0b;
		border: 1px solid #28251e;
		border-radius: 6px;
		padding: 1.5rem;
		transition: all 0.2s;
	}

	.signal-card:hover {
		border-color: #585141;
		box-shadow: 0 4px 20px rgba(0,0,0,0.5);
	}

	.signal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.2rem;
		font-family: ui-monospace, monospace;
		font-size: 0.65rem;
		color: #8c877a;
		letter-spacing: 0.1em;
	}

	.signal-badge {
		color: #d1b884;
	}

	.signal-name {
		font-family: 'Exocet', serif;
		font-size: 1.8rem;
		color: #f1e9cd;
		margin-bottom: 0.5rem;
		text-transform: uppercase;
		line-height: 1.1;
	}

	.signal-game {
		font-family: ui-monospace, monospace;
		font-size: 0.75rem;
		color: #a39c8c;
		margin-bottom: 1.5rem;
		letter-spacing: 0.05em;
	}

	.signal-footer {
		margin-top: 1rem;
	}

	.progress-bar {
		height: 4px;
		background: #25221b;
		border-radius: 2px;
		overflow: hidden;
		display: flex;
	}

	.progress-fill {
		background: #c29d59;
		height: 100%;
		transition: width 0.3s ease;
	}

	.create-room-panel {
		background: #0a0a0b;
		border: 1px solid #28251e;
		border-radius: 8px;
		padding: 2rem;
		margin-bottom: 2rem;
	}

	.panel-title {
		font-family: 'Exocet', serif;
		color: #e3bc74;
		margin: 0 0 1.5rem 0;
		font-weight: normal;
	}

	.form-group {
		margin-bottom: 1.5rem;
	}

	.form-group label {
		display: block;
		font-family: ui-monospace, monospace;
		font-size: 0.75rem;
		color: #8c877a;
		margin-bottom: 0.5rem;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}

	.form-group input,
	.form-group select {
		width: 100%;
		background: #141415;
		border: 1px solid #28251e;
		color: #e4d8b8;
		padding: 0.8rem;
		border-radius: 4px;
		font-family: ui-monospace, monospace;
		font-size: 0.9rem;
	}

	.form-group input:focus,
	.form-group select:focus {
		outline: none;
		border-color: #e3bc74;
	}

	.error-msg {
		color: #ff6b6b;
		font-family: ui-monospace, monospace;
		font-size: 0.8rem;
		margin-bottom: 1.5rem;
		padding: 0.8rem;
		border: 1px solid #ff6b6b;
		background: rgba(255, 107, 107, 0.1);
		border-radius: 4px;
	}

	.card-actions {
		display: flex;
		gap: 0.5rem;
		margin-top: 1rem;
	}

	.card-actions form {
		flex: 1;
	}

	.card-btn {
		width: 100%;
		background: transparent;
		border: 1px solid #28251e;
		color: #8c877a;
		padding: 0.5rem;
		font-family: ui-monospace, monospace;
		font-size: 0.7rem;
		cursor: pointer;
		border-radius: 4px;
		transition: all 0.2s;
	}

	.card-btn:hover:not(:disabled) {
		border-color: #e3bc74;
		color: #e3bc74;
	}

	.card-btn.join:hover:not(:disabled) {
		border-color: #4CAF50;
		color: #4CAF50;
	}

	.card-btn.leave:hover:not(:disabled) {
		border-color: #ff6b6b;
		color: #ff6b6b;
	}

	.card-btn:disabled {
		opacity: 0.3;
		cursor: not-allowed;
	}
</style>
