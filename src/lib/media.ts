import { getCollection, type CollectionEntry } from 'astro:content';
import { withBase } from './url';

export type Kind = 'music' | 'films' | 'books';

export interface CardModel {
  kind: Kind;
  kindLabel: string;
  href: string;
  transitionName: string;
  title: string;
  creator: string;
  year?: number;
  cover: string;
  rating?: number;
  date: Date;
  aspect: 'square' | 'poster';
}

export const KIND_LABEL: Record<Kind, string> = {
  music: '음악',
  films: '영화',
  books: '책',
};

const FALLBACK_COVER: Record<Kind, string> = {
  music: '/covers/placeholder-music.svg',
  films: '/covers/placeholder-film.svg',
  books: '/covers/placeholder-book.svg',
};

function creatorOf(kind: Kind, data: Record<string, unknown>): string {
  if (kind === 'music') return String(data.artist ?? '');
  if (kind === 'films') return String(data.director ?? '');
  return String(data.author ?? '');
}

export function toCard(kind: Kind, entry: CollectionEntry<Kind>): CardModel {
  const data = entry.data as Record<string, unknown> & {
    title: string;
    year?: number;
    cover?: string;
    rating?: number;
    date: Date;
  };
  return {
    kind,
    kindLabel: KIND_LABEL[kind],
    href: withBase(`/${kind}/${entry.id}/`),
    transitionName: `cover-${kind}-${entry.id}`,
    title: data.title,
    creator: creatorOf(kind, data),
    year: data.year,
    cover: withBase(data.cover ?? FALLBACK_COVER[kind]),
    rating: data.rating,
    date: data.date,
    aspect: kind === 'music' ? 'square' : 'poster',
  };
}

export async function getPublished(kind: Kind) {
  return getCollection(kind, ({ data }) => data.publish);
}

export async function getAllCards(): Promise<CardModel[]> {
  const kinds: Kind[] = ['music', 'films', 'books'];
  const nested = await Promise.all(
    kinds.map(async (kind) => (await getPublished(kind)).map((e) => toCard(kind, e))),
  );
  return nested.flat().sort((a, b) => b.date.getTime() - a.date.getTime());
}
