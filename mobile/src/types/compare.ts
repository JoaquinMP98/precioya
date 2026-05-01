export interface MarketResult {
  supermarket: string;
  product_name: string;
  price: number;
  price_per_unit: string | null;
  url: string;
  image_url: string | null;
}

export interface CompareResponse {
  query: string;
  cheapest: MarketResult | null;
  by_supermarket: MarketResult[];
  from_cache: boolean;
  warnings: string[];
}
