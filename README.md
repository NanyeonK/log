# Record blog

The site uses one `posts` content collection. Each published Markdown file has
`title`, `date`, `category`, `tags`, and `publish: true` front matter. Category
names are free text; category pages and navigation are generated from the posts.
Optional book, film and music fields include `author`, `director`, `artist`,
`cover`, `year`, `genre`, and `rating`. Covers can be HTTPS URLs or existing
paths under `/covers/`.

Posts are managed by `~/bin/blog-publish` on server1. The timer remains in
`--dry-run` mode until this change has been reviewed and merged. Build with
Node 22.12 or later and `npm ci && npm run build`.
