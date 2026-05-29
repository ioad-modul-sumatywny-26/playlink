<script lang="ts">
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import InnerPanel from '$lib/components/chrome/InnerPanel.svelte';
	import SectionTitle from '$lib/components/chrome/SectionTitle.svelte';
	import OrnateButton from '$lib/components/chrome/OrnateButton.svelte';
	import Sigil from '$lib/components/chrome/Sigil.svelte';
	import SystemDialog from '$lib/components/chrome/SystemDialog.svelte';
	import { getHintsState } from '$lib/hintsContext.svelte';
	import type { PageProps } from './$types';

	let { data, form }: PageProps = $props();

	let username = $state(data.profile.username);
	let saving = $state(false);
	let savedAt = $state<string | null>(null);

	// Client-side mirror of the backend rule: 3-20 chars, [a-zA-Z0-9_-].
	const USERNAME_RE = /^[a-zA-Z0-9_-]{3,20}$/;
	let clientValid = $derived(USERNAME_RE.test(username.trim()));
	let dirty = $derived(username.trim() !== data.profile.username);
	let serverError = $derived(form && 'error' in form ? form.error : '');
	let errorOpen = $derived(!!serverError);

	const hintsState = getHintsState();
	$effect(() => {
		hintsState?.set([{ key: 'Enter', label: 'Save Name', tone: 'gold' }]);
	});

	function fmtDate(iso: string | null): string {
		if (!iso) return '—';
		const d = new Date(iso);
		return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
	}
</script>

<svelte:head>
	<title>PlayLink — Profile</title>
</svelte:head>

<div class="profile-page anim-content-in">
	<InnerPanel title="Wanderer's Profile">
		<div class="profile">
			<div class="identity-head">
				<div class="sigil-halo">
					<Sigil address={data.profile.identity_address} size={88} />
				</div>
				<div class="identity">
					<h2 class="username etched-gold">{data.profile.username}</h2>
					<code class="address mono">{data.profile.identity_address}</code>
				</div>
			</div>

			<span class="hairline-gold"></span>

			<dl class="meta">
				<div class="meta-row">
					<dt>Bound Since</dt>
					<dd class="mono">{fmtDate(data.profile.created_at)}</dd>
				</div>
				<div class="meta-row">
					<dt>Last Seen</dt>
					<dd class="mono">{fmtDate(data.profile.last_login)}</dd>
				</div>
			</dl>

			<span class="hairline-gold"></span>

			<div class="edit-zone">
				<SectionTitle title="Chosen Name" size="small" tone="gold" />
				<form
					method="POST"
					action="?/update"
					class="edit-form"
					use:enhance={() => {
						saving = true;
						return async ({ result, update }) => {
							await update({ reset: false });
							saving = false;
							if (result.type === 'success') {
								savedAt = new Date().toLocaleTimeString();
								await invalidateAll();
							}
						};
					}}
				>
					<input
						name="username"
						class="name-input mono"
						bind:value={username}
						maxlength="20"
						autocomplete="off"
						spellcheck="false"
						aria-label="Username"
					/>
					<OrnateButton
						variant="primary"
						size="md"
						type="submit"
						loading={saving}
						disabled={saving || !dirty || !clientValid}
					>
						{saving ? 'Saving…' : 'Save Name'}
					</OrnateButton>
				</form>

				<p class="hint" class:bad={username.trim().length > 0 && !clientValid}>
					3–20 characters · letters, numbers, <code>_</code> or <code>-</code>
				</p>

				{#if savedAt && !dirty && !serverError}
					<p class="ok">Name saved ✓</p>
				{/if}
			</div>

			{#if serverError}
				<SystemDialog
					bind:open={errorOpen}
					title="Name Rejected"
					tone="blood"
					inline
					closeable
					onclose={() => (errorOpen = false)}
				>
					<p class="error-body">{serverError}</p>
				</SystemDialog>
			{/if}
		</div>
	</InnerPanel>
</div>

<style>
	.profile-page {
		max-width: 760px;
		margin: 2rem auto;
		padding: 0 1rem;
	}

	.profile {
		display: flex;
		flex-direction: column;
	}

	.etched-gold {
		font-family: var(--font-display);
		font-weight: normal;
		color: var(--bone-bright);
		text-shadow:
			0 0 14px rgba(227, 188, 116, 0.16),
			0 1px 0 rgba(0, 0, 0, 0.85);
	}

	.mono {
		font-family: var(--font-mono);
	}

	.hairline-gold {
		display: block;
		height: 1px;
		width: 100%;
		background: var(--hair-gold);
		border: 0;
		margin: 1.25rem 0;
	}

	.identity-head {
		display: flex;
		gap: 1.4rem;
		align-items: center;
	}

	.sigil-halo {
		flex-shrink: 0;
	}

	.identity {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		min-width: 0;
		flex: 1;
	}

	.username {
		margin: 0;
		font-size: 1.9rem;
		letter-spacing: var(--track-display);
		text-transform: uppercase;
		line-height: 1.05;
		word-break: break-word;
	}

	.address {
		display: inline-block;
		font-size: 0.78rem;
		color: var(--bone-muted);
		letter-spacing: 0.04em;
		word-break: break-all;
	}

	.meta {
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
	}

	.meta-row {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: baseline;
	}

	.meta-row dt {
		font-family: var(--font-display);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		font-size: 0.8rem;
		color: var(--gold-muted);
	}

	.meta-row dd {
		margin: 0;
		font-size: 0.82rem;
		color: var(--bone-muted);
		text-align: right;
	}

	.edit-zone {
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
	}

	.edit-form {
		display: flex;
		gap: 0.8rem;
		align-items: stretch;
		flex-wrap: wrap;
	}

	.name-input {
		flex: 1;
		min-width: 200px;
		background: var(--ink-well, rgba(0, 0, 0, 0.35));
		border: 1px solid var(--hair-gold);
		color: var(--bone-bright);
		font-size: 1rem;
		letter-spacing: 0.04em;
		padding: 0.6rem 0.8rem;
	}

	.name-input:focus {
		outline: none;
		border-color: var(--gold-base);
		box-shadow: 0 0 8px rgba(227, 188, 116, 0.25);
	}

	.hint {
		margin: 0;
		font-family: var(--font-display);
		font-size: 0.8rem;
		color: var(--bone-muted);
		letter-spacing: 0.02em;
	}

	.hint code {
		font-family: var(--font-mono);
		color: var(--gold-muted);
	}

	.hint.bad {
		color: var(--blood-bright);
	}

	.ok {
		margin: 0;
		font-family: var(--font-mono);
		font-size: 0.82rem;
		color: var(--pip-good);
	}

	.error-body {
		margin: 0;
		font-family: var(--font-mono);
		font-size: 0.85rem;
		color: var(--blood-bright);
		line-height: 1.45;
		word-break: break-word;
	}

	@media (max-width: 540px) {
		.identity-head {
			flex-direction: column;
			align-items: flex-start;
		}
	}
</style>
