// Minimal AG-UI client: POST a run to the Python agent and yield parsed events.
//
// The agent (backend/agui_agent) streams Server-Sent Events whose `data:` lines
// are AG-UI event JSON: RUN_STARTED, TEXT_MESSAGE_START/CONTENT/END,
// TOOL_CALL_START/ARGS/END/RESULT, RUN_FINISHED, RUN_ERROR.

export interface AGUIEvent {
  type: string;
  // common fields (camelCase, as emitted by the AG-UI EventEncoder)
  messageId?: string;
  delta?: string;
  toolCallId?: string;
  toolCallName?: string;
  content?: string;
  message?: string;
  [k: string]: unknown;
}

export interface AGUIMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export interface RunInput {
  url: string;
  threadId: string;
  runId: string;
  messages: AGUIMessage[];
  signal?: AbortSignal;
}

/** POST a run and asynchronously yield each AG-UI event as it streams in. */
export async function* runAgent(input: RunInput): AsyncGenerator<AGUIEvent> {
  const payload = {
    threadId: input.threadId,
    runId: input.runId,
    state: {},
    messages: input.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
    })),
    tools: [],
    context: [],
    forwardedProps: {},
  };

  const res = await fetch(input.url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(payload),
    signal: input.signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Agent responded ${res.status} ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by a blank line.
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const dataLine = chunk
        .split("\n")
        .find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      const json = dataLine.slice(5).trim();
      if (!json) continue;
      try {
        yield JSON.parse(json) as AGUIEvent;
      } catch {
        /* ignore malformed keep-alive lines */
      }
    }
  }
}
