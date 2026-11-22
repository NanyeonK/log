import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';
const posts = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(), date: z.coerce.date(), category: z.string().min(1),
    publish: z.boolean().default(false), tags: z.array(z.string()).default([]),
    year: z.number().int().optional(), genre: z.union([z.string(), z.array(z.string())]).optional()
      .transform((g) => typeof g === 'string' ? [g] : (g ?? [])),
    cover: z.string().optional(), rating: z.number().min(0).max(10).optional(),
    artist: z.string().optional(), label: z.string().optional(), tracks: z.array(z.string()).optional(),
    director: z.string().optional(), cast: z.array(z.string()).optional(),
    author: z.string().optional(), publisher: z.string().optional(), pages: z.number().int().optional(),
  }),
});
export const collections = { posts };
