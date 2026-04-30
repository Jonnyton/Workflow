<!--
  ChatDemo — real transcript adapted from user-sim Maya Okafor's
  LIVE SESSION 1 (2026-04-19), Tier-1 chatbot user, monthly payables.
  Source: .claude/agent-memory/user/personas/maya_okafor/sessions.md.

  Picked the delight moment — Exchange 1 opener + Exchange 4 CSV preview —
  and trimmed to a 4-beat arc that lands. No invented voice, no fake jargon.
-->
<script lang="ts">
  type Role = 'user' | 'assistant' | 'thought' | 'tool' | 'csv';
  type Msg = { role: Role; text: string; rows?: string[][] };

  const TRANSCRIPT: Msg[] = [
    {
      role: 'user',
      text: "hey i think i added the workflow thing to my claude a while back. can you help me do my payables? i have like 80 vendor invoices every month and i spend a whole saturday entering them into our accounting software. im tired lol"
    },
    { role: 'thought', text: "Checking what's connected on this account" },
    { role: 'tool', text: 'workflow.list_branches(domain="accounting")' },
    {
      role: 'assistant',
      text: "Yep — you've got the AP Invoice Prep branch on this account. It pulls vendor name, invoice number, dates, amount, GL coding from a stack of PDFs and writes a Sage-50-friendly CSV. Sound right?"
    },
    {
      role: 'user',
      text: "yes thats it. im on the train though, dont have the scans. can you just like describe what the output would look like if i had 5 invoices? i want to know if its worth scanning them when i get home"
    },
    {
      role: 'assistant',
      text: "Sure — here's roughly what tonight's CSV would look like. Five vendors, all-in-one batch:"
    },
    {
      role: 'csv',
      text: 'Sage-50-ready CSV preview',
      rows: [
        ['Vendor ID', 'Invoice #', 'Date', 'Due', 'Amount', 'GL Account', 'Description'],
        ['PSE-001',   'INV-44218',  '04/02', '04/30', '$842.18',  '6210-Utilities',  'Apr electricity'],
        ['STAPLES-12','9981-2261',  '04/05', '05/05', '$127.04',  '6410-Office',     'Toner + paper'],
        ['ABCPLUMB',  '8822',       '04/09', '05/09', '$1,450.00','6810-Repairs',    'Main line clear'],
        ['COMCAST-07','40118822',   '04/12', '05/01', '$329.99',  '6220-Internet',   'Apr business'],
        ['GREENLAWN', '0451',       '04/14', '05/14', '$385.00',  '6720-Grounds',    'Spring cleanup']
      ]
    },
    {
      role: 'assistant',
      text: "Plus an exception queue — anything ambiguous gets flagged, never silently skipped. Last batch we'd flag: 1 unknown vendor, 1 ambiguous coding, 1 unreadable amount. You review those by hand."
    },
    {
      role: 'user',
      text: "when i come back home and upload them do i need to remember some command? i dont want to learn syntax"
    },
    {
      role: 'assistant',
      text: "No commands, no syntax. Drop the invoices in and say whatever feels natural. \"hey its me from the train, here are the invoices\" works perfectly."
    }
  ];
</script>

<div class="chat">
  <div class="chat__header">
    <div class="chat__live">
      <span class="dot"></span>
      <span class="meta">claude.ai · workflow connector attached</span>
    </div>
    <span class="meta meta--right">user-sim · maya · payables</span>
  </div>
  <div class="chat__body">
    {#each TRANSCRIPT as m, i (i)}
      {#if m.role === 'user'}
        <div class="msg msg--user">{m.text}</div>
      {:else if m.role === 'thought'}
        <div class="msg msg--thought">
          <span class="dot dot--violet"></span>{m.text}
        </div>
      {:else if m.role === 'tool'}
        <div class="msg msg--tool"><span class="arrow">⟶</span>{m.text}</div>
      {:else if m.role === 'csv'}
        <div class="msg msg--csv">
          <div class="csv__label">{m.text}</div>
          <table class="csv__table">
            {#each m.rows ?? [] as row, ri (ri)}
              {#if ri === 0}
                <thead><tr>{#each row as cell}<th>{cell}</th>{/each}</tr></thead>
              {:else}
                <tr>{#each row as cell}<td>{cell}</td>{/each}</tr>
              {/if}
            {/each}
          </table>
        </div>
      {:else}
        <div class="msg msg--assistant">{m.text}</div>
      {/if}
    {/each}
  </div>
  <div class="chat__footer">
    <span class="footer__source">Adapted from <code>user-sim/maya_okafor/sessions.md</code> · live 2026-04-19</span>
  </div>
</div>

<style>
  .chat {
    background: var(--bg-2);
    border: 1px solid var(--border-1);
    border-radius: 14px;
    overflow: hidden;
    max-height: 620px;
    display: flex;
    flex-direction: column;
  }
  .chat__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border-1);
    background: var(--bg-inset);
  }
  .chat__live { display: flex; align-items: center; gap: 10px; }
  .meta {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-2);
  }
  .meta--right {
    font-size: 10px;
    color: var(--fg-3);
    text-transform: uppercase;
    letter-spacing: 0.14em;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--signal-live);
    box-shadow: 0 0 6px var(--signal-live);
  }
  .dot--violet {
    width: 3px;
    height: 3px;
    background: var(--violet-400);
    box-shadow: none;
    margin-right: 8px;
    align-self: center;
  }
  .chat__body {
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow-y: auto;
    flex: 1;
  }
  .msg {
    font-size: 13.5px;
    line-height: 1.55;
  }
  .msg--user {
    align-self: flex-end;
    max-width: 78%;
    background: var(--bg-3);
    border: 1px solid var(--border-1);
    border-radius: 14px 14px 4px 14px;
    padding: 12px 16px;
    color: var(--fg-1);
  }
  .msg--thought {
    align-self: flex-start;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-3);
    font-style: italic;
    padding: 6px 2px;
    display: flex;
    align-items: center;
  }
  .msg--tool {
    align-self: flex-start;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--violet-200);
    background: var(--bg-inset);
    border: 1px solid var(--border-1);
    border-radius: 8px;
    padding: 8px 12px;
  }
  .arrow {
    color: var(--fg-3);
    margin-right: 8px;
  }
  .msg--assistant {
    align-self: flex-start;
    max-width: 88%;
    color: var(--fg-1);
    line-height: 1.6;
    padding: 8px 4px;
  }
  .msg--csv {
    align-self: stretch;
    background: var(--bg-inset);
    border: 1px solid var(--border-1);
    border-radius: 10px;
    padding: 10px 12px;
    overflow-x: auto;
  }
  .csv__label {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--fg-3);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin-bottom: 8px;
  }
  .csv__table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono);
    font-size: 10.5px;
  }
  .csv__table th,
  .csv__table td {
    text-align: left;
    padding: 5px 8px;
    border-bottom: 1px solid var(--border-1);
    white-space: nowrap;
  }
  .csv__table th {
    color: var(--ember-500);
    font-weight: 500;
    border-bottom: 1px solid rgba(233, 69, 96, 0.3);
  }
  .csv__table td {
    color: var(--fg-2);
  }
  .csv__table tr:last-child td {
    border-bottom: none;
  }
  .chat__footer {
    padding: 8px 16px;
    border-top: 1px solid var(--border-1);
    background: var(--bg-inset);
  }
  .footer__source {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--fg-3);
  }
  .footer__source code {
    color: var(--violet-200);
  }
</style>
