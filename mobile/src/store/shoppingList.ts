import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import type { MarketResult } from '@/types/compare';

const STORAGE_KEY = 'precioya_shopping_list';

interface ShoppingListStore {
  items: MarketResult[];
  hydrated: boolean;
  hydrate: () => Promise<void>;
  addItem: (item: MarketResult) => void;
  removeItem: (url: string) => void;
  clearList: () => void;
}

export const useShoppingList = create<ShoppingListStore>((set, get) => ({
  items: [],
  hydrated: false,

  hydrate: async () => {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY);
      if (raw) {
        set({ items: JSON.parse(raw), hydrated: true });
      } else {
        set({ hydrated: true });
      }
    } catch {
      set({ hydrated: true });
    }
  },

  addItem: (item) => {
    const current = get().items;
    if (current.some((i) => i.url === item.url)) return;
    const next = [...current, item];
    set({ items: next });
    AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next)).catch(() => {});
  },

  removeItem: (url) => {
    const next = get().items.filter((i) => i.url !== url);
    set({ items: next });
    AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next)).catch(() => {});
  },

  clearList: () => {
    set({ items: [] });
    AsyncStorage.removeItem(STORAGE_KEY).catch(() => {});
  },
}));
