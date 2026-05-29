<script lang="ts">
	import { wordlists } from 'ethers';
	import { untrack } from 'svelte';

	const wordlist = wordlists.en;

	interface Props {
		value?: string;
	}

	let { value = $bindable() }: Props = $props();

	let words = $state<string[]>(Array(12).fill(''));
	let focusedIndex = $state(-1);
	let inputs = $state<(HTMLInputElement | null)[]>([]);

	// WATCHER: Sync Parent -> Child (e.g. when "Generate Phrase" is clicked)
	$effect(() => {
		if (value) {
			const splitWords = value.trim().split(/\s+/);
			if (splitWords.length === 12) {
				const currentInternal = untrack(() => words.map((w) => w.trim()).join(' '));
				if (value !== currentInternal) {
					words = splitWords.map((w) => w.toLowerCase().replace(/[^a-z]/g, ''));
				}
			}
		} else {
			const isInternalEmpty = untrack(() => words.every((w) => w === ''));
			if (!isInternalEmpty) {
				words = Array(12).fill('');
			}
		}
	});

	// WATCHER: Sync Child -> Parent (when user types)
	$effect(() => {
		const combined = words.map((w) => w.trim()).join(' ');
		if (value !== combined) {
			value = combined;
		}
	});

	function handleInput(index: number, rawVal: string) {
		const cleanVal = rawVal.toLowerCase().replace(/[^a-z]/g, '');
		words[index] = cleanVal;

		if (rawVal.includes(' ')) {
			words[index] = cleanVal.trim();
			if (words[index].length > 0) {
				focusNext(index);
			}
		}
	}

	function handleKeyDown(index: number, e: KeyboardEvent) {
		if (e.key === 'Backspace' && words[index] === '' && index > 0) {
			e.preventDefault();
			focusPrev(index);
		} else if (e.key === 'Enter' || e.key === 'Tab') {
			if (index < 11) {
				e.preventDefault();
				focusNext(index);
			}
		}
	}

	function handlePaste(e: ClipboardEvent) {
		e.preventDefault();
		const pasteData = e.clipboardData?.getData('text') ?? '';
		const pastedWords = pasteData.trim().split(/\s+/).slice(0, 12);

		const newWords = [...words];
		pastedWords.forEach((word, i) => {
			if (i < 12) {
				newWords[i] = word.toLowerCase().replace(/[^a-z]/g, '');
			}
		});
		words = newWords;
	}

	function focusNext(index: number) {
		if (index < 11) {
			inputs[index + 1]?.focus();
		}
	}

	function focusPrev(index: number) {
		if (index > 0) {
			inputs[index - 1]?.focus();
		}
	}

	function isValidWord(word: string) {
		if (!word) return true;
		try {
			return wordlist.getWordIndex(word.toLowerCase()) !== -1;
		} catch {
			return false;
		}
	}
</script>

<div class="mnemonic-grid" onpaste={handlePaste} role="none">
	{#each words as word, i (i)}
		{@const valid = isValidWord(word)}
		{@const filled = !!word}
		<div
			class="word-slot bevel-in"
			class:focused={focusedIndex === i}
			class:invalid={filled && !valid}
			class:valid-filled={filled && valid}
		>
			<span class="number small-caps">{(i + 1).toString().padStart(2, '0')}</span>
			{#if filled && valid}
				<span class="mark" aria-hidden="true">▸</span>
			{/if}
			<input
				type="text"
				bind:this={inputs[i]}
				bind:value={words[i]}
				oninput={(e) => handleInput(i, e.currentTarget.value)}
				onkeydown={(e) => handleKeyDown(i, e)}
				onfocus={() => (focusedIndex = i)}
				onblur={() => (focusedIndex = -1)}
				placeholder="—"
				autocomplete="off"
				spellcheck="false"
			/>
		</div>
	{/each}
</div>

<style>
	.mnemonic-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.6rem;
		padding: 1rem 0;
	}

	.word-slot {
		position: relative;
		display: flex;
		align-items: center;
		min-height: 52px;
		padding: 0 0.75rem 0 2.4rem;
		border-radius: 0;
		border: 1px solid var(--stone-5);
		background: linear-gradient(180deg, var(--stone-1) 0%, var(--stone-2) 100%);
		box-shadow:
			inset 0 1px 0 rgba(0, 0, 0, 0.85),
			inset 1px 0 0 rgba(0, 0, 0, 0.55),
			inset 0 -1px 0 rgba(227, 188, 116, 0.06),
			inset -1px 0 0 rgba(227, 188, 116, 0.04);
		transition:
			border-color 140ms ease,
			box-shadow 180ms ease,
			background 200ms ease;
	}

	.word-slot.valid-filled {
		box-shadow:
			inset 0 1px 0 rgba(0, 0, 0, 0.85),
			inset 1px 0 0 rgba(0, 0, 0, 0.55),
			inset 0 -1px 0 rgba(227, 188, 116, 0.08),
			inset -1px 0 0 rgba(227, 188, 116, 0.05),
			inset 0 0 12px rgba(227, 188, 116, 0.06);
	}

	.word-slot.focused {
		border: 1px solid var(--gold-base);
		box-shadow:
			0 0 0 1px var(--gold-faint),
			0 0 18px rgba(227, 188, 116, 0.18),
			inset 0 1px 0 rgba(0, 0, 0, 0.85),
			inset 0 0 14px rgba(227, 188, 116, 0.08);
	}

	.word-slot.invalid {
		border: 1px solid var(--blood);
		box-shadow:
			0 0 0 1px rgba(181, 54, 54, 0.28),
			0 0 16px rgba(181, 54, 54, 0.28),
			inset 0 1px 0 rgba(0, 0, 0, 0.85),
			inset 0 0 12px rgba(181, 54, 54, 0.1);
	}

	.number {
		position: absolute;
		top: 0.3rem;
		left: 0.5rem;
		font-family: var(--font-display);
		font-feature-settings:
			'smcp' 1,
			'c2sc' 1;
		font-size: 0.62rem;
		letter-spacing: var(--track-loose);
		color: var(--gold-muted);
		text-transform: uppercase;
		user-select: none;
		pointer-events: none;
		text-shadow: 0 1px 0 rgba(0, 0, 0, 0.85);
	}

	.mark {
		position: absolute;
		top: 0.3rem;
		right: 0.55rem;
		font-family: var(--font-mono);
		font-size: 0.7rem;
		color: var(--gold-base);
		text-shadow: 0 1px 0 rgba(0, 0, 0, 0.7);
		pointer-events: none;
		user-select: none;
	}

	input {
		flex: 1;
		min-width: 0;
		background: transparent;
		color: var(--bone);
		border: none;
		outline: none;
		width: 100%;
		font-family: var(--font-mono);
		font-size: 0.92rem;
		letter-spacing: 0.04em;
		padding: 0;
	}

	input::placeholder {
		color: var(--stone-7);
		opacity: 0.7;
	}

	input::selection {
		background: rgba(227, 188, 116, 0.28);
		color: var(--bone-bright);
	}

	@media (max-width: 540px) {
		.mnemonic-grid {
			grid-template-columns: repeat(2, 1fr);
			gap: 0.5rem;
		}
	}

	/* Very small phones: reclaim the wide left gutter and tighten cells so the
	   word inputs stay legible at ~300px wide. */
	@media (max-width: 360px) {
		.word-slot {
			min-height: 46px;
			padding: 0 0.5rem 0 1.6rem;
		}
		.number {
			left: 0.35rem;
			font-size: 0.55rem;
		}
		input {
			font-size: 0.82rem;
		}
	}
</style>
