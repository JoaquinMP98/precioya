import { act, renderHook, waitFor } from '@testing-library/react-native';
import { useCompare } from '../hooks/useCompare';
import * as api from '../services/api';

jest.mock('../services/api');
const mockCompare = api.compareProducts as jest.MockedFunction<typeof api.compareProducts>;

const mockResponse = {
  query: 'leche',
  cheapest: {
    supermarket: 'lidl',
    product_name: 'Leche fresca 1L',
    price: 0.58,
    price_per_unit: '0,58 €/L',
    url: 'https://lidl.es/product/leche',
    image_url: null,
  },
  by_supermarket: [
    {
      supermarket: 'lidl',
      product_name: 'Leche fresca 1L',
      price: 0.58,
      price_per_unit: '0,58 €/L',
      url: 'https://lidl.es/product/leche',
      image_url: null,
    },
    {
      supermarket: 'mercadona',
      product_name: 'Leche entera 1L',
      price: 0.65,
      price_per_unit: '0,65 €/L',
      url: 'https://tienda.mercadona.es/product/7543',
      image_url: null,
    },
  ],
  from_cache: false,
  warnings: [],
};

describe('useCompare', () => {
  beforeEach(() => jest.clearAllMocks());

  it('starts with empty state', () => {
    const { result } = renderHook(() => useCompare());
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('sets loading=true while fetching', async () => {
    let resolve!: (v: typeof mockResponse) => void;
    mockCompare.mockReturnValue(new Promise((r) => { resolve = r; }));

    const { result } = renderHook(() => useCompare());
    act(() => { result.current.search('leche'); });

    expect(result.current.loading).toBe(true);
    act(() => { resolve(mockResponse); });
    await waitFor(() => expect(result.current.loading).toBe(false));
  });

  it('populates data on success', async () => {
    mockCompare.mockResolvedValue(mockResponse);
    const { result } = renderHook(() => useCompare());

    await act(async () => { await result.current.search('leche'); });

    expect(result.current.data).toEqual(mockResponse);
    expect(result.current.error).toBeNull();
  });

  it('sets error on API failure', async () => {
    mockCompare.mockRejectedValue(new Error('Network Error'));
    const { result } = renderHook(() => useCompare());

    await act(async () => { await result.current.search('leche'); });

    expect(result.current.error).toBe('Network Error');
    expect(result.current.data).toBeNull();
  });

  it('skips search when query is too short', async () => {
    const { result } = renderHook(() => useCompare());
    await act(async () => { await result.current.search('a'); });
    expect(mockCompare).not.toHaveBeenCalled();
  });

  it('reset clears all state', async () => {
    mockCompare.mockResolvedValue(mockResponse);
    const { result } = renderHook(() => useCompare());

    await act(async () => { await result.current.search('leche'); });
    expect(result.current.data).not.toBeNull();

    act(() => { result.current.reset(); });
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });
});
