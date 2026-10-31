<script lang="ts">
	import { onMount } from 'svelte';
	import type { ProbeResult, RegionConfig, RegionId } from '$lib/regions';
	import {
		isMeaningfullyFaster,
		liveRegionsSorted,
		probeAll,
		readSavedRegion,
		redirectToRegion,
		saveRegion
	} from '$lib/regions';
	import Crest from '$lib/components/chrome/Crest.svelte';
	import InnerPanel from '$lib/components/chrome/InnerPanel.svelte';
	import OrnateButton from '$lib/components/chrome/OrnateButton.svelte';
	import SectionTitle from '$lib/components/chrome/SectionTitle.svelte';

	let { regions }: { regions: RegionConfig[] } = $props();

	let status = $state<'probing' | 'redirecting' | 'propose' | 'failed'>('probing');
	let message = $state('Measuring both regions…');
	let results = $state<ProbeResult[]>([]);
	let savedRegion = $state<RegionConfig | null>(null);
	let proposedRegion = $state<RegionConfig | null>(null);

	async function select(region: RegionConfig) {
		saveRegion(region.id);
		status = 'redirecting';
		message = `Opening ${region.label}…`;
		if (!redirectToRegion(region.id, regions)) {
			status = 'failed';
			message = `You are already on the ${region.label} host. Open the lobby manually.`;
		}
	}

	function keepSaved() {
		if (!savedRegion) return;
		void select(savedRegion);
	}

	function acceptProposal() {
		if (!proposedRegion) return;
		void select(proposedRegion);
	}

	onMount(async () => {
		const forced = new URLSearchParams(window.location.search).get('region');
		if (forced === 'eu' || forced === 'us') {
			const region = regions.find((candidate) => candidate.id === forced);
			if (region) {
				await select(region);
				return;
			}
		}

		message = 'Measuring both regions…';
		results = await probeAll(regions);
		const live = liveRegionsSorted(results);

		const savedId: RegionId | null = readSavedRegion();
		const saved = savedId ? (regions.find((candidate) => candidate.id === savedId) ?? null) : null;
		const savedProbe = saved
			? results.find((result) => result.region.id === saved.id)
			: undefined;

		// Saved region is silent -> fail over to the fastest live region.
		if (saved && savedProbe && !savedProbe.ok) {
			if (live.length === 0) {
				status = 'failed';
				message = 'Saved region is offline and no fallback is responding.';
				return;
			}
			message = `Saved region ${saved.label} is offline — opening ${live[0].region.label}…`;
			await select(live[0].region);
			return;
		}

		// Saved region is live: stay there unless another region is clearly faster,
		// in which case only *propose* a change (do not auto-switch).
		if (saved && savedProbe?.ok) {
			savedRegion = saved;
			const faster = live.find((result) => result.region.id !== saved.id);
			if (
				faster &&
				isMeaningfullyFaster(faster.ms, savedProbe.ms ?? null)
			) {
				proposedRegion = faster.region;
				status = 'propose';
				message = `${faster.region.label} looks faster (${Math.round(faster.ms ?? 0)} ms vs ${Math.round(savedProbe.ms ?? 0)} ms). Stay on ${saved.label}, or switch?`;
				return;
			}
			await select(saved);
			return;
		}

		// First visit (no saved region): open the fastest live one.
		if (live.length === 0) {
			status = 'failed';
			message = 'Neither region is responding. You can still try a direct link below.';
			return;
		}

		await select(live[0].region);
	});

	function latencyFor(region: RegionConfig): string {
		const result = results.find((candidate) => candidate.region.id === region.id);
		if (!result) return '—';
		if (!result.ok) return 'offline';
		return `${Math.round(result.ms ?? 0)} ms`;
	}
</script>

<svelte:head><title>PlayLink — Choose region</title></svelte:head>

