<script lang="ts">
	import { roomsStore } from '$lib/roomsStore';
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
				Find players for forgotten servers, overhaul mods, and retro netplay
				nights without account walls. This concept focuses on instant browsing,
				strong atmosphere, and a clear path to a later backend.
			</p>
			
			<div class="badges">
				<span class="badge">INSTANT SESSION BROWSE</span>
				<span class="badge">NO-AUTH CONCEPT</span>
				<span class="badge">RETRO SKIN SYSTEM</span>
			</div>
			
			<div class="actions">
				<button class="btn btn-primary">BROWSE SIGNALS</button>
				<button class="btn btn-secondary">STAGE A MOCK SIGNAL</button>
			</div>
		</div>

		<div class="stats-grid">
			<div class="stat-card">
				<h3 class="stat-title">OPEN SIGNALS</h3>
				<div class="stat-value">{$roomsStore.length}</div>
				<p class="stat-desc">Lobbies currently broadcasting</p>
			</div>
			<div class="stat-card">
				<h3 class="stat-title">AVERAGE PING</h3>
				<div class="stat-value">71 MS</div>
				<p class="stat-desc">Healthy enough for browse mode</p>
			</div>
		</div>
	</header>

	<section class="board-section">
		<div class="section-header">
			<h2 class="section-title">— ACTIVE SIGNALS</h2>
		</div>

		{#if $roomsStore.length === 0}
			<div class="empty-state">
				<p>Awaiting signals...</p>
			</div>
		{:else}
			<div class="signals-grid">
				{#each $roomsStore as room (room.name)}
					<div class="signal-card">
						<div class="signal-header">
							<span class="signal-badge">LOBBY</span>
							<span class="signal-slots">{room.players_active} / {room.players_max} SLOTS</span>
						</div>
						<div class="signal-name">{room.name}</div>
						<div class="signal-footer">
							<div class="progress-bar">
								<div class="progress-fill" style="width: {(room.players_active / room.players_max) * 100}%"></div>
							</div>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</section>
</div>
</div>

<style>
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
		margin-bottom: 1.5rem;
		text-transform: uppercase;
		line-height: 1.1;
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
</style>

