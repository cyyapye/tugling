import { JobStore } from "./jobStore";

export type Message = { eventId: string; jobId: string };
export type Processor = { run(message: Message): Promise<void> };

export async function handleMessage(
  message: Message,
  store: JobStore,
  processor: Processor,
): Promise<"processed" | "leased"> {
  if (!store.tryAcquire(message.jobId)) return "leased";
  await processor.run(message);
  store.complete(message.jobId);
  return "processed";
}
