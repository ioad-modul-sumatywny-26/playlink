<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
	import type { PageData } from './$types';
	import { createChatStore, type ChatMessage, type ChatStore } from '$lib/chatStore';

	let { data }: { data: PageData } = $props();

	let chat = $state<ChatStore | null>(null);
	let messages = $state<ChatMessage[]>([]);
	let input = $state('');
	let scroller: HTMLDivElement | null = $state(null);

	onMount(() => {
		const store = createChatStore(data.roomName, data.token);
		chat = store;
		const unsubscribe = store.subscribe(async (m) => {
			messages = m;
			await tick();
			if (scroller) scroller.scrollTop = scroller.scrollHeight;
		});
		return unsubscribe;
	});

	onDestroy(() => {
		chat?.destroy();
	});

	function send() {
		if (!chat || !input.trim()) return;
		chat.send(input);
		input = '';
	}

	function onKey(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			send();
		}
	}

	function shortAddr(addr: string): string {
		if (addr.length <= 10) return addr;
		return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
	}

	function fmtTime(iso: string): string {
		try {
			return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
		} catch {
			return '';
		}
	}
</script>

<section class="page">
	<header>
		<a class="back" href="/rooms">← Rooms</a>
		<div class="title">
			<h1>{data.roomName}</h1>
			{#if data.roomGame}<span class="game">{data.roomGame}</span>{/if}
		</div>
		{#if data.description || data.communicatorLink || data.requirements}
			<div class="meta-block">
				{#if data.description}
					<div class="meta-item">
						<span class="meta-label">Description</span>
						<p class="meta-value">{data.description}</p>
					</div>
				{/if}
				{#if data.communicatorLink}
					<div class="meta-item">
						<span class="meta-label">Communicator</span>
						<a class="meta-link" href={data.communicatorLink} target="_blank" rel="noopener">
							{data.communicatorLink}
						</a>
					</div>
				{/if}
				{#if data.requirements}
					<div class="meta-item">
						<span class="meta-label">Requirements</span>
						<p class="meta-value">{data.requirements}</p>
					</div>
				{/if}
			</div>
		{/if}
	</header>

	<div class="chat" bind:this={scroller}>
		{#if messages.length === 0}
			<p class="empty">No messages yet. Say hi.</p>
		{:else}
			{#each messages as msg (msg.id)}
				<article
					class="msg"
					class:mine={msg.sender_address.toLowerCase() === data.address.toLowerCase()}
				>
					<div class="meta">
						<span class="user">{msg.sender_username || shortAddr(msg.sender_address)}</span>
						<span class="time">{fmtTime(msg.created_at)}</span>
					</div>
					<div class="content">{msg.content}</div>
				</article>
			{/each}
		{/if}
	</div>

	<form
		class="composer"
		onsubmit={(e) => {
			e.preventDefault();
			send();
		}}
	>
		<input
			type="text"
			placeholder="Message…"
			bind:value={input}
			onkeydown={onKey}
			maxlength={1000}
			autocomplete="off"
		/>
		<button type="submit" disabled={!input.trim()}>Send</button>
	</form>
</section>

<style>
	.page {
		max-width: 760px;
		margin: 0 auto;
		padding: 1.5rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
		min-height: calc(100vh - 4rem);
	}

	header {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.back {
		color: #e3bc74;
		text-decoration: none;
		font-size: 0.9rem;
		opacity: 0.8;
	}
	.back:hover {
		opacity: 1;
	}

	.title {
		display: flex;
		align-items: baseline;
		gap: 0.75rem;
	}

	h1 {
		margin: 0;
		font-size: 1.6rem;
		color: #f4ecd8;
	}

	.game {
		color: #e3bc74;
		font-size: 0.9rem;
		opacity: 0.85;
	}

	.meta-block {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-top: 0.5rem;
		padding: 0.75rem 1rem;
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid rgba(227, 188, 116, 0.2);
		border-radius: 8px;
	}

	.meta-item {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.meta-label {
		font-size: 0.7rem;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: #e3bc74;
		opacity: 0.85;
	}

	.meta-value {
		margin: 0;
		color: #f4ecd8;
		font-size: 0.9rem;
		line-height: 1.4;
		white-space: pre-wrap;
		word-wrap: break-word;
	}

	.meta-link {
		color: #f4ecd8;
		font-size: 0.9rem;
		word-break: break-all;
		text-decoration: underline;
		text-decoration-color: rgba(227, 188, 116, 0.4);
	}

	.meta-link:hover {
		text-decoration-color: #e3bc74;
	}

	.chat {
		flex: 1;
		min-height: 50vh;
		max-height: 65vh;
		overflow-y: auto;
		padding: 1rem;
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid rgba(227, 188, 116, 0.2);
		border-radius: 12px;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.empty {
		margin: auto;
		color: rgba(244, 236, 216, 0.5);
		font-style: italic;
	}

	.msg {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		max-width: 85%;
		padding: 0.5rem 0.75rem;
		background: rgba(0, 0, 0, 0.25);
		border-left: 2px solid rgba(227, 188, 116, 0.4);
		border-radius: 6px;
	}

	.msg.mine {
		align-self: flex-end;
		border-left: none;
		border-right: 2px solid #e3bc74;
		background: rgba(227, 188, 116, 0.08);
	}

	.meta {
		display: flex;
		gap: 0.5rem;
		font-size: 0.75rem;
		opacity: 0.7;
	}

	.user {
		color: #e3bc74;
		font-weight: 600;
	}

	.time {
		color: rgba(244, 236, 216, 0.5);
	}

	.content {
		color: #f4ecd8;
		word-wrap: break-word;
		white-space: pre-wrap;
	}

	.composer {
		display: flex;
		gap: 0.5rem;
	}

	.composer input {
		flex: 1;
		padding: 0.65rem 0.9rem;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(227, 188, 116, 0.3);
		border-radius: 8px;
		color: #f4ecd8;
		font-size: 0.95rem;
	}

	.composer input:focus {
		outline: none;
		border-color: #e3bc74;
	}

	.composer button {
		padding: 0.65rem 1.2rem;
		background: #e3bc74;
		color: #0d0d0d;
		border: none;
		border-radius: 8px;
		font-weight: 600;
		cursor: pointer;
	}

	.composer button:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
</style>
