import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

/** 공통 frontmatter — 세 컬렉션이 공유하는 필드 */
const common = {
  title: z.string(),
  year: z.number().int().optional(),
  genre: z
    .union([z.string(), z.array(z.string())])
    .optional()
    .transform((g) => (typeof g === 'string' ? [g] : (g ?? []))),
  cover: z.string().optional(),
  rating: z.number().min(0).max(10).optional(),
  /** 감상일 (정렬 기준) */
  date: z.coerce.date(),
  publish: z.boolean().default(true),
};

const music = defineCollection({
  loader: glob({ pattern: ['**/*.md', '!_*'], base: './src/content/music' }),
  schema: z.object({
    type: z.literal('music').default('music'),
    artist: z.string(),
    label: z.string().optional(),
    tracks: z.array(z.string()).optional(),
    ...common,
  }),
});

const films = defineCollection({
  loader: glob({ pattern: ['**/*.md', '!_*'], base: './src/content/films' }),
  schema: z.object({
    type: z.literal('film').default('film'),
    director: z.string(),
    cast: z.array(z.string()).optional(),
    ...common,
  }),
});

const books = defineCollection({
  loader: glob({ pattern: ['**/*.md', '!_*'], base: './src/content/books' }),
  schema: z.object({
    type: z.literal('book').default('book'),
    author: z.string(),
    publisher: z.string().optional(),
    pages: z.number().int().optional(),
    ...common,
  }),
});

export const collections = { music, films, books };
