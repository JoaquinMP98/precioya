const BASE = 'https://world.openfoodfacts.org/api/v0/product';

export async function lookupBarcode(barcode: string): Promise<string | null> {
  try {
    const res = await fetch(`${BASE}/${barcode}.json`, {
      headers: { 'User-Agent': 'PrecioYa/1.0 (contact@precioya.app)' },
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (data.status !== 1 || !data.product) return null;
    const p = data.product;
    return (
      p.product_name_es ||
      p.product_name ||
      p.generic_name_es ||
      p.generic_name ||
      null
    );
  } catch {
    return null;
  }
}
