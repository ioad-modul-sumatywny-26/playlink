<script lang="ts">
	import { onDestroy, onMount, tick, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import type { PageData } from './$types';
	import {
		createChatStore,
		type ChatMessage,
		type ChatStore,
		type RoomEventState,
		type RoomMember
	} from '$lib/chatStore';
	import InnerPanel from '$lib/components/chrome/InnerPanel.svelte';
	import SectionTitle from '$lib/components/chrome/SectionTitle.svelte';
	import OrnateButton from '$lib/components/chrome/OrnateButton.svelte';
	import Sigil from '$lib/components/chrome/Sigil.svelte';
	import Crest from '$lib/components/chrome/Crest.svelte';
	import SystemDialog from '$lib/components/chrome/SystemDialog.svelte';
	import RoomEvent from '$lib/components/RoomEvent.svelte';
	import { getHintsState } from '$lib/hintsContext.svelte';

	const CLOSE_REDIRECT_SECONDS = 5;

	let { data, form }: { data: PageData; form: { error?: string } | null } = $props();

	let chat = $state<ChatStore | null>(null);
	let messages = $state<ChatMessage[]>([]);
	let event = $state<RoomEventState | null>(untrack(() => data.event));
	let roster = $state<RoomMember[]>(untrack(() => data.members));
	let input = $state('');
	let scroller: HTMLDivElement | null = $state(null);

	// Set when an admin closes the room; freezes the UI and counts down to a
	// redirect back to the rooms list.
	let closed = $state(false);
	let redirectIn = $state(CLOSE_REDIRECT_SECONDS);

	function leaveClosedRoom() {
		goto('/rooms');
	}

	const hintsState = getHintsState();

	$effect(() => {
		hintsState?.set([
			{ key: 'Enter', label: 'Transmit', tone: 'gold' },
			{ key: '⇧Enter', label: 'Newline', tone: 'stone' },
			{ key: 'Esc', label: 'Leave', tone: 'red' }
		]);
	});

	onMount(() => {
		const store = createChatStore(data.roomName, data.token, {
			initialEvent: data.event,
			initialMembers: data.members
		});
		chat = store;
		const unsubMessages = store.messages.subscribe(async (m) => {
			messages = m;
			await tick();
			if (scroller) scroller.scrollTop = scroller.scrollHeight;
		});
		const unsubEvent = store.event.subscribe((e) => {
			event = e;
		});
		const unsubMembers = store.members.subscribe((m) => {
			roster = m;
		});
		let countdown: ReturnType<typeof setInterval> | null = null;
		let redirectTimer: ReturnType<typeof setTimeout> | null = null;
		const unsubClosed = store.closed.subscribe((isClosed) => {
			if (!isClosed || closed) return;
			closed = true;
			redirectIn = CLOSE_REDIRECT_SECONDS;
			countdown = setInterval(() => {
				redirectIn = Math.max(0, redirectIn - 1);
			}, 1000);
			redirectTimer = setTimeout(leaveClosedRoom, CLOSE_REDIRECT_SECONDS * 1000);
		});
		return () => {
			unsubMessages();
			unsubEvent();
			unsubMembers();
			unsubClosed();
			if (countdown) clearInterval(countdown);
			if (redirectTimer) clearTimeout(redirectTimer);
		};
	});

	onDestroy(() => {
		chat?.destroy();
	});

	function send() {
		if (closed || !chat || !input.trim()) return;
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
		if (!addr) return '';
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

	interface PartyMember {
		address: string;
		username: string;
		isMe: boolean;
	}

	const partyMembers = $derived.by<PartyMember[]>(() => {
		const meKey = (data.address ?? '').toLowerCase();
		return roster.map((m) => ({
			address: m.address,
			username: m.username || shortAddr(m.address),
			isMe: m.address.toLowerCase() === meKey
		}));
	});

	const eventMembers = $derived(roster.map((m) => ({ address: m.address, username: m.username })));

	function isMine(addr: string): boolean {
		return (addr ?? '').toLowerCase() === (data.address ?? '').toLowerCase();
	}

	const hasMetadata = $derived(
		Boolean(data.description || data.communicatorLink || data.requirements)
	);
</script>

<svelte:head>
	<title>PlayLink — {data.roomName}</title>
</svelte:head>

<section class="room-page">
	<div class="rail">
		<InnerPanel padded={false}>
			<div class="rail-inner">
				<SectionTitle title="Party" size="small" tone="gold">
					{partyMembers.length} / {data.memberAddresses.length || partyMembers.length}
				</SectionTitle>

				<ul class="member-list scroll-d2">
					{#each partyMembers as m (m.address)}
						<li class="member" class:is-me={m.isMe}>
							<Sigil address={m.address} size={28} />
							<div class="member-meta">
								<span class="member-name small-caps" class:is-me-name={m.isMe}>
									{m.username}
								</span>
								<span class="member-addr">{shortAddr(m.address)}</span>
							</div>
						</li>
					{/each}
				</ul>
			</div>
		</InnerPanel>
	</div>

	<div class="main">
		<InnerPanel padded={false}>
			<div class="main-inner">
				<header class="room-head">
					<div class="head-row top-row">
						<a class="back small-caps" href="/rooms">◄ Rooms</a>
						<div class="shard">
							<span class="shard-label small-caps">Shard Hash</span>
							<span class="shard-hash">{shortAddr(data.address)}</span>
						</div>
					</div>
					<div class="head-row title-row">
						<h1 class="room-title etched-gold small-caps">{data.roomName}</h1>
						{#if data.roomGame}
							<span class="game small-caps">
								<span class="dot" aria-hidden="true">·</span>
								Game · {data.roomGame}
							</span>
						{/if}
					</div>
					<span class="head-rule" aria-hidden="true"></span>

					{#if hasMetadata}
						<dl class="meta-list">
							{#if data.description}
								<div class="meta-item">
									<dt class="small-caps">Description</dt>
									<dd>{data.description}</dd>
								</div>
							{/if}
							{#if data.communicatorLink}
								<div class="meta-item">
									<dt class="small-caps">Communicator</dt>
									<dd>
										<a
											class="meta-link"
											href={data.communicatorLink}
											target="_blank"
											rel="noopener noreferrer"
										>
											{data.communicatorLink}
										</a>
									</dd>
								</div>
							{/if}
							{#if data.requirements}
								<div class="meta-item">
									<dt class="small-caps">Requirements</dt>
									<dd>{data.requirements}</dd>
								</div>
							{/if}
						</dl>
					{/if}
				</header>

				<div class="event-slot">
					<RoomEvent
						{event}
						isCreator={data.isCreator}
						isMember={true}
						viewerAddress={data.address}
						members={eventMembers}
						formError={form?.error ?? null}
					/>
				</div>

				<div class="chat-wrap">
					<div class="chat scroll-d2 bevel-in" bind:this={scroller}>
						<div class="chat-noise" aria-hidden="true"></div>
						{#if messages.length === 0}
							<div class="empty">
								<Crest size={56} tone="iron" />
								<p>The void is silent. Speak first.</p>
							</div>
						{:else}
							<ul class="msg-list">
								{#each messages as msg (msg.id)}
									{@const mine = isMine(msg.sender_address)}
									<li class="msg-row" class:mine class:other={!mine}>
										<article class="msg" class:mine class:other={!mine}>
											<div class="msg-meta">
												<span class="sender small-caps">
													{mine ? 'You' : msg.sender_username || shortAddr(msg.sender_address)}
												</span>
												<span class="sep" aria-hidden="true">·</span>
												<span class="addr">{shortAddr(msg.sender_address)}</span>
												<span class="sep" aria-hidden="true">·</span>
												<span class="time">{fmtTime(msg.created_at)}</span>
											</div>
											<div class="content">{msg.content}</div>
										</article>
									</li>
								{/each}
							</ul>
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
							class="msg-input bevel-in"
							type="text"
							bind:value={input}
							onkeydown={onKey}
							placeholder={closed ? 'Room closed' : 'Speak…'}
							maxlength={1000}
							autocomplete="off"
							disabled={closed}
						/>
						<OrnateButton
							type="submit"
							variant="primary"
							size="md"
							disabled={closed || !input.trim()}
						>
							Transmit
						</OrnateButton>
					</form>
				</div>
			</div>
		</InnerPanel>
	</div>
</section>

{#if closed}
	<SystemDialog
		open={true}
		title="Connection Lost"
		tone="blood"
		modal
		closeable={false}
		width="460px"
	>
		<p class="closed-text">This room has been closed by an administrator.</p>
		<p class="closed-sub">
			Returning to the rooms list in {redirectIn}
			{redirectIn === 1 ? 'second' : 'seconds'}…
		</p>
		{#snippet footer()}
			<OrnateButton variant="primary" size="md" onclick={leaveClosedRoom}
				>Return to Rooms</OrnateButton
			>
		{/snippet}
	</SystemDialog>
{/if}

<style>
	.room-page {
		display: grid;
		grid-template-columns: 240px 1fr;
		/* `minmax(0, 1fr)` row + a viewport-bounded height give the grid a definite
		   height, so the flex chain inside can hand the chat exactly the leftover
		   space (and scroll it) instead of growing the page. The subtracted ~20rem
		   accounts for the fixed page chrome above/below (frame, brand, tabs, hint
		   bar). */
		grid-template-rows: minmax(0, 1fr);
		gap: 1rem;
		min-height: 380px;
		height: calc(100dvh - 10rem);
		align-items: stretch;
	}

	.rail,
	.main {
		display: flex;
		min-height: 0;
		min-width: 0;
	}

	.rail-inner {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		padding: 1rem 0.85rem;
		min-height: 0;
		flex: 1;
	}

	.member-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0;
		overflow-y: auto;
		min-height: 0;
		flex: 1;
	}

	.member {
		display: grid;
		grid-template-columns: 28px 1fr auto;
		align-items: center;
		gap: 0.55rem;
		padding: 0.5rem 0.45rem;
		border-bottom: 1px solid var(--stone-5);
		border-left: 2px solid transparent;
		transition: background 140ms ease;
	}

	.member:hover {
		background: rgba(227, 188, 116, 0.04);
	}

	.member.is-me {
		border-left: 2px solid var(--gold-base);
		background: rgba(227, 188, 116, 0.05);
	}

	.member-meta {
		display: flex;
		flex-direction: column;
		gap: 1px;
		min-width: 0;
	}

	.member-name {
		font-family: var(--font-display);
		font-size: 0.78rem;
		color: var(--bone);
		letter-spacing: var(--track-loose);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.member-name.is-me-name {
		color: var(--bone-bright);
	}

	.member-addr {
		font-family: var(--font-mono);
		font-size: 0.65rem;
		color: var(--bone-dim);
		letter-spacing: 0.04em;
	}

	/* --- Main column --- */

	.main-inner {
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
		padding: 1.1rem 1.2rem 1.2rem;
		min-height: 0;
		flex: 1;
	}

	.room-head {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
		position: relative;
	}

	.head-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
	}

	.top-row {
		font-size: 0.72rem;
	}

	.back {
		font-family: var(--font-display);
		color: var(--gold-base);
		text-decoration: none;
		letter-spacing: var(--track-loose);
		font-size: 0.72rem;
		padding: 0.15rem 0;
		transition: color 140ms ease;
	}
	.back:hover {
		color: var(--gold-lit);
	}

	.shard {
		display: inline-flex;
		align-items: baseline;
		gap: 0.5rem;
		color: var(--bone-dim);
	}

	.shard-label {
		font-family: var(--font-display);
		font-size: 0.65rem;
		color: var(--bone-dim);
		letter-spacing: var(--track-loose);
	}

	.shard-hash {
		font-family: var(--font-mono);
		font-size: 0.72rem;
		color: var(--bone-muted);
		letter-spacing: 0.05em;
	}

	.title-row {
		align-items: baseline;
	}

	.room-title {
		margin: 0;
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 1.65rem;
		letter-spacing: var(--track-loose);
		line-height: 1.05;
	}

	.game {
		font-family: var(--font-display);
		font-size: 0.72rem;
		color: var(--gold-base);
		letter-spacing: var(--track-loose);
		display: inline-flex;
		gap: 0.35rem;
		align-items: baseline;
	}
	.game .dot {
		color: var(--gold-muted);
		opacity: 0.6;
	}

	.head-rule {
		display: block;
		height: 1px;
		width: 100%;
		background: var(--hair-gold);
		margin-top: 0.15rem;
	}

	/* --- Metadata --- */

	.meta-list {
		margin: 0.5rem 0 0;
		padding: 0;
		display: grid;
		gap: 0.45rem;
	}

	.meta-item {
		display: grid;
		grid-template-columns: 130px 1fr;
		gap: 0.75rem;
		align-items: baseline;
	}

	.meta-item dt {
		margin: 0;
		font-family: var(--font-display);
		font-size: 0.65rem;
		color: var(--bone-dim);
		letter-spacing: var(--track-loose);
	}

	.meta-item dd {
		margin: 0;
		font-family: var(--font-display);
		font-size: 0.82rem;
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

	@media (max-width: 760px) {
		.meta-item {
			grid-template-columns: 1fr;
			gap: 0.15rem;
		}
	}

	/* --- Event slot --- */

	.event-slot {
		display: flex;
		flex-direction: column;
	}

	/* --- Chat scroll area --- */

	.chat-wrap {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		flex: 1;
		min-height: 0;
	}

	.chat {
		position: relative;
		flex: 1;
		/* `min-height: 0` lets this flex child shrink below its content size so
		   `overflow-y` engages. The room-page grid gives the column a definite
		   height, so the chat takes the leftover space and scrolls — the message
		   log no longer stretches the page without bound. */
		min-height: 160px;
		overflow-y: auto;
		padding: 1rem 1.05rem;
		background: linear-gradient(180deg, var(--stone-2) 0%, var(--stone-1) 100%);
	}

	.chat-noise {
		position: absolute;
		inset: 0;
		pointer-events: none;
		background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='1.1' numOctaves='1' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.35 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
		background-size: 160px 160px;
		opacity: 0.12;
		mix-blend-mode: overlay;
		z-index: 0;
	}

	.empty {
		position: relative;
		z-index: 1;
		height: 100%;
		min-height: 200px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.6rem;
		color: var(--bone-muted);
	}
	.empty p {
		margin: 0;
		font-family: var(--font-display);
		font-style: italic;
		font-size: 0.95rem;
		letter-spacing: 0.02em;
	}

	.msg-list {
		position: relative;
		z-index: 1;
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.msg-row {
		padding: 0.45rem 0;
		border-bottom: 1px solid var(--stone-5);
	}
	.msg-row:last-child {
		border-bottom: 0;
	}

	.msg {
		padding: 0.4rem 0.7rem;
		background: transparent;
		border-radius: 0;
		max-width: 100%;
		transition:
			background 160ms ease,
			box-shadow 160ms ease;
	}

	.msg.other {
		border-left: 2px solid var(--gold-muted);
	}

	.msg.mine {
		border-right: 2px solid var(--gold-base);
		background: var(--gold-faint);
		text-align: right;
	}
	.msg.mine:hover {
		background: rgba(227, 188, 116, 0.22);
	}

	.msg-meta {
		display: inline-flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.4rem;
		font-size: 0.65rem;
		line-height: 1.2;
		margin-bottom: 0.2rem;
	}

	.msg.mine .msg-meta {
		justify-content: flex-end;
		width: 100%;
	}

	.sender {
		font-family: var(--font-display);
		color: var(--bone-bright);
		font-size: 0.72rem;
		letter-spacing: var(--track-loose);
	}

	.sep {
		color: var(--bone-dim);
		opacity: 0.6;
	}

	.addr,
	.time {
		font-family: var(--font-mono);
		color: var(--bone-dim);
		font-size: 0.65rem;
		letter-spacing: 0.04em;
	}

	.content {
		font-family: var(--font-display);
		color: var(--bone);
		font-size: 0.92rem;
		line-height: 1.45;
		word-wrap: break-word;
		white-space: pre-wrap;
		font-weight: 400;
	}

	.msg.mine .content {
		color: var(--bone-bright);
	}

	/* --- Composer --- */

	.composer {
		display: flex;
		gap: 0.6rem;
		align-items: stretch;
		position: sticky;
		bottom: 0;
	}

	.msg-input {
		flex: 1;
		padding: 0.65rem 0.85rem;
		font-family: var(--font-display);
		font-size: 0.92rem;
		color: var(--bone-bright);
		border-radius: 0;
		outline: none;
		letter-spacing: 0.02em;
		transition:
			border-color 140ms ease,
			box-shadow 140ms ease;
	}

	.msg-input::placeholder {
		color: var(--bone-dim);
		font-style: italic;
		letter-spacing: 0.02em;
	}

	.msg-input:focus {
		border-color: var(--gold-muted);
		box-shadow:
			var(--bevel-in),
			0 0 0 1px var(--gold-muted),
			0 0 14px rgba(227, 188, 116, 0.18);
	}

	@media (max-width: 760px) {
		.room-page {
			grid-template-columns: 1fr;
		}
		.rail {
			max-height: 200px;
		}
	}

	.closed-text {
		margin: 0 0 0.6rem 0;
		font-family: var(--font-display);
		font-size: 1rem;
		color: var(--bone-bright);
		letter-spacing: 0.02em;
		line-height: 1.5;
	}

	.closed-sub {
		margin: 0;
		font-family: var(--font-mono);
		font-size: 0.82rem;
		color: var(--bone-muted);
		letter-spacing: 0.03em;
	}
</style>
