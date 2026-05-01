import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '@/constants/colors';
import { formatPrice, supermarketLabel } from '@/utils/formatPrice';
import type { MarketResult } from '@/types/compare';

interface Props {
  result: MarketResult;
  isCheapest: boolean;
}

const SUPERMARKET_COLORS: Record<string, string> = colors.supermarket;

function SupermarketDot({ slug }: { slug: string }) {
  const dotColor = SUPERMARKET_COLORS[slug] ?? colors.primary;
  return <View style={[styles.dot, { backgroundColor: dotColor }]} />;
}

export function PriceCard({ result, isCheapest }: Props) {
  return (
    <View style={[styles.card, isCheapest && styles.cheapestCard]}>
      {isCheapest && (
        <View style={styles.cheapestBadge}>
          <Ionicons name="trophy" size={11} color={colors.cheapest} />
          <Text style={styles.cheapestBadgeText}>Más barato</Text>
        </View>
      )}

      <View style={styles.row}>
        <View style={styles.left}>
          <View style={styles.supermarketRow}>
            <SupermarketDot slug={result.supermarket} />
            <Text style={styles.supermarket}>
              {supermarketLabel(result.supermarket)}
            </Text>
          </View>
          <Text style={styles.name} numberOfLines={2}>
            {result.product_name}
          </Text>
          {result.price_per_unit != null && (
            <Text style={styles.pricePerUnit}>{result.price_per_unit}</Text>
          )}
        </View>

        <View style={styles.priceBox}>
          <Text style={[styles.price, isCheapest && styles.cheapestPrice]}>
            {formatPrice(result.price)}
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.cardBg,
    borderRadius: 14,
    marginHorizontal: 16,
    marginVertical: 6,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 2,
  },
  cheapestCard: {
    borderColor: colors.cheapest,
    backgroundColor: colors.cheapestBg,
  },
  cheapestBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 8,
  },
  cheapestBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.cheapest,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  left: {
    flex: 1,
  },
  supermarketRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  supermarket: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  name: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.textPrimary,
    lineHeight: 20,
  },
  pricePerUnit: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: 4,
  },
  priceBox: {
    alignItems: 'flex-end',
    flexShrink: 0,
  },
  price: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  cheapestPrice: {
    color: colors.cheapest,
  },
});
