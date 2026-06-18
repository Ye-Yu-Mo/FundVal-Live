/**
 * 测试 M4 前端: danjuan 数据源支持
 */

import { describe, it, expect } from 'vitest';

describe('fundsAPI.fundDetail', () => {
  it('exports fundDetail method', async () => {
    const { fundsAPI } = await import('../api/index');
    expect(fundsAPI.fundDetail).toBeDefined();
    expect(typeof fundsAPI.fundDetail).toBe('function');
  });
});
