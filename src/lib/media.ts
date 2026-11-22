import { getCollection, type CollectionEntry } from 'astro:content';
import { withBase } from './url';
export interface CardModel {
  kindLabel: string; href: string; transitionName: string; title: string;
  creator: string; year?: number; cover: string; rating?: number; date: Date;
  aspect: 'square' | 'poster';
}
export const categorySlug = (category: string) => category.trim().toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '');
export const categoryLabel = (category: string) => ({ book: '책', film: '영화', music: '음악' } as Record<string, string>)[category.toLowerCase()] ?? category;
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
  const categories = [...new Set((await getPublished()).map((entry) => entry.data.category.trim()))];
  const slugs = categories.map(categorySlug);
  if (slugs.some((s) => !s) || new Set(slugs).size !== slugs.length) throw new Error('Category names must have distinct URL slugs');
  return categories.sort((a, b) => a.localeCompare(b));
}
