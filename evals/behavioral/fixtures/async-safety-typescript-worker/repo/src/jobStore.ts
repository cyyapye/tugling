export type Clock = { nowSeconds(): number };

export class JobStore {
  private leases = new Map<string, number>();

  constructor(
    private readonly clock: Clock,
    private readonly leaseTtlSeconds: number,
  ) {}

  tryAcquire(jobId: string): boolean {
    const now = this.clock.nowSeconds();
    const expiresAt = this.leases.get(jobId);
    if (expiresAt !== undefined && expiresAt > now) return false;
    this.leases.set(jobId, now + this.leaseTtlSeconds);
    return true;
  }

  complete(jobId: string): void {
    this.leases.delete(jobId);
  }
}