<div class="chooser anim-content-in">
	<div class="crest"><Crest size={96} tone="gold" /></div>
	<h1 class="title etched-gold">PLAYLINK</h1>
	<p class="subtitle small-caps">Choose your lobby region</p>

	<InnerPanel title="REGION SELECT">
		<div class="status">
			<span
				class="status-dot"
				class:failed={status === 'failed'}
				class:propose={status === 'propose'}
			></span>
			<span>{message}</span>
		</div>

		{#if status === 'propose' && savedRegion && proposedRegion}
			<div class="propose-actions">
				<OrnateButton variant="primary" size="sm" onclick={keepSaved}>
					Stay on {savedRegion.label}
				</OrnateButton>
				<OrnateButton variant="secondary" size="sm" onclick={acceptProposal}>
					Switch to {proposedRegion.label}
				</OrnateButton>
			</div>
		{/if}

		<div class="region-list">
			{#each regions as region (region.id)}
				<div class="region-row">
					<div class="region-name">
						<span class="region-label">{region.label}</span>
						<span class="region-id small-caps">{region.id.toUpperCase()}</span>
					</div>
					<span class="region-latency mono">{latencyFor(region)}</span>
					<OrnateButton
						variant="secondary"
						size="sm"
						disabled={!region.frontend || status === 'redirecting'}
						onclick={() => void select(region)}
					>
						Open
					</OrnateButton>
				</div>
			{/each}
		</div>

		<SectionTitle title="Notes" size="small" tone="gold" />
		<ul class="notes">
			<li>Your first visit measures both regions and opens the faster live one.</li>
			<li>The choice is remembered. A faster second region is only a proposal — never forced.</li>
			<li>Auto-switch happens only when the saved region does not respond.</li>
			<li>
				Each region has its own session — switching requires signing in with the same 12 words.
			</li>
		</ul>

		{#if status === 'failed'}
			<div class="manual">
				{#each regions as region (region.id)}
					{#if region.frontend}
						<a class="manual-link" href={region.frontend}>{region.label} — direct link</a>
					{/if}
				{/each}
			</div>
		{/if}
	</InnerPanel>
</div>

<style>
	.chooser {
		max-width: 620px;
		width: 100%;
		margin: 0 auto;
		padding: 1rem 0 4rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
	}

	.crest {
		filter: drop-shadow(0 1px 0 rgba(0, 0, 0, 0.7));
	}

	.title {
		font-family: var(--font-display);
		font-size: clamp(2rem, 6vw, 3.5rem);
		letter-spacing: 0.08em;
		margin: 0;
	}

	.subtitle {
		color: var(--bone-muted);
		font-family: var(--font-display);
		letter-spacing: var(--track-extra);
		font-size: 0.8rem;
		margin: 0 0 0.5rem;
	}

	.chooser :global(.inner-panel) {
		width: 100%;
	}

	.status {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		font-family: var(--font-mono);
		font-size: 0.78rem;
		color: var(--bone);
		padding: 0.6rem 0.8rem;
		border: 1px solid var(--stone-5);
		background: var(--stone-1);
		box-shadow: var(--bevel-in);
		margin-bottom: 1rem;
	}

	.status-dot {
		width: 8px;
		height: 8px;
		background: var(--pip-good);
		box-shadow: 0 0 6px var(--pip-good);
		flex-shrink: 0;
	}

	.status-dot.failed {
		background: var(--blood-bright);
		box-shadow: 0 0 6px var(--blood-bright);
	}

	.status-dot.propose {
		background: var(--gold-base);
		box-shadow: 0 0 6px var(--gold-base);
	}

	.propose-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		margin: -0.35rem 0 1rem;
	}

	.region-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 1.25rem;
	}

	.region-row {
		display: grid;
		grid-template-columns: 1fr auto auto;
		align-items: center;
		gap: 0.9rem;
		padding: 0.65rem 0.8rem;
		border: 1px solid var(--stone-5);
		background: var(--stone-2);
		box-shadow: var(--bevel-in);
	}

	.region-name {
		display: flex;
		align-items: baseline;
		gap: 0.55rem;
	}

	.region-label {
		font-family: var(--font-display);
		font-size: 0.95rem;
		letter-spacing: var(--track-loose);
		color: var(--bone-bright);
		text-transform: uppercase;
	}

	.region-id {
		font-family: var(--font-mono);
		font-size: 0.65rem;
		color: var(--bone-dim);
		letter-spacing: var(--track-loose);
	}

	.region-latency {
		font-size: 0.78rem;
		color: var(--gold-muted);
		min-width: 4.5em;
		text-align: right;
	}

	.mono {
		font-family: var(--font-mono);
	}

	.notes {
		margin: 0;
		padding-left: 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-family: var(--font-display);
		font-size: 0.78rem;
		line-height: 1.45;
		color: var(--bone-muted);
	}

	.manual {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		margin-top: 1rem;
	}

	.manual-link {
		font-family: var(--font-mono);
		font-size: 0.78rem;
		color: var(--gold-muted);
		text-decoration: none;
		border-bottom: 1px dashed var(--gold-muted);
		align-self: flex-start;
	}

	.manual-link:hover {
		color: var(--gold-lit);
		border-bottom-color: var(--gold-lit);
	}
</style>
