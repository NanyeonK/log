#!/usr/bin/env python3
"""Regression tests use isolated sources, checkouts and local bare remotes."""
import importlib.machinery
import importlib.util
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('blog_publish', os.environ.get('BLOG_PUBLISH', str(Path.home() / 'bin/blog-publish')))
spec = importlib.util.spec_from_loader(loader.name, loader)
publisher = importlib.util.module_from_spec(spec)
loader.exec_module(publisher)

def git(*args, cwd):
    return subprocess.run(['git', *args], cwd=cwd, text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

def note(path, title, category, extra=''):
    path.write_text(f'---\ntitle: {title}\ndate: "2026-11-22"\npublish: true\ncategory: "{category}"\ntags: []\n{extra}---\nBody\n', encoding='utf-8')

class PublisherRegression(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='blog-regression-')
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
    def tearDown(self):
        self.tmp.cleanup()

    def test_1_identical_unmanaged_is_never_adopted(self):
        note(self.source/'same.md', 'Same', 'book')
        desired = publisher.scan('log', self.source)
        dest, content = desired['same.md']
        target = self.root/dest
        target.parent.mkdir(parents=True)
        target.write_bytes(content)
        with self.assertRaisesRegex(ValueError, 'unmanaged'):
            publisher.plan('log', self.root, desired, {})
        self.assertEqual(target.read_bytes(), content)
        print('  unmanaged identical target: refused; original preserved')

    def test_2_user_slugs_cannot_override_ids(self):
        for filename in ('first', 'second'):
            note(self.source/f'{filename}.md', filename, 'book', 'slug: shared\n')
        desired = publisher.scan('log', self.source)
        self.assertEqual({v[0] for v in desired.values()}, {'src/content/posts/first.md', 'src/content/posts/second.md'})
        self.assertTrue(all('slug:' not in content.decode() for _, content in desired.values()))
        print('  duplicate user slug stripped: first.md, second.md')

    def test_3_unicode_categories_and_collisions_build(self):
        checkout = self.root/'site'
        shutil.copytree(ROOT, checkout, ignore=shutil.ignore_patterns('.git', 'node_modules', 'dist', '.astro', '__pycache__'))
        posts = checkout/'src/content/posts'
        for i, category in enumerate(('이슈', '생각', 'C++', 'thought', 'book', 'a b')):
            note(self.source/f'post-{i}.md', f'Post {i}', category, 'slug: shared\n')
        for dest, content in publisher.scan('log', self.source).values():
            (checkout/dest).write_bytes(content)
        publisher.build_log(checkout)
        pages = {p.parent.name for p in (checkout/'dist/categories').glob('*/index.html')}
        slug = lambda raw, base: f"{base}-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"
        cpp_slug = slug('C++', 'c')
        self.assertTrue({'이슈', '생각', 'thought', 'book', cpp_slug, slug('a b', 'a-b')} <= pages, pages)
        note(posts/'c-sharp.md', 'C sharp', 'C#')
        publisher.build_log(checkout)
        pages = {p.parent.name for p in (checkout/'dist/categories').glob('*/index.html')}
        self.assertTrue({cpp_slug, slug('C#', 'c'), '이슈', '생각'} <= pages, pages)
        self.assertEqual(len(list((checkout/'dist/posts').glob('*/index.html'))), 7)
        print('  category pages:', ', '.join(sorted(pages)))
        print('  C++ slug unchanged after adding C#:', cpp_slug)
        print('  distinct post pages: 7')
        # A literal category matching the generated slug must still fail the build.
        note(posts/'collision.md', 'Collision', cpp_slug)
        with self.assertRaisesRegex(ValueError, 'Category URL slug collision'):
            publisher.build_log(checkout)
        (posts/'collision.md').unlink()
        print('  literal hashed-slug collision: Astro build rejected')
        # Reuse the installed checkout to exercise the real schema validator.
        note(posts/'invalid.md', 'Bad', 'book', 'rating: 11\nyear: "bad"\n')
        env = os.environ.copy()
        env['PATH'] = str(Path.home()/'.local/share/blog-publish-runtime/node_modules/node/bin') + ':' + env['PATH']
        build = subprocess.run(['npm', 'run', 'build'], cwd=checkout, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertNotEqual(build.returncode, 0, build.stdout)
        print('  invalid rating/year: Astro build rejected')

    def test_4_rejected_push_clears_journal_and_next_attempt_works(self):
        remote = self.root/'remote.git'
        work = self.root/'work'
        git('init', '--bare', str(remote), cwd=self.root)
        git('init', '-b', 'main', str(work), cwd=self.root)
        git('config', 'user.email', 'test@example.invalid', cwd=work)
        git('config', 'user.name', 'Test', cwd=work)
        (work/'one').write_text('one')
        git('add', 'one', cwd=work)
        git('commit', '-m', 'one', cwd=work)
        git('remote', 'add', 'origin', str(remote), cwd=work)
        hook = remote/'hooks/pre-receive'
        hook.write_text('#!/bin/sh\necho rejected >&2\nexit 1\n')
        hook.chmod(0o755)
        journal = self.root/'pending.json'
        journal.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'push rejected'):
            publisher.push_commit(work, journal)
        self.assertFalse(journal.exists())
        hook.unlink()
        journal.write_text('{}')
        publisher.push_commit(work, journal)
        self.assertEqual(git('rev-parse', 'HEAD', cwd=work).strip(), git('rev-parse', 'refs/heads/main', cwd=remote).strip())
        other = self.root/'other'
        git('clone', '-b', 'main', str(remote), str(other), cwd=self.root)
        git('config', 'user.email', 'test@example.invalid', cwd=other)
        git('config', 'user.name', 'Test', cwd=other)
        (other/'two').write_text('two')
        git('add', 'two', cwd=other)
        git('commit', '-m', 'other update', cwd=other)
        git('push', 'origin', 'main', cwd=other)
        (work/'three').write_text('three')
        git('add', 'three', cwd=work)
        git('commit', '-m', 'stale update', cwd=work)
        journal.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'push rejected'):
            publisher.push_commit(work, journal)
        self.assertFalse(journal.exists())
        journal.write_text('{}')
        ambiguous = subprocess.CompletedProcess([], 1, '', 'connection lost')
        with patch.object(publisher.subprocess, 'run', return_value=ambiguous):
            with self.assertRaisesRegex(ValueError, 'outcome unknown'):
                publisher.push_commit(work, journal)
        self.assertTrue(journal.exists())
        print('  rejected and non-fast-forward pushes: journals cleared; retry succeeded')
        print('  ambiguous push: journal preserved for reconciliation')

    def test_5_failed_build_prevents_push(self):
        repos, sources, heads = {}, {}, {}
        for kind in ('academic', 'log'):
            remote = self.root/f'{kind}.git'
            checkout = self.root/kind
            git('init', '--bare', str(remote), cwd=self.root)
            if kind == 'log':
                shutil.copytree(ROOT, checkout, ignore=shutil.ignore_patterns('.git', 'node_modules', 'dist', '.astro', '__pycache__'))
            else:
                checkout.mkdir()
                (checkout/'README').write_text('academic')
            git('init', '-b', 'main', cwd=checkout)
            git('config', 'user.email', 'test@example.invalid', cwd=checkout)
            git('config', 'user.name', 'Test', cwd=checkout)
            git('add', '.', cwd=checkout)
            git('commit', '-m', 'initial', cwd=checkout)
            git('remote', 'add', 'origin', str(remote), cwd=checkout)
            git('push', 'origin', 'main', cwd=checkout)
            heads[kind] = git('rev-parse', 'refs/heads/main', cwd=remote).strip()
            repos[kind] = checkout
            sources[kind] = self.root/f'{kind}-source'
            sources[kind].mkdir()
        note(sources['log']/'invalid.md', 'Bad', 'book', 'rating: 11\n')
        note(sources['academic']/'valid.md', 'Academic', 'book')
        state = self.root/'state'
        with patch.object(publisher, 'REPOS', repos), patch.object(publisher, 'SOURCES', sources), \
             patch.object(publisher, 'DEFAULT', state), patch.object(publisher.os.path, 'ismount', return_value=True), \
             patch('sys.argv', ['blog-publish']):
            with self.assertRaisesRegex(ValueError, 'log validation failed'):
                publisher.main()
        for kind in repos:
            self.assertEqual(heads[kind], git('rev-parse', 'refs/heads/main', cwd=self.root/f'{kind}.git').strip())
        self.assertFalse((state/'pending.json').exists())
        print('  invalid schema: build failed; neither remote changed; no journal')

if __name__ == '__main__':
    unittest.main(verbosity=2)
