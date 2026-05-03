import React, { useEffect } from 'react';
import {
  FlatList,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '@/constants/colors';

const SUPERMARKET_COLORS: Record<string, string> = colors.supermarket;
import { formatPrice, supermarketLabel } from '@/utils/formatPrice';
import { useShoppingList } from '@/store/shoppingList';
import type { MarketResult } from '@/types/compare';

interface SupermarketSection {
  supermarket: string;
  items: MarketResult[];
  total: number;
}

function buildSections(items: MarketResult[]): SupermarketSection[] {
  const map: Record<string, MarketResult[]> = {};
  for (const item of items) {
    if (!map[item.supermarket]) map[item.supermarket] = [];
    map[item.supermarket].push(item);
  }
  return Object.entries(map).map(([supermarket, sItems]) => ({
    supermarket,
    items: sItems,
    total: sItems.reduce((sum, i) => sum + i.price, 0),
  }));
}

function cheapestSupermarket(sections: SupermarketSection[]): string | null {
  if (sections.length === 0) return null;
  return sections.reduce((best, s) => (s.total < best.total ? s : best))
    .supermarket;
}

interface ItemRowProps {
  item: MarketResult;
  onRemove: () => void;
}

function ItemRow({ item, onRemove }: ItemRowProps) {
  return (
    <View style={styles.itemRow}>
      <View style={styles.itemInfo}>
        <Text style={styles.itemName} numberOfLines={2}>
          {item.product_name}
        </Text>
        {item.price_per_unit && (
          <Text style={styles.itemUnit}>{item.price_per_unit}</Text>
        )}
      </View>
      <Text style={styles.itemPrice}>{formatPrice(item.price)}</Text>
      <TouchableOpacity onPress={onRemove} style={styles.removeBtn} hitSlop={8}>
        <Ionicons name="trash-outline" size={18} color={colors.textMuted} />
      </TouchableOpacity>
    </View>
  );
}

interface GroupCardProps {
  section: SupermarketSection;
  isCheapest: boolean;
  onRemove: (url: string) => void;
}

function GroupCard({ section, isCheapest, onRemove }: GroupCardProps) {
  const dotColor = SUPERMARKET_COLORS[section.supermarket] ?? colors.primary;
  return (
    <View style={[styles.groupCard, isCheapest && styles.cheapestGroup]}>
      <View style={styles.groupHeader}>
        <View style={[styles.dot, { backgroundColor: dotColor }]} />
        <Text style={styles.groupTitle}>
          {supermarketLabel(section.supermarket)}
        </Text>
        {isCheapest && (
          <View style={styles.cheapestBadge}>
            <Ionicons name="trophy" size={10} color={colors.cheapest} />
            <Text style={styles.cheapestBadgeText}>Más barato</Text>
          </View>
        )}
      </View>
      {section.items.map((item) => (
        <ItemRow key={item.url} item={item} onRemove={() => onRemove(item.url)} />
      ))}
      <View style={styles.groupFooter}>
        <Text style={styles.groupTotalLabel}>Total</Text>
        <Text style={[styles.groupTotal, isCheapest && styles.cheapestTotal]}>
          {formatPrice(section.total)}
        </Text>
      </View>
    </View>
  );
}

export default function ListaScreen() {
  const { items, hydrated, hydrate, removeItem, clearList } = useShoppingList();

  useEffect(() => {
    if (!hydrated) hydrate();
  }, [hydrated, hydrate]);

  const sections = buildSections(items);
  const cheapest = cheapestSupermarket(sections);

  if (!hydrated) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <StatusBar style="dark" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <StatusBar style="dark" />
      <View style={styles.header}>
        <Text style={styles.title}>Lista de la compra</Text>
        {items.length > 0 && (
          <TouchableOpacity onPress={clearList} hitSlop={8}>
            <Text style={styles.clearBtn}>Vaciar</Text>
          </TouchableOpacity>
        )}
      </View>

      {items.length === 0 ? (
        <View style={styles.empty}>
          <Ionicons name="cart-outline" size={56} color={colors.textMuted} />
          <Text style={styles.emptyTitle}>Tu lista está vacía</Text>
          <Text style={styles.emptySubtitle}>
            Pulsa + en cualquier producto para añadirlo.
          </Text>
        </View>
      ) : (
        <FlatList
          data={sections}
          keyExtractor={(s) => s.supermarket}
          renderItem={({ item: section }) => (
            <GroupCard
              section={section}
              isCheapest={section.supermarket === cheapest}
              onRemove={removeItem}
            />
          )}
          contentContainerStyle={styles.list}
          ListHeaderComponent={
            sections.length > 1 && cheapest ? (
              <View style={styles.summaryBanner}>
                <Ionicons name="trending-down" size={14} color={colors.primary} />
                <Text style={styles.summaryText}>
                  Más barato en{' '}
                  <Text style={styles.summaryHighlight}>
                    {supermarketLabel(cheapest)}
                  </Text>
                </Text>
              </View>
            ) : null
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.cardBg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 8,
    backgroundColor: colors.cardBg,
  },
  title: {
    fontSize: 26,
    fontWeight: '800',
    color: colors.primary,
    letterSpacing: -0.5,
  },
  clearBtn: {
    fontSize: 14,
    color: colors.error,
    fontWeight: '600',
  },
  list: {
    padding: 16,
    gap: 12,
    paddingBottom: 40,
    backgroundColor: colors.background,
  },
  summaryBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#EFF6FF',
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 14,
    marginBottom: 4,
  },
  summaryText: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  summaryHighlight: {
    fontWeight: '700',
    color: colors.primary,
  },
  groupCard: {
    backgroundColor: colors.cardBg,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 2,
  },
  cheapestGroup: {
    borderColor: colors.cheapest,
    backgroundColor: colors.cheapestBg,
  },
  groupHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 12,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  groupTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    flex: 1,
  },
  cheapestBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  cheapestBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.cheapest,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  itemInfo: {
    flex: 1,
  },
  itemName: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.textPrimary,
    lineHeight: 18,
  },
  itemUnit: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: 2,
  },
  itemPrice: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textPrimary,
    flexShrink: 0,
  },
  removeBtn: {
    padding: 4,
    flexShrink: 0,
  },
  groupFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  groupTotalLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  groupTotal: {
    fontSize: 20,
    fontWeight: '800',
    color: colors.textPrimary,
  },
  cheapestTotal: {
    color: colors.cheapest,
  },
  empty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    paddingHorizontal: 40,
    backgroundColor: colors.background,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  emptySubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
  },
});
