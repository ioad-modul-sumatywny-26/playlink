<script lang="ts">
	import { onMount } from 'svelte';
	import InnerPanel from '$lib/components/chrome/InnerPanel.svelte';
	import SectionTitle from '$lib/components/chrome/SectionTitle.svelte';
	import PipMeter from '$lib/components/chrome/PipMeter.svelte';
	import { getHintsState } from '$lib/hintsContext.svelte';
	import { getBackendUrl } from '$lib/urls';

	let data = $state<unknown>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let latency = $state<number | null>(null);
	const backendLabel = $derived(getBackendUrl() || '—');

	const hintsState = getHintsState();
	$effect(() => {
		hintsState?.set([
			{ key: 'R', label: 'Re-ping', tone: 'green' },
			{ key: 'Esc', label: 'Back', tone: 'red' }
		]);
	});

	async function probe() {
		loading = true;
		error = null;
		const start = performance.now();
		try {
			const backendUrl = getBackendUrl();
			if (!backendUrl) {
				throw new Error('Missing backend URL');
			}

			const response = await fetch(`${backendUrl}/healthz`);
			if (!response.ok) {
				throw new Error(`Error: ${response.status}`);
			}
			data = await response.json();
			latency = Math.round(performance.now() - start);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		probe();
		function onKey(e: KeyboardEvent) {
			if (e.key === 'r' || e.key === 'R') probe();
		}
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});

	const pipValue = $derived.by(() => {
		if (error) return 0;
		if (latency === null) return 0;
		if (latency < 80) return 3;
		if (latency < 250) return 2;
		return 1;
	});
</script>

<svelte:head><title>PlayLink — Observatory</title></svelte:head>

<div class="test-page anim-content-in">
	<InnerPanel title="OBSERVATORY">
		<div class="probe">
			<div class="probe-row">
				<span class="probe-label">SHARD</span>
				<span class="probe-value">{backendLabel}</span>
			</div>
			<div class="probe-row">
				<span class="probe-label">STATUS</span>
				<span class="probe-value" class:err={error} class:ok={!error && !loading}>
					{#if loading}PROBING…{:else if error}FAILED{:else}BONDED{/if}
				</span>
			</div>
			<div class="probe-row">
				<span class="probe-label">LATENCY</span>
				<span class="probe-value mono">
					{#if latency !== null}{latency} MS{:else}—{/if}
				</span>
				<PipMeter value={pipValue} tone="auto" size="md" />
			</div>
		</div>

		<SectionTitle title="Echo" size="small" tone="gold" />

		{#if loading}
			<pre class="echo">…</pre>
		{:else if error}
			<pre class="echo err">{error}</pre>
		{:else}
			<pre class="echo scroll-d2">{JSON.stringify(data, null, 2)}</pre>
		{/if}
	</InnerPanel>
</div>

<style>
	.test-page {
		display: flex;
		flex: 1;
		flex-direction: column;
		max-width: 980px;
		width: 100%;
		margin: 0 auto;
	}

	.probe {
		display: grid;
		gap: 0.75rem;
		margin-bottom: 1.5rem;
	}

	.probe-row {
		display: grid;
		grid-template-columns: 120px 1fr auto;
		align-items: center;
		gap: 1rem;
		padding: 0.6rem 0.9rem;
		background: var(--stone-2);
		border: 1px solid var(--stone-5);
		box-shadow: var(--bevel-in);
	}

	.probe-label {
		font-family: var(--font-display);
		font-size: 0.72rem;
		letter-spacing: var(--track-extra);
		text-transform: uppercase;
		color: var(--bone-dim);
	}

	.probe-value {
		font-family: var(--font-mono);
		font-size: 0.85rem;
		color: var(--bone);
		word-break: break-all;
	}

	.probe-value.ok {
		color: var(--pip-good);
	}
	.probe-value.err {
		color: var(--blood-bright);
	}

	.mono {
		font-family: var(--font-mono);
	}

	.echo {
		font-family: var(--font-mono);
		font-size: 0.78rem;
		color: var(--gold-muted);
		background: var(--stone-1);
		border: 1px solid var(--stone-5);
		box-shadow: var(--bevel-in);
		padding: 1rem;
		margin: 0;
		max-height: 320px;
		overflow: auto;
		white-space: pre-wrap;
		word-break: break-all;
	}

	.echo.err {
		color: var(--blood-bright);
		border-color: var(--blood);
	}
</style>
