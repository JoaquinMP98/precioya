import React from 'react';
import { render, screen } from '@testing-library/react-native';
import { PriceCard } from '../components/PriceCard';
import type { MarketResult } from '../types/compare';

const baseResult: MarketResult = {
  supermarket: 'mercadona',
  product_name: 'Leche entera 1L',
  price: 0.65,
  price_per_unit: '0,65 €/L',
  url: 'https://tienda.mercadona.es/product/7543',
  image_url: null,
  best_unit_price: false,
  nutriscore: null,
  nova_group: null,
  best_nutriscore: false,
};

describe('PriceCard', () => {
  it('renders product name', () => {
    render(<PriceCard result={baseResult} isCheapest={false} />);
    expect(screen.getByText('Leche entera 1L')).toBeTruthy();
  });

  it('renders supermarket label', () => {
    render(<PriceCard result={baseResult} isCheapest={false} />);
    expect(screen.getByText('Mercadona')).toBeTruthy();
  });

  it('renders price per unit when provided', () => {
    render(<PriceCard result={baseResult} isCheapest={false} />);
    expect(screen.getByText('0,65 €/L')).toBeTruthy();
  });

  it('shows cheapest badge when isCheapest=true', () => {
    render(<PriceCard result={baseResult} isCheapest={true} />);
    expect(screen.getByText('Más barato')).toBeTruthy();
  });

  it('hides cheapest badge when isCheapest=false', () => {
    render(<PriceCard result={baseResult} isCheapest={false} />);
    expect(screen.queryByText('Más barato')).toBeNull();
  });

  it('does not render price_per_unit when null', () => {
    render(<PriceCard result={{ ...baseResult, price_per_unit: null }} isCheapest={false} />);
    expect(screen.queryByText('0,65 €/L')).toBeNull();
  });
});
