import { handleMessage } from "../src/worker";

test("routes a processor failure back to the queue", async () => {
  const store = { tryAcquire: () => true, complete: () => undefined } as never;
  const processor = { run: async () => { throw new Error("crash"); } };
  await expect(handleMessage({ eventId: "evt-1", jobId: "job-1" }, store, processor)).rejects.toThrow("crash");
});
