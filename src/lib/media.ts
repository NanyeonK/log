import { getCollection, type CollectionEntry } from 'astro:content';
import { withBase } from './url';
import { createHash } from 'node:crypto';
export interface CardModel {
  kindLabel: string; href: string; transitionName: string; title: string;
  creator: string; year?: number; cover: string; rating?: number; date: Date;
  aspect: 'square' | 'poster';
}
const baseSlug = (category: string) => {
  const slug = category.normalize('NFKC').trim().toLowerCase().replace(/[^\p{L}\p{M}\p{N}._~-]+/gu, '-').replace(/^-|-$/g, '');
  return !slug || slug === '.' || slug === '..' ? 'category' : slug;
};
export function categorySlugs(categories: string[]): Map<string, string> {
  const result = new Map(categories.map((category) => {
    const base = baseSlug(category);
    const suffix = base !== category || /-[0-9a-f]{12}$/.test(category) ? `-${createHash('sha256').update(category).digest('hex').slice(0, 12)}` : '';
    return [category, base + suffix];
  }));
  if (new Set(result.values()).size !== result.size) throw new Error('Category URL slug collision');
  return result;
}
const categoryLabels = new Map([['book', '책'], ['film', '영화'], ['music', '음악']]);
export const categoryLabel = (category: string) => categoryLabels.get(category.toLowerCase()) ?? category;
export async function getPublished() { return getCollection('posts', ({ data }) => data.publish); }
export function toCard(entry: CollectionEntry<'posts'>): CardModel {
  const d = entry.data;
  const kind = d.category.toLowerCase();
  const fallback = kind === 'music' ? 'music' : kind === 'film' ? 'film' : 'book';
  return { kindLabel: categoryLabel(d.category), href: withBase(`/posts/${entry.id}/`),
    transitionName: `cover-${entry.id}`, title: d.title,
    creator: d.author ?? d.director ?? d.artist ?? '', year: d.year,
    cover: withBase(d.cover ?? `/covers/placeholder-${fallback}.svg`), rating: d.rating,
    date: d.date, aspect: kind === 'music' ? 'square' : 'poster' };
}
export async function getAllCards() {
  return (await getPublished()).map(toCard).sort((a, b) => b.date.getTime() - a.date.getTime());
}
export async function getCategories() {
  const categories = [...new Set((await getPublished()).map((entry) => entry.data.category))];
  categorySlugs(categories);
  return categories.sort((a, b) => a.localeCompare(b));
}
