<script lang="ts">
	import { deserialize } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import SystemDialog from '$lib/components/chrome/SystemDialog.svelte';
	import OrnateButton from '$lib/components/chrome/OrnateButton.svelte';

	interface Props {
		open: boolean;
		games: string[];
		onclose: () => void;
	}

	let { open = $bindable(), games, onclose }: Props = $props();

	let newName = $state('');
	let busy = $state(false);
	let feedback = $state<{ text: string; type: 'success' | 'error' } | null>(null);
	// When deletion is blocked by active rooms we stash the game + message here so
	// the operator can confirm a force-delete.
	let conflict = $state<{ game: string; message: string } | null>(null);

	type ActionResult =
		| { type: 'success'; data?: Record<string, unknown> }
		| { type: 'failure'; data?: Record<string, unknown> }
		| { type: 'error' }
		| { type: 'redirect' };

	async function callAction(action: string, fields: Record<string, string>): Promise<ActionResult> {
		const body = new FormData();
		for (const [k, v] of Object.entries(fields)) body.append(k, v);
		const res = await fetch(`?/${action}`, { method: 'POST', body });
		return deserialize(await res.text()) as ActionResult;
	}

	async function addGame() {
		const name = newName.trim();
		if (!name || busy) return;
		busy = true;
		feedback = null;
		try {
			const result = await callAction('addGame', { name });
			if (result.type === 'success') {
				newName = '';
				feedback = { text: `Added “${name}”.`, type: 'success' };
				await invalidateAll();
			} else if (result.type === 'failure') {
				feedback = { text: String(result.data?.error ?? 'Failed to add game.'), type: 'error' };
			} else {
				feedback = { text: 'Failed to add game.', type: 'error' };
			}
		} finally {
			busy = false;
		}
	}

	async function deleteGame(game: string, force = false) {
		if (busy) return;
		busy = true;
		feedback = null;
		try {
			const result = await callAction('deleteGame', {
				name: game,
				...(force ? { force: 'true' } : {})
			});
			if (result.type === 'success') {
				conflict = null;
				feedback = { text: `Deleted “${game}”.`, type: 'success' };
				await invalidateAll();
			} else if (result.type === 'failure' && result.data?.conflict) {
				conflict = {
					game,
					message: String(result.data?.error ?? `Active rooms are still playing ${game}.`)
				};
			} else if (result.type === 'failure') {
				feedback = { text: String(result.data?.error ?? 'Failed to delete game.'), type: 'error' };
			} else {
				feedback = { text: 'Failed to delete game.', type: 'error' };
			}
		} finally {
			busy = false;
		}
	}

	function close() {
		// Reset transient state so a re-open starts clean.
		newName = '';
		feedback = null;
		conflict = null;
		open = false;
		onclose();
	}

	function onAddKey(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			addGame();
		}
	}
</script>

<SystemDialog {open} title="Game Manager" tone="gold" modal width="520px" onclose={close}>
	{#if conflict}
		<div class="conflict" role="alert">
			<p class="conflict-text">{conflict.message}</p>
			<OrnateButton
				variant="danger"
				size="sm"
				disabled={busy}
				onclick={() => deleteGame(conflict!.game, true)}
			>
				Force Delete
			</OrnateButton>
			<button class="link-btn" type="button" onclick={() => (conflict = null)}>Cancel</button>
		</div>
	{/if}

	{#if feedback}
		<p class="feedback" class:is-error={feedback.type === 'error'}>{feedback.text}</p>
	{/if}

	<section class="section">
		<h4 class="section-title small-caps">Add Game <span class="rule"></span></h4>
		<div class="add-row">
			<input
				class="text-input bevel-in"
				type="text"
				bind:value={newName}
				onkeydown={onAddKey}
				placeholder="New game name…"
				maxlength={100}
				autocomplete="off"
			/>
			<OrnateButton
				variant="primary"
				size="md"
				disabled={busy || !newName.trim()}
				onclick={addGame}
			>
				Add Game
			</OrnateButton>
		</div>
	</section>

	<section class="section">
		<h4 class="section-title small-caps">Existing Games <span class="rule"></span></h4>
		{#if games.length === 0}
			<p class="empty">No game categories defined.</p>
		{:else}
			<ul class="game-list">
				{#each games as game (game)}
					<li class="game-row">
						<span class="game-name small-caps">{game}</span>
						<OrnateButton
							variant="danger"
							size="sm"
							disabled={busy}
							onclick={() => deleteGame(game)}
						>
							Delete
						</OrnateButton>
					</li>
				{/each}
			</ul>
		{/if}
	</section>

	{#snippet footer()}
		<OrnateButton variant="ghost" size="md" onclick={close}>Close</OrnateButton>
	{/snippet}
</SystemDialog>

<style>
	.section {
		margin-bottom: 1.4rem;
	}
	.section:last-of-type {
		margin-bottom: 0;
	}

	.section-title {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin: 0 0 0.75rem 0;
		font-family: var(--font-display);
		font-size: 0.78rem;
		letter-spacing: var(--track-extra);
		color: var(--gold-base);
		text-transform: uppercase;
	}

	.rule {
		flex: 1;
		height: 1px;
		background: var(--hair-gold);
	}

	.add-row {
		display: flex;
		gap: 0.6rem;
		align-items: stretch;
	}

	.text-input {
		flex: 1;
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

	.game-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.game-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.55rem 0.75rem;
		background: #080604;
		border: 1px solid var(--stone-5);
		border-left: 2px solid var(--gold-dark);
	}

	.game-name {
		font-family: var(--font-display);
		font-size: 0.92rem;
		color: var(--bone-bright);
		letter-spacing: var(--track-loose);
		text-transform: uppercase;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.empty {
		margin: 0;
		font-family: var(--font-display);
		font-style: italic;
		color: var(--bone-muted);
		letter-spacing: var(--track-loose);
	}

	.conflict {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1.1rem;
		padding: 0.8rem 0.9rem;
		border: 1px solid #4a1414;
		border-left: 3px solid var(--blood);
		background: rgba(181, 54, 54, 0.1);
	}

	.conflict-text {
		flex: 1 1 100%;
		margin: 0;
		font-family: var(--font-mono);
		font-size: 0.82rem;
		color: var(--blood-bright);
		line-height: 1.4;
	}

	.link-btn {
		appearance: none;
		background: transparent;
		border: 0;
		color: var(--bone-muted);
		font-family: var(--font-display);
		font-size: 0.72rem;
		letter-spacing: var(--track-loose);
		text-transform: uppercase;
		cursor: pointer;
		padding: 0.3rem 0.2rem;
	}
	.link-btn:hover {
		color: var(--bone-bright);
	}

	.feedback {
		margin: 0 0 1.1rem 0;
		padding: 0.6rem 0.8rem;
		font-family: var(--font-mono);
		font-size: 0.8rem;
		color: var(--pip-good);
		border: 1px solid rgba(127, 191, 92, 0.4);
		background: rgba(127, 191, 92, 0.08);
	}
	.feedback.is-error {
		color: var(--blood-bright);
		border-color: #4a1414;
		background: rgba(181, 54, 54, 0.08);
	}
</style>
