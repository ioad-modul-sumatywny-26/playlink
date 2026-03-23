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
	let inputs = $state<(HTMLInputElement | undefined)[]>([]);

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
		<div
			class="word-slot"
			class:focused={focusedIndex === i}
			class:invalid={word && !isValidWord(word)}
		>
			<span class="number">{i + 1}</span>
			<input
				type="text"
				bind:this={inputs[i]}
				bind:value={words[i]}
				oninput={(e) => handleInput(i, e.currentTarget.value)}
				onkeydown={(e) => handleKeyDown(i, e)}
				onfocus={() => (focusedIndex = i)}
				onblur={() => (focusedIndex = -1)}
				placeholder="..."
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
		gap: 0.5rem;
		margin: 1rem 0;
	}

	.word-slot {
		display: flex;
		border: 1px solid #ccc;
		padding: 0.2rem;
	}

	.number {
		font-size: 0.8rem;
		color: #888;
		margin-right: 0.4rem;
	}

	input {
		border: none;
		outline: none;
		width: 100%;
	}
</style>
