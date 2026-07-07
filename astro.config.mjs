// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
  // TODO(사용자 결정 대기): 실제 배포 주소로 교체.
  //  - user/organization pages:  https://<USERNAME>.github.io
  //  - project pages:            https://<USERNAME>.github.io + base: '/<REPO>'
  //  - custom domain:            https://media.example.com (base 제거)
  site: 'https://example.github.io',
  // base: '/media_blog',
});
