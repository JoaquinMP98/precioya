export function formatPrice(price: number): string {
  return price.toLocaleString('es-ES', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
  });
}

export function supermarketLabel(slug: string): string {
  const labels: Record<string, string> = {
    mercadona: 'Mercadona',
    lidl: 'Lidl',
    alcampo: 'Alcampo',
    supercor: 'Supercor',
    carrefour: 'Carrefour',
    dia: 'DIA',
    aldi: 'Aldi',
  };
  return labels[slug] ?? slug.charAt(0).toUpperCase() + slug.slice(1);
}
