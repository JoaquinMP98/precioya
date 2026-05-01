import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '@/constants/colors';
import { lookupBarcode } from '@/services/openFoodFacts';

interface Props {
  visible: boolean;
  onScanned: (productName: string) => void;
  onClose: () => void;
}

type ScanState = 'scanning' | 'looking_up' | 'not_found';

export function BarcodeScanner({ visible, onScanned, onClose }: Props) {
  const [permission, requestPermission] = useCameraPermissions();
  const [scanState, setScanState] = useState<ScanState>('scanning');
  const processingRef = useRef(false);

  // Reset state each time the modal opens
  useEffect(() => {
    if (visible) {
      setScanState('scanning');
      processingRef.current = false;
    }
  }, [visible]);

  const handleBarcodeScanned = useCallback(
    async ({ data: barcode }: { data: string }) => {
      if (processingRef.current) return;
      processingRef.current = true;
      setScanState('looking_up');

      const name = await lookupBarcode(barcode);
      if (name) {
        onScanned(name);
      } else {
        setScanState('not_found');
        // Let the user retry after a moment
        setTimeout(() => {
          setScanState('scanning');
          processingRef.current = false;
        }, 2000);
      }
    },
    [onScanned],
  );

  const handleRequestPermission = useCallback(async () => {
    await requestPermission();
  }, [requestPermission]);

  const renderBody = () => {
    if (!permission) {
      // Permission state loading
      return <ActivityIndicator color="#fff" size="large" />;
    }

    if (!permission.granted) {
      return (
        <View style={styles.centeredBox}>
          <Ionicons name="camera-outline" size={56} color="#fff" />
          <Text style={styles.permissionTitle}>Acceso a la cámara</Text>
          <Text style={styles.permissionBody}>
            Necesitamos permiso para escanear códigos de barras.
          </Text>
          <TouchableOpacity
            style={styles.permissionBtn}
            onPress={handleRequestPermission}
          >
            <Text style={styles.permissionBtnText}>Dar permiso</Text>
          </TouchableOpacity>
        </View>
      );
    }

    return (
      <>
        <CameraView
          style={StyleSheet.absoluteFill}
          facing="back"
          barcodeScannerSettings={{
            barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e', 'code128'],
          }}
          onBarcodeScanned={
            scanState === 'scanning' ? handleBarcodeScanned : undefined
          }
        />

        {/* Viewfinder overlay */}
        <View style={styles.overlay}>
          <View style={styles.topDim} />
          <View style={styles.middleRow}>
            <View style={styles.sideDim} />
            <View style={styles.viewfinder}>
              <View style={[styles.corner, styles.cornerTL]} />
              <View style={[styles.corner, styles.cornerTR]} />
              <View style={[styles.corner, styles.cornerBL]} />
              <View style={[styles.corner, styles.cornerBR]} />
            </View>
            <View style={styles.sideDim} />
          </View>
          <View style={styles.bottomDim}>
            {scanState === 'looking_up' && (
              <View style={styles.statusRow}>
                <ActivityIndicator color="#fff" size="small" />
                <Text style={styles.statusText}>Buscando producto…</Text>
              </View>
            )}
            {scanState === 'not_found' && (
              <View style={styles.statusRow}>
                <Ionicons name="warning-outline" size={18} color="#FCD34D" />
                <Text style={[styles.statusText, { color: '#FCD34D' }]}>
                  Código no encontrado. Inténtalo de nuevo.
                </Text>
              </View>
            )}
            {scanState === 'scanning' && (
              <Text style={styles.hint}>
                Apunta al código de barras del producto
              </Text>
            )}
          </View>
        </View>
      </>
    );
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="fullScreen"
      onRequestClose={onClose}
    >
      <View style={styles.container}>
        {renderBody()}

        <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
          <Ionicons name="close" size={28} color="#fff" />
        </TouchableOpacity>
      </View>
    </Modal>
  );
}

const DIM = 'rgba(0,0,0,0.6)';
const VF_SIZE = 240;
const CORNER = 20;
const CORNER_WIDTH = 3;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  centeredBox: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 40,
    gap: 16,
  },
  permissionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#fff',
    textAlign: 'center',
  },
  permissionBody: {
    fontSize: 15,
    color: 'rgba(255,255,255,0.7)',
    textAlign: 'center',
    lineHeight: 22,
  },
  permissionBtn: {
    marginTop: 8,
    backgroundColor: colors.primary,
    paddingHorizontal: 28,
    paddingVertical: 12,
    borderRadius: 10,
  },
  permissionBtnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 16,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    flexDirection: 'column',
  },
  topDim: {
    flex: 1,
    backgroundColor: DIM,
  },
  middleRow: {
    height: VF_SIZE,
    flexDirection: 'row',
  },
  sideDim: {
    flex: 1,
    backgroundColor: DIM,
  },
  viewfinder: {
    width: VF_SIZE,
    height: VF_SIZE,
  },
  corner: {
    position: 'absolute',
    width: CORNER,
    height: CORNER,
    borderColor: '#fff',
  },
  cornerTL: {
    top: 0,
    left: 0,
    borderTopWidth: CORNER_WIDTH,
    borderLeftWidth: CORNER_WIDTH,
  },
  cornerTR: {
    top: 0,
    right: 0,
    borderTopWidth: CORNER_WIDTH,
    borderRightWidth: CORNER_WIDTH,
  },
  cornerBL: {
    bottom: 0,
    left: 0,
    borderBottomWidth: CORNER_WIDTH,
    borderLeftWidth: CORNER_WIDTH,
  },
  cornerBR: {
    bottom: 0,
    right: 0,
    borderBottomWidth: CORNER_WIDTH,
    borderRightWidth: CORNER_WIDTH,
  },
  bottomDim: {
    flex: 1,
    backgroundColor: DIM,
    alignItems: 'center',
    justifyContent: 'flex-start',
    paddingTop: 24,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  statusText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '500',
  },
  hint: {
    color: 'rgba(255,255,255,0.7)',
    fontSize: 14,
    textAlign: 'center',
    paddingHorizontal: 24,
  },
  closeBtn: {
    position: 'absolute',
    top: 56,
    right: 20,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(0,0,0,0.5)',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
