import { formatPrice, supermarketLabel } from '../utils/formatPrice';

describe('formatPrice', () => {
  it('formats euro amounts with Spanish locale', () => {
    const result = formatPrice(0.65);
    expect(result).toContain('0,65');
    expect(result).toContain('€');
  });

  it('formats two decimal places', () => {
    expect(formatPrice(1)).toContain('1,00');
  });
});

describe('supermarketLabel', () => {
  it('returns known labels', () => {
    expect(supermarketLabel('mercadona')).toBe('Mercadona');
    expect(supermarketLabel('lidl')).toBe('Lidl');
    expect(supermarketLabel('alcampo')).toBe('Alcampo');
    expect(supermarketLabel('supercor')).toBe('Supercor');
  });

  it('capitalises unknown slugs', () => {
    expect(supermarketLabel('dia')).toBe('Dia');
  });
});
