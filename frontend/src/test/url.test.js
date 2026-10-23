import { describe, it, expect } from 'vitest';
import { normalizeApiBaseUrl } from '../utils/url';

describe('normalizeApiBaseUrl', () => {
  it('去掉末尾斜杠', () => {
    expect(normalizeApiBaseUrl('http://192.168.1.10:21345/')).toBe(
      'http://192.168.1.10:21345',
    );
  });

  it('去掉多个末尾斜杠和空白', () => {
    expect(normalizeApiBaseUrl('  https://fund.example.com///  ')).toBe(
      'https://fund.example.com',
    );
  });

  it('空值返回空字符串', () => {
    expect(normalizeApiBaseUrl('')).toBe('');
    expect(normalizeApiBaseUrl(null)).toBe('');
    expect(normalizeApiBaseUrl(undefined)).toBe('');
  });
});
