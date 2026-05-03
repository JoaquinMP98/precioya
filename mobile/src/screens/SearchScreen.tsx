import React, { useCallback, useRef, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  SectionList,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { SearchBar } from '@/components/SearchBar';
import { BarcodeScanner } from '@/components/BarcodeScanner';
import { PriceCard } from '@/components/PriceCard';
import { useCompare } from '@/hooks/useCompare';
import { colors } from '@/constants/colors';
import { supermarketLabel } from '@/utils/formatPrice';

const SUPERMARKET_COLORS: Record<string, string> = colors.supermarket;
import { useShoppingList } from '@/store/shoppingList';
import type { MarketResult, SupermarketGroup } from '@/types/compare';

const DEBOUNCE_MS = 500;

interface Section {
  supermarket: string;
  data: MarketResult[];
}

export default function SearchScreen() {
  const [query, setQuery] = useState('');
  const [scannerVisible, setScannerVisible] = useState(false);
  const { data, loading, error, search, reset } = useCompare();
  const { addItem } = useShoppingList();
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleChangeText = useCallback(
    (text: string) => {
      setQuery(text);
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      if (text.trim().length < 2) {
        reset();
        return;
      }
      debounceTimer.current = setTimeout(() => search(text), DEBOUNCE_MS);
    },
    [search, reset],
  );

  const handleClear = useCallback(() => {
    setQuery('');
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    reset();
  }, [reset]);

  const handleScanned = useCallback(
    (productName: string) => {
      setScannerVisible(false);
      setQuery(productName);
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      search(productName);
    },
    [search],
  );

  const cheapestUrl = data?.cheapest?.url ?? null;

  const sections: Section[] = (data?.by_supermarket ?? []).map(
    (group: SupermarketGroup) => ({
      supermarket: group.supermarket,
      data: group.products,
    }),
  );

  const totalProducts = sections.reduce((sum, s) => sum + s.data.length, 0);

  const renderItem = useCallback(
    ({ item }: { item: MarketResult }) => (
      <PriceCard
        result={item}
        isCheapest={item.url === cheapestUrl}
        onAdd={() => addItem(item)}
      />
    ),
    [cheapestUrl, addItem],
  );

  const renderSectionHeader = useCallback(
    ({ section }: { section: Section }) => (
      <View style={styles.sectionHeader}>
        <View
          style={[
            styles.sectionDot,
            {
              backgroundColor:
                SUPERMARKET_COLORS[section.supermarket] ?? colors.primary,
            },
          ]}
        />
        <Text style={styles.sectionTitle}>
          {supermarketLabel(section.supermarket)}
        </Text>
      </View>
    ),
    [],
  );

  const keyExtractor = useCallback(
    (item: MarketResult) => `${item.supermarket}-${item.url}`,
    [],
  );

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <StatusBar style="dark" />
      <BarcodeScanner
        visible={scannerVisible}
        onScanned={handleScanned}
        onClose={() => setScannerVisible(false)}
      />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.logo}>PrecioYa</Text>
          <Text style={styles.tagline}>Compara precios en supermercados</Text>
        </View>

        {/* Search bar */}
        <SearchBar
          value={query}
          onChangeText={handleChangeText}
          onClear={handleClear}
          loading={loading}
          onScanPress={() => setScannerVisible(true)}
        />

        {/* Results */}
        <SectionList
          sections={sections}
          renderItem={renderItem}
          renderSectionHeader={renderSectionHeader}
          keyExtractor={keyExtractor}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
          stickySectionHeadersEnabled={false}
          ListHeaderComponent={
            data && sections.length > 0 ? (
              <ResultHeader
                query={data.query}
                supermarketCount={sections.length}
                productCount={totalProducts}
                fromCache={data.from_cache}
                warnings={data.warnings}
              />
            ) : null
          }
          ListEmptyComponent={
            <EmptyState
              query={query}
              loading={loading}
              error={error}
              hasData={data !== null}
            />
          }
        />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ---- sub-components ----

interface ResultHeaderProps {
  query: string;
  supermarketCount: number;
  productCount: number;
  fromCache: boolean;
  warnings: string[];
}

function ResultHeader({
  query,
  supermarketCount,
  productCount,
  fromCache,
  warnings,
}: ResultHeaderProps) {
  return (
    <View style={styles.resultHeader}>
      <Text style={styles.resultTitle}>
        {productCount} producto{productCount !== 1 ? 's' : ''} en{' '}
        {supermarketCount} supermercado{supermarketCount !== 1 ? 's' : ''} para{' '}
        <Text style={styles.resultQuery}>"{query}"</Text>
      </Text>
      {fromCache && (
        <Text style={styles.cacheLabel}>· resultado guardado</Text>
      )}
      {warnings.map((w, i) => (
        <Text key={i} style={styles.warning}>
          ⚠ {w}
        </Text>
      ))}
    </View>
  );
}

interface EmptyStateProps {
  query: string;
  loading: boolean;
  error: string | null;
  hasData: boolean;
}

function EmptyState({ query, loading, error, hasData }: EmptyStateProps) {
  if (loading) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyIcon}>🔍</Text>
        <Text style={styles.emptyTitle}>Buscando en supermercados...</Text>
        <Text style={styles.emptySubtitle}>
          Esto puede tardar unos segundos.
        </Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyIcon}>⚠️</Text>
        <Text style={styles.emptyTitle}>Error al buscar</Text>
        <Text style={styles.emptySubtitle}>{error}</Text>
      </View>
    );
  }

  if (hasData) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyIcon}>🔍</Text>
        <Text style={styles.emptyTitle}>Sin resultados</Text>
        <Text style={styles.emptySubtitle}>
          Prueba con otro nombre de producto.
        </Text>
      </View>
    );
  }

  if (query.length > 0 && query.trim().length < 2) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptySubtitle}>Escribe al menos 2 caracteres</Text>
      </View>
    );
  }

  return (
    <View style={styles.emptyContainer}>
      <Text style={styles.emptyIcon}>🛒</Text>
      <Text style={styles.emptyTitle}>Busca cualquier producto</Text>
      <Text style={styles.emptySubtitle}>
        Leche, aceite, pan… te decimos dónde está más barato.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.cardBg,
  },
  flex: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 8,
    backgroundColor: colors.cardBg,
  },
  logo: {
    fontSize: 26,
    fontWeight: '800',
    color: colors.primary,
    letterSpacing: -0.5,
  },
  tagline: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  list: {
    paddingTop: 8,
    paddingBottom: 40,
    flexGrow: 1,
    backgroundColor: colors.background,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 6,
  },
  sectionDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  resultHeader: {
    paddingHorizontal: 16,
    paddingBottom: 4,
    paddingTop: 8,
  },
  resultTitle: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  resultQuery: {
    fontWeight: '600',
    color: colors.textPrimary,
  },
  cacheLabel: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: 2,
  },
  warning: {
    fontSize: 12,
    color: colors.warning,
    marginTop: 4,
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 40,
    paddingTop: 80,
    gap: 8,
  },
  emptyIcon: {
    fontSize: 44,
    marginBottom: 8,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
    textAlign: 'center',
  },
  emptySubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
  },
});
