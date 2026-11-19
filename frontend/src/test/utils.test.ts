import { describe, it, expect } from 'vitest';
import { confidenceColor, formatDate, categoryColors, cn } from '../lib/utils';

describe('Frontend Utility Functions', () => {
  it('assigns appropriate confidence colors', () => {
    expect(confidenceColor(0.9)).toBe('text-emerald-400');
    expect(confidenceColor(0.6)).toBe('text-amber-400');
    expect(confidenceColor(0.3)).toBe('text-rose-400');
  });

  it('provides color definitions for known failure categories', () => {
    expect(categoryColors.CODE_DEFECT).toBeDefined();
    expect(categoryColors.FLAKY_TEST).toBeDefined();
    expect(categoryColors.DEPENDENCY).toBeDefined();
    expect(categoryColors.INFRASTRUCTURE).toBeDefined();
    expect(categoryColors.CONFIGURATION).toBeDefined();
    expect(categoryColors.UNKNOWN).toBeDefined();
  });

  it('merges tailwind classes cleanly', () => {
    const res = cn('px-2 py-1', 'bg-blue-600', 'px-4');
    expect(res).toContain('bg-blue-600');
    expect(res).toContain('px-4');
    expect(res).not.toContain('px-2');
  });

  it('formats dates consistently', () => {
    const formatted = formatDate('2024-01-15T10:00:00Z');
    expect(typeof formatted).toBe('string');
    expect(formatted.length).toBeGreaterThan(0);
  });
});
