import axios from 'axios';
import type { CompareResponse } from '@/types/compare';

// Use your machine's LAN IP when testing on a physical device,
// or 10.0.2.2 for Android emulator, or localhost for iOS simulator.
const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

const client = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 15_000,
});

export async function compareProducts(query: string): Promise<CompareResponse> {
  const { data } = await client.get<CompareResponse>('/compare', {
    params: { q: query },
  });
  return data;
}
