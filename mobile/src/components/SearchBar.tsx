import React, { useRef } from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '@/constants/colors';

interface Props {
  value: string;
  onChangeText: (text: string) => void;
  onClear: () => void;
  loading: boolean;
  onScanPress: () => void;
}

export function SearchBar({ value, onChangeText, onClear, loading, onScanPress }: Props) {
  const inputRef = useRef<TextInput>(null);

  return (
    <View style={styles.container}>
      <View style={styles.inner}>
        {loading ? (
          <ActivityIndicator
            size="small"
            color={colors.primary}
            style={styles.icon}
          />
        ) : (
          <Ionicons
            name="search"
            size={20}
            color={colors.textMuted}
            style={styles.icon}
          />
        )}
        <TextInput
          ref={inputRef}
          style={styles.input}
          value={value}
          onChangeText={onChangeText}
          placeholder="Buscar producto…"
          placeholderTextColor={colors.textMuted}
          returnKeyType="search"
          autoCorrect={false}
          autoCapitalize="none"
          clearButtonMode="never"
        />
        {value.length > 0 && (
          <TouchableOpacity
            onPress={() => {
              onClear();
              inputRef.current?.focus();
            }}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Ionicons name="close-circle" size={18} color={colors.textMuted} />
          </TouchableOpacity>
        )}
        <TouchableOpacity
          onPress={onScanPress}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          style={styles.scanBtn}
        >
          <Ionicons name="barcode-outline" size={22} color={colors.primary} />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: colors.cardBg,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  inner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.background,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 12,
    height: 44,
  },
  icon: {
    marginRight: 8,
  },
  scanBtn: {
    marginLeft: 6,
  },
  input: {
    flex: 1,
    fontSize: 16,
    color: colors.textPrimary,
    paddingVertical: 0,
  },
});
