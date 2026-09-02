import { JobStore } from "../src/jobStore";

test("an isolated lease can be reclaimed after expiry", () => {
  let now = 0;
  const store = new JobStore({ nowSeconds: () => now }, 60);
  expect(store.tryAcquire("job-1")).toBe(true);
  expect(store.tryAcquire("job-1")).toBe(false);
  now = 61;
  expect(store.tryAcquire("job-1")).toBe(true);
});
